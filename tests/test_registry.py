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

import xml.etree.ElementTree as ET
import os
import sys
from collections import Counter

# Import vkapi from parent directory
currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)

from vkapi import *  # noqa


# TODO proper test framework
def TestParser(registry_file):
  r = Registry(registry_file,
               platforms=['', 'android', 'ggp'],
               authors=['', 'KHR', 'EXT', 'ANDROID', 'GGP'],
               allowed_extensions=['VK_KHR_acceleration_structure'])

  # Confirm handle parents make sense.
  assert r.types['VkInstance'].is_instance_handle
  assert not r.types['VkInstance'].is_device_handle

  assert not r.types['VkDevice'].is_instance_handle
  assert r.types['VkDevice'].is_device_handle

  assert r.types['VkCommandPool'].is_device_handle

  assert r.types['VkSurfaceKHR'].is_instance_handle
  assert r.types['VkSwapchainKHR'].is_device_handle

  # Basic type checks
  pdp = r.types["VkPhysicalDeviceProperties"]
  assert pdp is not None and isinstance(pdp, Struct)
  pcuuid = next(m for m in pdp.members if m.name == 'pipelineCacheUUID')
  assert isinstance(pcuuid.type, FixedArray)
  assert pcuuid.type.length == 'VK_UUID_SIZE'

  # Check some array and string array parsing.
  dci = r.types["VkDeviceCreateInfo"]

  pqci = next(m for m in dci.members if m.name == 'pQueueCreateInfos')
  assert isinstance(pqci.type, DynamicArray)
  assert pqci.type.length == 'queueCreateInfoCount'
  assert pqci.type.name == 'ConstDynamicArray(VkDeviceQueueCreateInfo)'

  een = next(m for m in dci.members if m.name == 'ppEnabledExtensionNames')
  assert isinstance(een.type, DynamicArray)
  assert een.type.length == 'enabledExtensionCount'
  assert een.type.name == 'ConstDynamicArray(string)'

  # Do some sanity checks using VkMemoryRequirements2 as it's got
  # aliases, extensions and promotions.
  assert 'VkMemoryRequirements2' in r.types

  # Command checks.
  assert r.commands['vkCreateInstance'].is_instance
  assert r.commands['vkEnumeratePhysicalDevices'].is_instance
  assert not r.commands['vkCmdDraw'].is_instance

  # Enum and enum values
  # Check that aliases are all valid and point to enum values
  # VkStructureType is one of the more complex with aliases to aliases
  # and promotions and such. So we just check this one works.
  st = r.types['VkStructureType']
  for ev in st.values.values():
    assert isinstance(ev, EnumValue) or isinstance(ev, TypeAlias) and (
        isinstance(ev.alias, EnumValue) or isinstance(ev.alias, TypeAlias))

  stiv = st.get_integer_values()
  for iv in stiv:
    assert isinstance(stiv[iv], int)

  # Check return types
  assert r.commands['vkCreateInstance'].return_type.name == 'VkResult'
  assert r.commands['vkCmdDraw'].return_type.name == 'void'
  assert r.commands[
      'vkGetBufferDeviceAddress'].return_type.name == 'VkDeviceAddress'

  # Pointer to pointer checks
  mm = r.commands['vkMapMemory']
  assert isinstance(mm.parameters[5].type, Pointer)
  assert not mm.parameters[5].type.is_const
  assert isinstance(mm.parameters[5].type.base_type, Pointer)
  assert not mm.parameters[5].type.base_type.is_const
  assert mm.parameters[5].type.base_type.name == 'Pointer(void)'
  assert mm.parameters[5].type.base_type.base_type.name == 'void'

  # Const pointer to pointec checks
  bas = r.commands['vkCmdBuildAccelerationStructuresKHR']
  assert isinstance(bas.parameters[3].type, DynamicArray)
  assert bas.parameters[3].type.is_const
  assert isinstance(bas.parameters[3].type.base_type, Pointer)
  assert bas.parameters[3].type.base_type.is_const
  assert bas.parameters[
      3].type.base_type.base_type.name == 'VkAccelerationStructureBuildRangeInfoKHR'

  # String type check
  ipa = r.commands['vkGetInstanceProcAddr']
  assert ipa.parameters[1].type.name == 'string'

  # Array type check
  bc = r.commands['vkCmdSetBlendConstants']
  assert isinstance(bc.parameters[1].type, FixedArray)
  assert bc.parameters[1].type.length == 4

  # 2-dimensional array type check
  tm = r.types['VkTransformMatrixKHR']
  assert isinstance(tm.members[0].type, FixedArray)
  assert tm.members[0].type.length == 3
  assert isinstance(tm.members[0].type.base_type, FixedArray)
  assert tm.members[0].type.base_type.length == 4
  assert tm.members[0].type.base_type.base_type.name == 'float'

  # String array checks
  ci = r.commands['vkCreateInstance']
  assert ci.parameters[0].name == 'pCreateInfo'
  assert isinstance(ci.parameters[0].type, Pointer)
  ici = ci.parameters[0].type.base_type
  assert isinstance(ici.members[5].type, DynamicArray)
  assert ici.members[5].type.name == 'ConstDynamicArray(string)'

  # Bit field checks
  asi = r.types['VkAccelerationStructureInstanceKHR']
  assert asi.members[0].bit_size is None
  assert asi.members[1].bit_size == 24

  # Output pointer check
  ci = r.commands['vkCreateImage']
  assert isinstance(ci.parameters[3].type, Pointer)
  assert ci.parameters[3].is_output

  # Output array check
  ads = r.commands['vkAllocateDescriptorSets']
  assert isinstance(ads.parameters[2].type, DynamicArray)
  assert ads.parameters[2].is_output

  # Non-output array of handles check
  bvb = r.commands['vkCmdBindVertexBuffers']
  assert isinstance(bvb.parameters[3].type, DynamicArray)
  assert not bvb.parameters[3].is_output

  # Successcodes check
  gfs = r.commands['vkGetFenceStatus']
  assert Counter(gfs.successcodes) == Counter(['VK_SUCCESS', 'VK_NOT_READY'])

  # EnumVal comment check
  ot = r.types['VkSwapchainCreateFlagBitsKHR']
  assert ot.values[
      'VK_SWAPCHAIN_CREATE_PROTECTED_BIT_KHR'].comment == 'Swapchain is protected'

  # Constants check
  assert r.constants['VK_MAX_PHYSICAL_DEVICE_NAME_SIZE'].value == 256
  assert r.constants['VK_LOD_CLAMP_NONE'].value == '1000.0F'
  assert r.constants['VK_REMAINING_MIP_LEVELS'].value == '(~0U)'

  # Base type alias check
  b32 = r.types['VkBool32']
  assert isinstance(b32, TypeAlias)
  assert b32.alias == r.types['uint32_t']

  # Test for TypeRef resolution
  si = r.types['VkSubmitInfo']
  assert si.members[4].name == 'pWaitDstStageMask'
  assert isinstance(si.members[4].type, DynamicArray)
  assert isinstance(si.members[4].type.base_type, Bitmask)

  up = r.commands['vkUpdateDescriptorSets']
  dw = up.parameters[2]
  assert isinstance(dw, Field)
  assert dw.type.name == 'ConstDynamicArray(VkWriteDescriptorSet)'
  assert isinstance(dw.type.base_type, Struct)
  wds = dw.type.base_type
  assert isinstance(wds.members[1].type, NextPtr)

  # Test struct extends
  ici = r.types['VkInstanceCreateInfo']
  assert len(ici.structextends) == 0
  for se in ici.extendedby:
    assert ici in se.structextends

  # Check enum value from included extension
  st = r.types['VkStructureType']
  assert 'VK_STRUCTURE_TYPE_SWAPCHAIN_CREATE_INFO_KHR' in st.values

  # Check filtering by author.
  r1 = Registry(registry_file, authors=[''])
  assert 'VkMemoryRequirements2' in r1.types
  assert 'VkMemoryRequirements2KHR' not in r1.types

  assert 'VkNativeBufferANDROID' not in r1.types

  # VkMemoryRequirements2 was promoted, it should be in core and have no
  # extensions.
  mr2 = r1.types["VkMemoryRequirements2"]
  assert mr2 is not None
  assert isinstance(mr2, Struct)
  assert len(mr2.extensions) == 0
  assert mr2.members[0].type == r1.types["VkStructureType"]
  assert mr2.members[0].values[0] == 'VK_STRUCTURE_TYPE_MEMORY_REQUIREMENTS_2'

  # Check enum value from excluded extension
  st = r1.types['VkStructureType']
  assert 'VK_STRUCTURE_TYPE_SWAPCHAIN_CREATE_INFO_KHR' not in st.values

  r2 = Registry(registry_file,
                authors=['', 'KHR'],
                allowed_extensions=['VK_EXT_private_data'])
  assert 'VkPrivateDataSlotEXT' in r2.types
  assert 'VkPrivateDataSlotEXT' not in r.types
  assert 'vkCreatePrivateDataSlotEXT' in r2.commands
  assert 'vkCreatePrivateDataSlotEXt' not in r.commands

  r3 = Registry(registry_file,
                authors=['', 'KHR'],
                blocked_extensions=['VK_KHR_display'])
  assert 'VkDisplayKHR' not in r3.types
  assert 'VkDisplayKHR' in r.types
  assert 'vkCreateDisplayModeKHR' not in r3.commands
  assert 'vkCreateDisplayModeKHR' in r.commands

  assert r.commands["vkCmdDrawIndexedIndirectCount"].feature == "VK_VERSION_1_2"
  assert r.commands["vkCmdDraw"].feature == "VK_VERSION_1_0"
  assert r.commands["vkGetSwapchainImagesKHR"].feature is None


def TestAliases(registry_file):
  r = Registry(registry_file)

  # Check alias resolution works.
  aliased_types = [at for at in r.types.values() if isinstance(at, TypeAlias)]
  aliased_base_types = [
      at for at in r.types.values()
      if isinstance(at, TypeAlias) and at.is_base_type_alias
  ]
  non_aliased_types = resolve_aliases(r.types)
  assert len(aliased_types) - len(aliased_base_types) + len(
      non_aliased_types) == len(r.types)

  # Confirm aliases are stripped.
  assert "VkMemoryRequirements2KHR" not in non_aliased_types
  assert "VkMemoryRequirements2" in non_aliased_types

  # Confirm base type aliases are not stripped
  assert "VkBool32" in non_aliased_types

  # Confirm base type aliases are stripped if resolve_base_type_aliases is True
  assert "VkBool32" not in resolve_aliases(r.types,
                                           resolve_base_type_aliases=True)

  # VkMemoryRequirements2KHR is an alias.
  # It should point to VkMemoryRequirements2 and have some extensions.
  mr2 = r.types["VkMemoryRequirements2"]
  mr2khr = r.types["VkMemoryRequirements2KHR"]
  assert isinstance(mr2khr, TypeAlias)
  assert mr2khr.alias == mr2
  assert len(mr2khr.extensions) == 2
  assert 'VK_KHR_get_memory_requirements2' in [
      ext.name for ext in mr2khr.extensions
  ]
  assert 'VK_NV_ray_tracing' in [ext.name for ext in mr2khr.extensions]


def TestFiltering(registry_file):
  # Select only the GGP extensions, make sure they get filtered.
  r = Registry(registry_file,
               platforms=['ggp'],
               authors=['', 'GGP'],
               supported='vulkan')

  assert 'VK_GGP_stream_descriptor_surface' in r.extensions
  assert 'VK_GGP_frame_token' in r.extensions
  # TODO FILTER EXTENSIONS assert 'VK_KHR_swapchain' not in r.extensions

  assert 'VkMemoryRequirements2KHR' not in r.types
  assert 'VkPresentFrameTokenGGP' in r.types
  assert 'VkPipelineCacheCreateInfo' in r.types


def TestEnumFiltering(registry_file):
  r = Registry(registry_file,
               platforms=['ggp'],
               authors=['', 'GGP'],
               supported='vulkan')

  # Check we filter out the enum values from VK_EXT_debug_report
  vkresult = r.types['VkResult']
  assert 'VK_ERROR_VALIDATION_FAILED_EXT' not in vkresult.values


def TestStructFiltering(registry_file):
  r = Registry(registry_file, platforms=[''], authors=['', 'KHR', 'EXT', 'AMD'])

  # Test that structs and their exteded refs get filtered
  assert 'VkPipelineRasterizationStateRasterizationOrderAMD' in r.types
  assert r.types['VkPipelineRasterizationStateCreateInfo'] in r.types[
      'VkPipelineRasterizationStateRasterizationOrderAMD'].structextends
  assert r.types[
      'VkPipelineRasterizationStateRasterizationOrderAMD'] in r.types[
          'VkPipelineRasterizationStateCreateInfo'].extendedby

  r = Registry(registry_file)

  # Make sure the AMD type and it's extended reference get removed
  assert 'VkPipelineRasterizationStateRasterizationOrderAMD' not in r.types
  assert 'VkPipelineRasterizationStateRasterizationOrderAMD' not in [
      x.name
      for x in r.types['VkPipelineRasterizationStateCreateInfo'].extendedby
  ]


def TestPlatforms(registry_file):
  r = Registry(registry_file)
  assert 'ggp' not in r.platforms

  # test the default/core platform
  p = r.platforms['']

  assert 'vkCmdDraw' in p.commands
  assert 'vkCreateDevice' in p.commands
  assert 'VK_EXT_debug_utils' in p.extensions
  assert 'VkGraphicsPipelineCreateInfo' in p.types
  assert 'VK_GGP_stream_descriptor_surface' not in p.extensions
  assert 'VkStreamDescriptorSurfaceCreateFlagsGGP' not in p.types
  assert 'vkCreateStreamDescriptorSurfaceGGP' not in p.commands

  # test platform filtering
  r = Registry(registry_file, platforms=['ggp'])

  ggp = r.platforms['ggp']
  assert ggp.macro == 'VK_USE_PLATFORM_GGP'
  assert 'VK_GGP_stream_descriptor_surface' in ggp.extensions
  assert 'VkStreamDescriptorSurfaceCreateFlagsGGP' in ggp.types
  assert 'vkCreateStreamDescriptorSurfaceGGP' in ggp.commands

  # win32 platform checks
  r = Registry(registry_file, platforms=['win32'])
  assert 'vkCreateAndroidSurfaceKHR' not in r.commands

  win = r.platforms['win32']
  ws = win.commands['vkCreateWin32SurfaceKHR']
  sci = ws.parameters[1]
  assert sci.name == 'pCreateInfo'

  # core vs platform checks
  r = Registry(registry_file, platforms=['', 'win32'])
  assert 'vkCreateWin32SurfaceKHR' not in r.platforms[''].commands
  assert 'vkCreateWin32SurfaceKHR' in r.platforms['win32'].commands

  # test all platforms and authors
  assert 'xlib_xrandr' not in r.platforms
  assert 'VK_FUCHSIA_imagepipe_surface' not in r.extensions
  assert 'VK_EXT_filter_cubic' not in r.extensions
  assert 'VK_INTEL_shader_integer_functions2' not in r.extensions
  r = Registry(registry_file, platforms=None, authors=None)
  assert 'VK_FUCHSIA_imagepipe_surface' in r.extensions
  assert 'VK_EXT_filter_cubic' in r.extensions
  assert 'VK_INTEL_shader_integer_functions2' in r.extensions
  assert 'xlib_xrandr' in r.platforms
  assert 16 == len(r.platforms)


def TestLengthExpr(registry_file):
  r = Registry(registry_file,
               platforms=['', 'android', 'ggp'],
               authors=['', 'KHR', 'EXT', 'GGP'],
               allowed_extensions=['VK_KHR_acceleration_structure'])
  c = r.commands['vkAllocateDescriptorSets']
  p = c.find_parameter('pDescriptorSets')
  assert 'pAllocateInfo->descriptorSetCount' == p.type.length_expr()
  assert 'my_args.pAllocateInfo->descriptorSetCount' == p.type.length_expr(
      'my_args')

  c = r.commands['vkEnumeratePhysicalDevices']
  p = c.find_parameter('pPhysicalDevices')
  assert '*pPhysicalDeviceCount' == p.type.length_expr()
  assert '*my_args.pPhysicalDeviceCount' == p.type.length_expr('my_args')

  t = r.types['VkPipelineMultisampleStateCreateInfo']
  m = t.find_member('pSampleMask')
  assert '(my_obj.rasterizationSamples + 31) / 32' == m.type.length_expr(
      'my_obj')

  t = r.types['VkAccelerationStructureVersionInfoKHR']
  m = t.find_member('pVersionData')
  assert '2*VK_UUID_SIZE' == m.type.length_expr('my_obj')


def TestXmlNodes(registry_file):
  r = Registry(registry_file, platforms=['', 'ggp'])

  # Every type must have an xml node unless it's a string or a type alias
  for t in r.types.values():
    if t.name == 'string' or isinstance(t, TypeAlias):
      assert t.xml_node is None, t
    else:
      assert isinstance(t.xml_node, ET.Element), t

  def check_obj_attr(obj, expected_class, attr_name, expected_attr):
    assert isinstance(obj, expected_class)
    actual_attr = obj.xml_node.attrib[attr_name]
    assert actual_attr == expected_attr, actual_attr

  def check_type_attr(name, expected_class, attr_name, expected_attr):
    check_obj_attr(r.types[name], expected_class, attr_name, expected_attr)

  # Tests for type classes
  check_type_attr('uint32_t', BaseType, 'name', 'uint32_t')
  check_type_attr('VkPhysicalDeviceProperties', Struct, 'returnedonly', 'true')
  check_type_attr('PFN_vkDebugUtilsMessengerCallbackEXT', FunctionPtr,
                  'requires', 'VkDebugUtilsMessengerCallbackDataEXT')
  check_type_attr('VkPhysicalDevice', Handle, 'parent', 'VkInstance')
  check_type_attr('VkFormat', Enum, 'name', 'VkFormat')
  check_type_attr('VkQueueFlags', Bitmask, 'requires', 'VkQueueFlagBits')
  check_type_attr('VK_API_VERSION_1_1', Define, 'requires',
                  'VK_MAKE_API_VERSION')

  ev = r.types['VkStructureType'].values['VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO']
  check_obj_attr(ev, EnumValue, 'value', '3')

  field = r.types['VkBaseInStructure'].find_member('pNext')
  check_obj_attr(field, Field, 'optional', 'true')

  # Type modifiers must have no xml node
  ptr = r.types['VkBaseInStructure'].find_member('pNext').type
  assert isinstance(ptr, TypeModifier)
  assert ptr.xml_node == None

  # Every command must have an xml node
  for c in r.commands.values():
    assert isinstance(c.xml_node, ET.Element), c

  assert Counter(r.commands['vkCreateInstance'].successcodes) == Counter(
      ['VK_SUCCESS'])
  assert Counter(
      r.commands['vkEnumerateDeviceLayerProperties'].errorcodes) == Counter(
          ['VK_ERROR_OUT_OF_HOST_MEMORY', 'VK_ERROR_OUT_OF_DEVICE_MEMORY'])

  # Every constant must have an xml node unless it's a type alias
  for c in r.constants.values():
    if isinstance(c, TypeAlias):
      assert c.xml_node is None, c
    else:
      assert isinstance(c.xml_node, ET.Element), c

  check_obj_attr(r.constants['VK_UUID_SIZE'], EnumValue, 'value', '16')

  # Every extension must have an xml node
  for e in r.extensions.values():
    assert isinstance(e.xml_node, ET.Element), e

  check_obj_attr(r.extensions['VK_KHR_surface'], Extension, 'author', 'KHR')

  # Every platform must have an xml node unless it's a default platform
  for p in r.platforms.values():
    if p.name == '':
      assert p.xml_node is None
    else:
      assert isinstance(p.xml_node, ET.Element), p

  check_obj_attr(r.platforms['ggp'], Platform, 'protect', 'VK_USE_PLATFORM_GGP')


def TestExtensionEnums(registry_file):
  r = Registry(registry_file)
  p = r.platforms['']
  extname = 'VK_KHR_get_physical_device_properties2'
  assert extname in p.extensions
  assert p.extensions[
      extname].name_enum == 'VK_KHR_GET_PHYSICAL_DEVICE_PROPERTIES_2_EXTENSION_NAME'
  assert p.extensions[
      extname].spec_version_enum == 'VK_KHR_GET_PHYSICAL_DEVICE_PROPERTIES_2_SPEC_VERSION'


registry_file = sys.argv[1] if len(sys.argv) > 1 else 'vk.xml'
TestParser(registry_file)
TestAliases(registry_file)
TestFiltering(registry_file)
TestEnumFiltering(registry_file)
TestStructFiltering(registry_file)
TestPlatforms(registry_file)
TestLengthExpr(registry_file)
TestXmlNodes(registry_file)
TestExtensionEnums(registry_file)
