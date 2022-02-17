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

import os
import sys
import argparse

# Import vkapi from parent directory
currentdir = os.path.dirname(os.path.realpath(__file__))
vkspecgendir = os.path.dirname(os.path.dirname(currentdir))
sys.path.append(vkspecgendir)

import vkapi  # noqa

# Map base C types to flatbuffer types
c_to_fb = {
    'char': 'ubyte',
    'float': 'float',
    'double': 'double',
    'int8_t': 'byte',
    'uint8_t': 'ubyte',
    'int16_t': 'short',
    'uint16_t': 'ushort',
    'int32_t': 'int',
    'uint32_t': 'uint',
    'int64_t': 'long',
    'uint64_t': 'ulong',
    'size_t': 'ulong',

    # Base Vulkan types that can be lowered directly.
    'VkBool32': 'uint',
    'VkFlags': 'uint',
    'VkFlags64': 'ulong',
    'VkSampleMask': 'uint',
    'VkDeviceSize': 'ulong',
    'VkDeviceMemory': 'ulong',
    'VkDeviceAddress': 'ulong',
}


# Converts a parameter (or struct member) to a flat buffer entry.
def parameter_to_flatbuffer(field, ftype):
  # TODO: Should fixed arrays be listed here?
  if isinstance(ftype, vkapi.DynamicArray):
    return '[' + parameter_to_flatbuffer(field, ftype.base_type) + ']'

  if isinstance(ftype, vkapi.Pointer):
    return parameter_to_flatbuffer(field, ftype.base_type)

  # TODO output parameters or arrays?
  if ftype.name == 'void':
    return 'ubyte'

  # TODO builtin should have a base type? based on typedef?
  if isinstance(ftype, vkapi.Bitmask):
    return 'uint'

  # Function pointers are treated as opaque 64bit values.
  if isinstance(ftype, vkapi.FunctionPtr):
    return 'ulong'

  fb = ftype.name
  if fb in c_to_fb:
    fb = c_to_fb[fb]

  return fb


# Determine the default value of the member.
# This is mostly relevant for enums with out 0 values as 0 is considered
# a valid default
def field_default_value(field):
  if field.type is None:
    return None

  if isinstance(field.type, vkapi.Enum):
    # Empty enums are given a default 0 value when converted.
    if len(field.type.values) == 0:
      return None

    # Return the lowest value if no 0.
    iv = field.type.get_integer_values()
    if 0 not in iv.values():
      return str(min(iv.values()))

  return None


# Prints a member of a struct (or command parameter) table
def print_field(field):
  s = f'    {field.name}: {parameter_to_flatbuffer(field, field.type)}'

  # FlatBuffer scalars (enums) with no 0 value must specify a default.
  default_value = field_default_value(field)
  if default_value is not None:
    s = s + ' = ' + default_value

  # Make non-optional tables required fields.
  #    if not m.is_optional and isinstance(mtype, vkapi.Struct):
  #        s = s + ' (required)'

  s = s + ';'
  print(s)


def print_struct(t):
  # VkClearColorValue is an enum of arrays, FlatBuffers just can't easily
  # represent this as a union, so we consider it a fixed byte array.
  if t.name == 'VkClearColorValue':
    print('struct VkClearColorValue {')
    print('    values: [ubyte:32];')
    print('}')
    print()
    return

  # TODO decide if struct, native struct or table
  if t.is_union:
    # We consider unions a table and treat non-union as optional.
    print('table ' + t.name + ' {')
  else:
    print('table ' + t.name + ' {')

  for m in t.members:
    # TODO decide to make (required)
    print_field(m)
  print('}')
  print()


def print_handle(h):
  print('struct ' + h.name + ' {')
  print('    handle: ulong;')
  print('}')
  print()


def print_enum(e):
  # FlatBuffer enums must have unique values.
  # So we create a value->name map then iterate on that.

  iv = e.get_integer_values()
  bitwidth = e.bitwidth
  value_to_name = {}
  for ev in e.values:
    v = iv[ev]
    value_to_name[v] = ev

  # Vulkan spec has bitmasks VkFlags typedef'd to XxxFlags.
  # The values however are as enum XxxFlagBits.
  # For flatbuffers we just rename the enum to match the VkFlags
  # named types.
  if bitwidth == 32:
    print('enum ' + e.name + ': int {')
  else:
    print('enum ' + e.name + ': int64 {')

  if len(value_to_name) == 0:
    print('\tNONE')

  for ev in value_to_name:
    print('\t' + value_to_name[ev] + ' = ' + str(ev) + ', ')
  print('}')
  print()


def print_command(c):
  tname = c.name + 'Params'
  print('table ' + tname + ' {')

  for p in c.parameters:
    # TODO decide to make (required)
    print_field(p)
  print('}')
  print()


# Main routine - setup Jinja and
parser = argparse.ArgumentParser()
parser.add_argument("-s", "--spec", help="path to the vk.xml spec file")
parser.add_argument("-p",
                    "--platform",
                    help="target platforms for the layer[win32, xcb, ggp, ...]",
                    nargs='+')

args = parser.parse_args()

specfile = args.spec
if specfile is None:
  specfile = 'vk.xml'

if not os.path.exists(specfile):
  print("Vulkan spec '" + os.path.abspath(specfile) + "' not found.")
  exit(-1)

print("Loading Vulkan spec '" + os.path.abspath(specfile) + "'.")

# Handle multiple platforms but always handle core.
platforms = ['']
if args.platform is not None:
  platforms.extend(args.platform)

print(f'Platforms: {platforms}')
registry = vkapi.Registry(specfile, platforms=platforms)

print("namespace vcr;")
print()

parsed = {}
for t in registry.types:

  # Aliased types can create duplicates, only write once.
  if t in parsed:
    continue
  parsed[t] = t

  if isinstance(t, vkapi.Enum):
    print_enum(t)
  elif isinstance(t, vkapi.Struct):
    print_struct(t)
  elif isinstance(t, vkapi.Handle):
    print_handle(t)

commands = vkapi.resolve_aliases(registry.commands)
for c in commands.values():
  print_command(c)
