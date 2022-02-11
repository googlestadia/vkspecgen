# Copyright (C) 2021 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# vkapi parses the Vulkan XML specification into a registry of types and commands.
# This Registry can be used to query the Vulkan API to generate code or other uses.

import xml.etree.ElementTree as ET
import copy
import jinja2
import re
from dataclasses import dataclass
from typing import Optional


# Base Type class.
class Type:

  def __init__(self, name, xml_node):
    self._name = name
    self.extensions = []
    self.xml_node = xml_node

  @property
  def name(self):
    return self._name

  def __str__(self):
    return self.name


# TypeRef class.
# This is used to reference a type that has yet to be defined.
# This is to help parse for self-referencing structs and forward decls.
# Mostly intended for internal parser usage.
class TypeRef(Type):

  def __init__(self, name):
    super().__init__(name, None)
    self.ref = name


# TypeAlias calss.
# Use for types that are promoted and now alias
class TypeAlias(Type):

  def __init__(self, name, alias):
    super().__init__(name, None)
    self.alias = alias

  # Returns the aliased type, recurses as needed.
  def resolve_type(self):
    ta = self
    while isinstance(ta, TypeAlias):
      ta = ta.alias
    return ta

  @property
  def is_base_type_alias(self):
    alias = self.alias
    while isinstance(alias, TypeAlias):
      alias = alias.alias
    return isinstance(alias, BaseType)


# BaseType types are pre-defined Vulkan types (VkBool32, VkResult, etc.)
# Base C/C++ types such as unit32_t, float, etc. belong here.
class BaseType(Type):

  def __init__(self, name, xml_node):
    super().__init__(name, xml_node)


# FunctionPtr represent function pointers.
class FunctionPtr(Type):

  def __init__(self, registry, te):
    super().__init__(te.find('name').text, te)
    # TODO parse the parameters for types and names.
    # They are obnoxiously a different schema than command parameters.
    self.parameters = []


# Handle
# Represents any Vulkan Handle.
class Handle(Type):
  # Initialize from a type element node.
  def __init__(self, registry, te):
    super().__init__(te.find('name').text, te)
    self.is_dispatchable = te.find('type').text == 'VK_DEFINE_HANDLE'
    self.parent = TypeRef(te.get('parent', ''))

  @property
  def is_device_handle(self):
    return not self.is_instance_handle

  @property
  def is_instance_handle(self):
    if self.name == 'VkDevice':
      return False
    elif self.name == 'VkInstance':
      return True
    elif self.name == 'VkSwapchainKHR':
      return False
    return self.parent.is_instance_handle


# EnumValue
# Represents an enum value.
class EnumValue(Type):

  def __init__(self, name, value, xml_node):
    super().__init__(name, xml_node)
    self.value = value
    self.comment = None

  def __str__(self):
    return str(self.value)


# Enum
# Represents a Vulkan/C enum type.
class Enum(Type):
  # Initialize from a type element node.
  # Optionally specify the name directly (for Enums without enum elements)
  # <enums name="VkImageLayout" type="enum">
  def __init__(self, te, name=None):
    self.values = {}
    self.is_bitmask = False
    self.bitwidth = 32

    if te is None:
      super().__init__(name, None)
      return

    super().__init__(te.get('name'), te)

    if te.get('bitwidth'):
      self.bitwidth = int(te.get('bitwidth'))

    # This means this enum is a FlagBits enum required by a bitmask type.
    self.is_bitmask = te.get('type') == 'bitmask'

    # Enum value elements look like this:
    # <enum value="0"   name="VK_IMAGE_LAYOUT_UNDEFINED"  comment="blah"/>
    for ee in te.findall('enum'):
      en = ee.get('name')
      if ee.get('alias') is not None:
        self.values[en] = TypeAlias(en, ee.get('alias'))
        continue
      try:
        if ee.get('bitpos') is not None:
          self.is_bitmask = True
          str_v = ee.get('bitpos')
          ev = str_v
          if str_v.startswith("0x"):
            ev = 1 << int(str_v, base=16)
          else:
            ev = 1 << int(str_v, base=10)
        else:
          str_v = ee.get('value')
          ev = str_v
          if str_v.startswith("0x"):
            ev = int(str_v, base=16)
          else:
            ev = int(str_v, base=10)
      except ValueError:
        pass
      self.values[en] = EnumValue(en, ev, ee)
      if ee.get('comment') is not None:
        self.values[en].comment = ee.get('comment')

  # Returns a {name:int} dictionary of all enum values, resolving alises.
  def get_integer_values(self):
    iv = {}
    for v in self.values.values():
      if isinstance(v, EnumValue):
        iv[v.name] = v.value
      else:
        iv[v.name] = v.resolve_type().value

    return iv

  def unique_values(self):
    return resolve_aliases(self.values)


# Bitmask
# Represents a Vulkan bitmask type, points to the enum of flag values.
class Bitmask(Type):

  def __init__(self, registry, te):
    super().__init__(te.find('name').text, te)
    self.type = te.find('type').text

    # Not all bitmasks have enums, often because they have no defined
    # values (placeholder types).
    self.flags = None
    if te.get('requires') is not None:
      self.flags = registry.types[te.get('requires')]


# Field
# A Struct member or Command parameter
class Field:

  def __init__(self, name, type, xml_node):
    self.name = name
    self.type = type
    self.is_optional = False
    self.is_output = False
    self.bit_size = None
    self.values = []  # list of allowed values
    self.xml_node = xml_node

  def __str__(self):
    return self.name


# TypeModifier
# A modified type (pointer, array, etc)
class TypeModifier(Type):

  def __init__(self, t):
    super().__init__(t.name, None)
    self.base_type = t
    self.is_const = False

  @property
  def name(self):
    const = "Const" if self.is_const else ""
    return f"{const}{type(self).__name__}({self.base_type.name})"


# NextPtr
class NextPtr(TypeModifier):

  def __init__(self, t):
    super().__init__(t)


# Pointer
class Pointer(TypeModifier):

  def __init__(self, t):
    super().__init__(t)


# DynamicArray length is usually a parameter.
class DynamicArray(TypeModifier):

  def __init__(self, t, length, parent):
    super().__init__(t)
    self.length = length
    self.parent = parent

  # Returns a C++ expression for the length
  # For dynamic arrays that are fields of structs, `obj_expr` should be an
  # expression for the struct containing this dynamic array.
  # For dynamic arrays that are parameters of commands, `obj_expr` could be
  # None (if the parameters are in-scope in the generated code), or could be an
  # expression for a struct storing the parameters.
  def length_expr(self, obj_expr: Optional[str] = None) -> str:
    # find the part of the `length` string that looks like a field
    # e.g. "pImageCount" or "pAllocateInfo->descriptorSetCount"
    match = re.search(r'\b[a-zA-Z](\w|->)+', self.length)
    if match is None:
      return self.length
    length_field_name = match[0]
    length_field_parts = length_field_name.split('->')

    def find_field(ty, name):
      if isinstance(ty, Command):
        return ty.find_parameter(name)
      else:
        return ty.find_member(name)

    # Some lengths are inside another struct
    # (e.g. "pAllocateInfo->descriptorSetCount").
    # Find the inner-most struct type containing the length field
    obj_ty = self.parent
    for part in length_field_parts[:-1]:
      field = find_field(obj_ty, part)
      assert (isinstance(field.type, Pointer) and
              isinstance(field.type.base_type, Struct))
      obj_ty = field.type.base_type

    length_field = find_field(obj_ty, length_field_parts[-1])

    if length_field is None:
      # In some cases, the length is actually a constant instead of a field
      # name; in that case, just return the original length string
      return self.length

    # prepend the object expression
    length_field_expr = length_field_name
    if obj_expr is not None:
      length_field_expr = obj_expr + "." + length_field_expr

    # dereference length pointer
    if isinstance(length_field.type, Pointer):
      length_field_expr = "*" + length_field_expr

    return self.length.replace(length_field_name, length_field_expr)


# FixedArray is aixed length array
class FixedArray(TypeModifier):

  def __init__(self, t, length):
    super().__init__(t)
    self.length = length


# Platform describes a Vulkan plaform: name, #ifdef, types and commands
class Platform:

  def __init__(self, registry, pe):
    self.xml_node = pe
    if pe is not None:
      self.name = pe.get('name')
      self.macro = pe.get('protect')

      self.select_types_and_commands(registry)
    else:
      # Default platform (i.e. no platform)
      self.name = ''
      self.macro = ''

      # This selects types and commands from non-platform specific extensions.
      self.select_types_and_commands(registry)

      # Finaly we add types and commands without an extension (core)
      core_commands = {
          k: v for (k, v) in registry.commands.items() if len(v.extensions) == 0
      }

      core_types = {
          k: v for (k, v) in registry.types.items() if len(v.extensions) == 0
      }

      self.commands = self.commands | core_commands
      self.types = self.types | core_types

  def select_types_and_commands(self, registry):
    self.extensions = {
        k: v
        for (k, v) in registry.extensions.items()
        if self.name == v.platform
    }

    exts = set(self.extensions.values())
    self.commands = {
        k: v
        for (k, v) in registry.commands.items()
        if len(exts.intersection(v.extensions)) > 0
    }
    self.types = {
        k: v
        for (k, v) in registry.types.items()
        if len(exts.intersection(v.extensions)) > 0
    }


# Handles enum value extensions from either ex
def parse_enum_extend(registry, ee, extnumber):
  # Get the base enum and exten it's list of values.
  name = ee.get('name')
  base_enum = ee.get('extends')
  enum = registry.types[base_enum]

  # Sigh...
  # <enum alias="VK_STRUCTURE_TYPE_DEBUG_REPORT_CALLBACK_CREATE_INFO_EXT" extends="VkStructureType" name="VK_STRUCTURE_TYPE_DEBUG_REPORT_CREATE_INFO_EXT" comment="Backwards-compatible alias containing a typo"/>
  if ee.get('alias') is not None:
    # print(f'alias {name} -> {alias}')
    ev = TypeAlias(name, ee.get('alias'))
    enum.values[ev.name] = ev
    return ev

  # A few extensions set values directly (e.g VK_KHR_push_descriptor)
  if ee.get('value') is not None:
    value = int(ee.get('value'))
  # Extended bitmask enums.
  elif enum.is_bitmask:
    value = 1 << int(ee.get('bitpos'))
  # Extended enums with magic calculation.
  else:
    offset = int(ee.get('offset'))
    value = 1000000000 + (extnumber - 1) * 1000 + offset

  ev = EnumValue(name, value, ee)
  if ee.get('comment') is not None:
    ev.comment = ee.get('comment')
  enum.values[ev.name] = ev
  return ev


@dataclass
class _PointerLevel:
  is_const: bool = False
  is_fixed_array: bool = False
  length: Optional[str] = None


def _parse_type_modifiers(me):
  type_regex = re.compile(r'\bstruct\b|\bconst\b|\*|\[|:')
  type_str = me.text or ''
  for e in me:
    if e.text is not None and e.tag != 'type' and e.tag != 'name' and e.tag != 'comment':
      type_str += e.text
    if e.tail is not None:
      type_str += e.tail
  type_str = type_str.strip()
  is_const = False
  pointer_levels = []
  bits = None
  while len(type_str) > 0:
    m = type_regex.match(type_str)
    tok = m.group(0)
    assert (m is not None)
    type_str = type_str[len(tok):].strip()
    if tok == 'struct':
      continue
    elif tok == 'const':
      is_const = True
    elif tok == '*':
      pointer_levels.append(_PointerLevel(is_const=is_const))
      is_const = False
    elif tok == '[':
      length = re.match(r'[^\]]+', type_str)[0]
      type_str = type_str[len(length) + 1:].strip()
      pointer_levels.append(
          _PointerLevel(is_const=is_const, is_fixed_array=True, length=length))
      pass
    elif tok == ':':
      bits = re.match(r'[0-9]+', type_str)[0]
      type_str = type_str[len(bits):].strip()
      bits = int(bits)

  len_str = me.get('altlen')
  if len_str is None:
    len_str = me.get('len')
  if len_str is not None:
    dynamic_lengths = len_str.split(',')
  else:
    dynamic_lengths = []

  for i in range(len(dynamic_lengths)):
    assert (not pointer_levels[i].is_fixed_array)
    pointer_levels[i].length = dynamic_lengths[i]

  return pointer_levels, bits


# Parameter and member nodes are basically the same, we parse out all
# the various attributes and modifiers and return a type chain.
def parse_parameter_or_member(registry, me, parent):
  # A member element looks something this this:
  # <member>const <type>void</type>*   name>pNext</name></member>
  ne = me.find('name')
  te = me.find('type')
  name = ne.text
  base_type_name = te.text

  # Resolve aliased types.
  if base_type_name in registry.aliases:
    base_type_name = registry.aliases[base_type_name].name

  base_type = TypeRef(base_type_name)

  pointer_levels, bits = _parse_type_modifiers(me)

  t = base_type
  for ptr in reversed(pointer_levels):
    if ptr.is_fixed_array:
      length = ptr.length
      try:
        length = int(length)
      except ValueError:
        pass
      t = FixedArray(t, length)
      t.is_const = ptr.is_const
    elif ptr.length is not None:
      if ptr.length == 'null-terminated':
        t = TypeRef('string')
      else:
        t = DynamicArray(t, ptr.length, parent)
        t.is_const = ptr.is_const
    elif t.name == 'void' and name == 'pNext':
      t = NextPtr(t)
      t.is_const = ptr.is_const
    else:
      t = Pointer(t)
      t.is_const = ptr.is_const

  # Create the actual field
  f = Field(name, t, me)

  # Some struct members have allowed values.
  f.values = [x for x in me.get("values", "").split(',') if x]

  # Structs and parameters are both allowed to be optional (0 or null)
  f.is_optional = me.get('optional', '') == 'true'

  # Output parameters are non-const pointers.
  is_pointer = len(pointer_levels) > 0 and not pointer_levels[0].is_fixed_array
  is_const = len(pointer_levels) > 0 and pointer_levels[0].is_const
  f.is_output = is_pointer and not is_const

  f.bit_size = bits

  return f


# Struct
# Structs represet a 'struct' type from the Vulkan spec.
class Struct(Type):
  # Given a type element create the approproate struct type.
  def __init__(self, registry, te):
    super().__init__(te.attrib['name'], te)
    self.is_union = False
    self.members = [
        parse_parameter_or_member(registry, me, self)
        for me in te.findall('member')
    ]
    self.extendedby = []

    # Get a list of structs this struct can extend.
    structextends = te.get('structextends', '')
    self.structextends = [x for x in structextends.split(',') if x]

  def find_member(self, name: str) -> Optional[Field]:
    for m in self.members:
      if m.name == name:
        return m
    return None


class Command:
  # Given a command element, parses into a Command type
  def __init__(self, registry, ce):
    self.name = ce.find('proto/name').text
    self.return_type = registry.types[ce.find('proto/type').text]
    self.parameters = [
        parse_parameter_or_member(registry, me, self)
        for me in ce.findall('param')
    ]
    successcodes = ce.get('successcodes')
    if successcodes is not None:
      self.successcodes = successcodes.split(',')
    else:
      self.successcodes = []
    self.extensions = []
    self.feature = None
    self.xml_node = ce

  def find_parameter(self, name: str) -> Optional[Field]:
    for p in self.parameters:
      if p.name == name:
        return p
    return None

  def __str__(self):
    return self.name


class Extension:

  def __init__(self, registry, en):
    self.name = en.get('name')
    self.number = int(en.get('number'))
    self.type = en.get('type', '')
    self.author = en.get('author', '')
    self.supported = en.get('supported', '')
    self.promotedto = en.get('promotedto', '')
    self.deprecatedby = en.get('deprecatedby', '')
    self.platform = en.get('platform', '')
    self.requires = [x for x in en.get('requires', '').split(',') if x]
    self.specialuse = [x for x in en.get('specialuse', '').split(',') if x]

    # Read extension name and spec version enums.
    for ee in [t.get('name') for t in en.findall('require/enum[@value]')]:
      if ee.endswith('_EXTENSION_NAME'):
        self.name_enum = ee
      elif ee.endswith('_SPEC_VERSION'):
        self.spec_version_enum = ee

    self.types = [t.get('name') for t in en.findall('require/type')]
    self.commands = [t.get('name') for t in en.findall('require/command')]
    self.xml_node = en

    # We tag types and commands to extensions for filtering.
    for t in self.types:
      registry.types[t].extensions.append(self)

    for c in self.commands:
      registry.commands[c].extensions.append(self)

    # Next we parse the enums, however instead of associating the enums
    # with the extension we just expand the enum types as extra enum values
    # should be harmless and aren't really enabled by extensions anyways.
    for ee in en.findall('require/enum[@extends]'):
      ev = parse_enum_extend(registry, ee, self.number)
      ev.extensions.append(self)

  def __str__(self):
    return self.name


def PrintField(field):
  s = '\t'

  def PrintFieldType(t):
    if isinstance(t, Pointer):
      PrintFieldType(t.base_type)
      if t.is_const:
        s += ' const'
      s += '*'
    elif isinstance(t, DynamicArray) or isinstance(t, FixedArray):
      PrintFieldType(t.base_type)
    elif isinstance(t, NextPtr):
      if t.is_const:
        s += 'void const*'
      else:
        s += 'void *'
    else:
      s += t.name

  PrintFieldType(field.type)

  s = s + ' ' + field.name

  if isinstance(field.type, DynamicArray) or isinstance(t, FixedArray):
    s = s + f'[{field.type.length}]'
  if field.is_optional:
    s = s + ' (optional)'
  if field.is_output:
    s = s + ' =>output'
  print(s)


def PrintType(t):
  print(t.name)
  if isinstance(t, Struct):
    for p in t.members:
      PrintField(p)
    if len(t.structextends) > 0:
      print("\tExtends:")
    for e in t.structextends:
      print(f'\t\t{e}')
    if len(t.extendedby) > 0:
      print("\tExtended by:")
    for e in t.extendedby:
      print(f'\t\t{e}')

  if isinstance(t, TypeAlias):
    print(f'\talias -> {t.alias.name}')

  if isinstance(t, TypeRef):
    print(f'\tref -> {t.ref}')

  if isinstance(t, Command):
    for p in t.parameters:
      PrintField(p)

  if isinstance(t, Bitmask):
    if t.flags is not None:
      print(f'\t{t.flags.name}')

  if len(t.extensions) > 0:
    print('\tExtensions:')
    for x in t.extensions:
      print(f'\t\t{x.name}')


# Define
# Represents a define type in Vulkan registry.
class Define(Type):

  def __init__(self, registry, te):
    if 'name' in te.attrib:
      super().__init__(te.attrib['name'], te)
      self.tail = None
    else:
      name = te.find('name')
      super().__init__(name.text, te)
      self.tail = name.tail
    self.text = te.text


class Registry:

  def __init__(self,
               registry_file,
               platforms=[''],
               authors=['', 'KHR', 'EXT'],
               supported='vulkan',
               allowed_extensions=None,
               blocked_extensions=None):

    # Globals/Registry
    self.types = {}
    self.commands = {}
    self.extensions = {}
    self.aliases = {}
    self.platforms = {}
    self.constants = {}

    # Registry version information
    self.vk_api_version_major = 1
    self.vk_api_version_minor = 0
    self.vk_api_version_patch = 0

    root = ET.parse(registry_file).getroot()

    if platforms is None:
      platforms = ['']
      platforms.extend(
          [p.get('name') for p in root.findall("platforms/platform[@name]")])

    # Add the core platform here to keep it first in dictionary.
    if '' in platforms:
      self.platforms[''] = None

    self.__parse(root)

    if allowed_extensions is None:
      allowed_extensions = set()
    else:
      allowed_extensions = set(
          self.extensions[name] for name in allowed_extensions)

    if blocked_extensions is None:
      blocked_extensions = set()
    else:
      blocked_extensions = set(
          self.extensions[name] for name in blocked_extensions)

    self.__filter_registry(platforms, authors, supported, allowed_extensions,
                           blocked_extensions)

    # Add the default non-platform specific platform.
    # We do this post-filter to make sure we only include filtered types and commands.
    if '' in platforms:
      self.platforms[''] = Platform(self, None)

    # Extract registry version information
    defines = [t for t in self.types.values() if isinstance(t, Define)]
    define_names = [t.name for t in defines]
    if 'VK_API_VERSION_1_2' in define_names:
      self.vk_api_version_minor = 2
    elif 'VK_API_VERSION_1_1' in define_names:
      self.vk_api_version_minor = 1
    else:
      self.vk_api_version_minor = 0
    for dfn in defines:
      if dfn.name == 'VK_HEADER_VERSION':
        self.vk_api_version_patch = int(dfn.tail)

  def __parse(self, root):
    self.__parse_basetypes(root)
    self.__parse_enums(root)
    self.__parse_types(root)
    self.__parse_commands(root)
    self.__parse_extensions(root)
    self.__parse_features(root)
    self.__parse_platforms(root)

  def __parse_basetypes(self, root):
    # Add some special types.
    self.types['string'] = BaseType('string', None)

    # Read in all the basetype types as BaseType types
    for te in root.findall("types/type"):
      if te.get('category') is not None:
        if te.get('category') == 'basetype':
          name = te.find('name').text
          tte = te.find('type')
          if tte is not None:
            self.types[name] = TypeAlias(name, TypeRef(tte.text))
          else:
            self.types[name] = BaseType(name, te)
      else:
        # Catch the non-base type types.
        name = te.get('name')
        self.types[name] = BaseType(name, te)

  def __parse_enums(self, root):
    # Parse all enums.
    for ee in root.findall("enums"):
      enum_type = ee.get('type', '')
      e = Enum(ee)
      # Enum elements are also used for some constants
      if enum_type == 'enum' or enum_type == 'bitmask':
        self.types[e.name] = e
      else:
        for n, v in e.values.items():
          self.constants[n] = v

  def __parse_types(self, root):
    # Parse all the types we care about.
    for te in root.findall("types/type[@category]"):
      category = te.get('category')

      # Aliased types point to their alias.
      # Aliases a
      if te.get('alias') is not None:
        name = te.get('name')
        alias = te.get('alias')
        at = TypeAlias(name, self.types[alias])
        self.types[name] = at
        self.aliases[name] = at
      # Handles are Vulkan handles (VkDevice)
      # Both dispatcable and non-dispatchable.
      elif category == 'handle':
        st = Handle(self, te)
        self.types[st.name] = st
      # Structs represent C-type structs.
      elif category == 'struct':
        st = Struct(self, te)
        self.types[st.name] = st
      # We treat unions as structs for now.
      elif category == 'union':
        st = Struct(self, te)
        st.is_union = True
        self.types[st.name] = st
      elif category == 'funcpointer':
        fp = FunctionPtr(self, te)
        self.types[fp.name] = fp
      # Bitmasks types are types with a corresponding flags enum.
      elif category == 'bitmask':
        bm = Bitmask(self, te)
        self.types[bm.name] = bm
      # We use define type to extract Vulkan version information.
      elif category == 'define':
        dfn = Define(self, te)
        self.types[dfn.name] = dfn

    # Some types are not defined in order and we use a TypeRef
    # to refer to them. We fix them up here.
    for t in self.types.values():
      t = self.__resolve_typeref(t)

    # Struct extends are in text, convert to types
    for t in self.types.values():
      if isinstance(t, Struct):
        for se in t.structextends:
          et = self.types[se]
          # Check for duplicates (which can be caused by aliasing)
          if t not in et.extendedby:
            et.extendedby.append(t)

        # convert struct extends to type ref (not just name)
        t.structextends = [self.types[se] for se in t.structextends]

  # Resolve all TypeRef in the given type. Recurses if needed.
  def __resolve_typeref(self, t):
    if isinstance(t, TypeRef):
      return self.types[t.ref]
    # Resolve TypeRefs for handle parents.
    elif isinstance(t, Handle):
      if isinstance(t.parent, TypeRef):
        if t.parent.ref == '':
          t.parent = None
        else:
          t.parent = self.__resolve_typeref(t.parent)
    # TODO IndirectType base? (pointer, array, fixedarray?)
    elif isinstance(t, DynamicArray) or isinstance(t, FixedArray) or isinstance(
        t, Pointer):
      t.base_type = self.__resolve_typeref(t.base_type)
    # Resolve TypeRefs for struct fields.
    elif isinstance(t, Struct):
      for m in t.members:
        m.type = self.__resolve_typeref(m.type)
    elif isinstance(t, TypeAlias):
      t.alias = self.__resolve_typeref(t.alias)
    return t

  def __parse_commands(self, root):
    # Parse all the commands.
    for ce in root.findall('commands/command'):
      if ce.get('alias') is not None:
        name = ce.get('name')
        alias = ce.get('alias')
        # print("cmd alias: " + name + "->" + alias)
        self.commands[name] = self.commands[alias]
        self.aliases[name] = alias
      else:
        cmd = Command(self, ce)
        # print('command ' + cmd.name)
        self.commands[cmd.name] = cmd

    # Resolve all type refs and determine if instance or device
    for cmd in self.commands.values():
      for p in cmd.parameters:
        p.type = self.__resolve_typeref(p.type)

      # Determine if this is an 'instance' command, used for
      # dispatch tables other layer related queries.
      cmd.is_instance = (cmd.name == 'vkCreateInstance' or
                         (isinstance(cmd.parameters[0].type, Handle) and
                          cmd.parameters[0].type.is_instance_handle))

  def __parse_extensions(self, root):
    # Parse all the extensions.
    for ee in root.findall('extensions/extension'):
      # We will ignore numbered and reserved extensions
      name = ee.get('name', '')
      if "RESERVED" in name:
        continue
      if name.endswith(ee.get('number')):
        continue

      ext = Extension(self, ee)
      self.extensions[ext.name] = ext

  # Parse the "Features" sections of the spec.
  # This is where promoted types are defined and we need to parse this to
  # properly evaluate all type aliases.
  # Currently we don't separate by feature set (1.0 vs 1.1 vs 1.2).
  def __parse_features(self, root):
    # Currently we only handle extended enum values as this is where
    # the promoted values are defined.
    for ee in root.findall('feature/require/enum[@extends]'):
      ev = parse_enum_extend(self, ee, int(ee.get('extnumber', '0')))

    # Set the Vulkan "feature" for each command (i.e. the Vulkan version where
    # the command was added to Vulkan Core)
    for f in root.findall('feature'):
      v = f.get('name')
      for c in f.findall('require/command'):
        name = c.get('name')
        self.commands[name].feature = v

    # At this point in parsing all types should be defined, we can
    # now resolve enum value aliases to point to the actual type.
    for k in self.types:
      v = self.types[k]
      if isinstance(v, Enum):
        for en, ev in v.values.items():
          if isinstance(ev, TypeAlias):
            ev.alias = v.values[ev.alias]

  # Parse the platform defines
  def __parse_platforms(self, root):
    for pe in root.findall('platforms/platform'):
      p = Platform(self, pe)
      self.platforms[p.name] = p

  # Return a set of extensions that match the given requirements.
  def __select_extensions(self, platforms, extension_authors, supported):
    # TODO: None == all?
    extensions = []
    for x in self.extensions.values():
      if (x.platform in platforms and x.supported in supported and
          (extension_authors is None or x.author in extension_authors)):
        extensions.append(x)

    return extensions

  # When filtering types we may need to modify the type, in which case
  # we create a copy of the type first and modify that.
  def __filter_type(self, t, platforms, extension_authors, supported):
    if not isinstance(t, Enum):
      return t

    # Copy the Enum and then filter values
    enum = copy.copy(t)
    enum.values = {}
    for (en, ev) in t.values.items():
      # TODO can we share this filter better?
      # TODO cleaner to make a list of extensions and intersect?
      if len(ev.extensions) > 0:
        for x in ev.extensions:
          if (x.platform in platforms and x.supported in supported and
              (extension_authors is None or x.author in extension_authors)):
            enum.values[en] = ev
            break
      # No extension, core.
      elif extension_authors is None or '' in extension_authors:
        enum.values[en] = ev

    return enum

  # Filter a single type, modifying if needed.
  def __filter_type_by_extensions(self, t, extension_set):
    if isinstance(t, Struct):
      # filter up the extendedby and structextends lists

      extendedby = []
      for eb in t.extendedby:
        if len(eb.extensions) > 0:
          if len(extension_set.intersection(eb.extensions)) > 0:
            extendedby.append(eb)
        else:
          extendedby.append(eb)

      structextends = []
      for eb in t.structextends:
        if len(eb.extensions) > 0:
          if len(extension_set.intersection(eb.extensions)) > 0:
            structextends.append(eb)
        else:
          structextends.append(eb)

      t.extendedby = extendedby
      t.structextends = structextends

      return t
    elif isinstance(t, Enum):
      # filter the extension values
      for en in list(t.values):
        ev = t.values[en]

        # If this is part of an extension, check it meets our filter.
        if len(ev.extensions) > 0:
          if len(extension_set.intersection(ev.extensions)) == 0:
            del t.values[en]

    return t

  # Modifies the registy to only have the requestied platform and authors.
  def __filter_registry(self, platforms, extension_authors, supported,
                        allowed_extensions, blocked_extensions):
    filtered_ex = self.__select_extensions(platforms, extension_authors,
                                           supported)
    filtered_set = set(filtered_ex)
    filtered_set = filtered_set.union(allowed_extensions)
    filtered_set = filtered_set.difference(blocked_extensions)

    # Filter extensions.
    self.extensions = {
        k: v for (k, v) in self.extensions.items() if v in filtered_set
    }

    # Filter platforms.
    self.platforms = {
        k: v for (k, v) in self.platforms.items() if k in platforms
    }

    # Filter all the types.
    for tname in list(self.types):
      t = self.types[tname]

      # If this is part of an extension, check it meets our filter.
      if len(t.extensions) > 0:
        if len(filtered_set.intersection(t.extensions)) > 0:
          self.types[tname] = self.__filter_type_by_extensions(t, filtered_set)
        else:
          del self.types[tname]

      # No extension, core?
      elif extension_authors is None or '' in extension_authors:
        self.types[tname] = self.__filter_type_by_extensions(t, filtered_set)
      # Drop.
      else:
        del self.types[tname]

    # Filter all the commands.
    for tname in list(self.commands):
      t = self.commands[tname]

      # If this is part of an extension, check it meets our filter.
      if len(t.extensions) > 0:
        if len(filtered_set.intersection(t.extensions)) > 0:
          self.commands[tname] = t
        else:
          del self.commands[tname]

      # No extension, core?
      elif extension_authors is None or '' in extension_authors:
        self.commands[tname] = t
      # Drop.
      else:
        del self.commands[tname]


# Removes all type aliases from the dictionary.
# Item (key, value) will have the condition: key == value.name
def resolve_aliases(aliased: dict, resolve_base_type_aliases: bool = False):
  return {
      value.name: value
      for (key, value) in aliased.items()
      if not isinstance(value, TypeAlias) or
      (value.is_base_type_alias and not resolve_base_type_aliases)
  }


# Returns a Jinja2 Environment initialized with vkapi types and some
# functions useful for working with the Registry in Jinja2
def JinjaEnvironment(registry, *args, **kwargs):
  env = jinja2.Environment(*args, **kwargs)

  def type_test(t):
    return lambda v: isinstance(v, t)

  env.tests.update(
      Type=type_test(Type),
      TypeAlias=type_test(TypeAlias),
      BaseType=type_test(BaseType),
      Struct=type_test(Struct),
      FunctionPtr=type_test(FunctionPtr),
      Handle=type_test(Handle),
      Enum=type_test(Enum),
      Bitmask=type_test(Bitmask),
      EnumValue=type_test(EnumValue),
      Field=type_test(Field),
      TypeModifier=type_test(TypeModifier),
      Pointer=type_test(Pointer),
      DynamicArray=type_test(DynamicArray),
      FixedArray=type_test(FixedArray),
      NextPtr=type_test(NextPtr),
  )

  env.globals.update(
      registry=registry,
      isinstance=isinstance,
      constants=registry.constants,
      Type=Type,
      TypeAlias=TypeAlias,
      BaseType=BaseType,
      Struct=Struct,
      FunctionPtr=FunctionPtr,
      Handle=Handle,
      Enum=Enum,
      Bitmask=Bitmask,
      EnumValue=EnumValue,
      Field=Field,
      TypeModifier=TypeModifier,
      Pointer=Pointer,
      DynamicArray=DynamicArray,
      FixedArray=FixedArray,
      NextPtr=NextPtr,
  )

  def filtered_types(type_kind):
    return [t for t in registry.types.values() if isinstance(t, type_kind)]

  def command_or_alias(name, cmd):
    if name == cmd.name:
      return cmd
    else:
      return TypeAlias(name=name, alias=cmd)

  env.globals.update(
      commands=[
          command_or_alias(name, cmd)
          for name, cmd in registry.commands.items()
      ],
      types=registry.types.values(),
      aliases=filtered_types(TypeAlias),
      base_types=filtered_types(BaseType),
      structs=filtered_types(Struct),
      function_ptrs=filtered_types(FunctionPtr),
      handles=filtered_types(Handle),
      enums=filtered_types(Enum),
      bitmasks=filtered_types(Bitmask),
      enum_values=filtered_types(EnumValue),
      fields=filtered_types(Field),
      type_modifiers=filtered_types(TypeModifier),
      pointers=filtered_types(Pointer),
      dynamic_arrays=filtered_types(DynamicArray),
      fixed_arrays=filtered_types(FixedArray),
  )

  return env
