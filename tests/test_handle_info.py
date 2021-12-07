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

# Import vkapi from parent directory
currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)

from vkapi import *  # noqa


# TODO proper test framework
def TestHandleInfo(registry_file):
  r = Registry(registry_file,
               platforms=['', 'android', 'ggp'],
               authors=['', 'KHR', 'EXT', 'ANDROID', 'GGP'],
               blocked_extensions=[
                   'VK_KHR_acceleration_structure',
                   'VK_KHR_ray_tracing_pipeline'
               ])
  hi = HandleInfoGlobals(r)

  # Check HandleInfo.handle
  assert hi.handle_info('VkInstance').handle == r.types['VkInstance']
  assert hi.handle_info('VkDevice').handle == r.types['VkDevice']
  assert hi.handle_info('VkBuffer').handle == r.types['VkBuffer']

  # Check HanldeInfo.parent
  assert hi.handle_info('VkInstance').parent is None
  assert hi.handle_info('VkDevice').parent == r.types['VkPhysicalDevice']
  assert hi.handle_info('VkBuffer').parent == r.types['VkDevice']
  assert hi.handle_info('VkSwapchainKHR').parent == r.types['VkDevice']
  assert hi.handle_info('VkSurfaceKHR').parent == r.types['VkInstance']

  # Check HandleInfo.pool
  assert hi.handle_info('VkInstance').pool is None
  assert hi.handle_info('VkDevice').pool is None
  assert hi.handle_info('VkDeviceMemory').pool is None
  assert hi.handle_info('VkDescriptorSet').pool == r.types['VkDescriptorPool']
  assert hi.handle_info('VkCommandBuffer').pool == r.types['VkCommandPool']

  # Check HandleInfo.pool_elem
  assert hi.handle_info('VkInstance').pool_elem is None
  assert hi.handle_info('VkDevice').pool_elem is None
  assert hi.handle_info('VkDeviceMemory').pool_elem is None
  assert hi.handle_info('VkDescriptorSet').pool_elem is None
  assert hi.handle_info(
      'VkDescriptorPool').pool_elem == r.types['VkDescriptorSet']
  assert hi.handle_info('VkCommandBuffer').pool_elem is None
  assert hi.handle_info('VkCommandPool').pool_elem == r.types['VkCommandBuffer']

  # Check HandleInfo.create_cmds
  assert set(cc.command for cc in hi.handle_info('VkInstance').create_cmds) == {
      r.commands['vkCreateInstance']
  }
  assert set(cc.command for cc in hi.handle_info('VkDevice').create_cmds) == {
      r.commands['vkCreateDevice']
  }
  assert set(cc.command for cc in hi.handle_info('VkQueue').create_cmds) == {
      r.commands['vkGetDeviceQueue'],
      r.commands['vkGetDeviceQueue2'],
  }
  assert set(cc.command for cc in hi.handle_info('VkPipeline').create_cmds) == {
      r.commands['vkCreateGraphicsPipelines'],
      r.commands['vkCreateComputePipelines'],
  }
  assert set(
      cc.command for cc in hi.handle_info('VkSurfaceKHR').create_cmds) == {
          r.commands['vkCreateStreamDescriptorSurfaceGGP'],
          r.commands['vkCreateAndroidSurfaceKHR'],
          r.commands['vkCreateDisplayPlaneSurfaceKHR'],
          r.commands['vkCreateHeadlessSurfaceEXT'],
      }
  assert set(
      cc.command for cc in hi.handle_info('VkDescriptorSet').create_cmds) == {
          r.commands['vkAllocateDescriptorSets']
      }
  assert set(
      cc.command for cc in hi.handle_info('VkCommandBuffer').create_cmds) == {
          r.commands['vkAllocateCommandBuffers']
      }
  assert set(
      cc.command for cc in hi.handle_info('VkDeviceMemory').create_cmds) == {
          r.commands['vkAllocateMemory']
      }

  # Check HandleInfo.destroy_cmd
  assert hi.handle_info(
      'VkInstance').destroy_cmd.command == r.commands['vkDestroyInstance']
  assert hi.handle_info(
      'VkDevice').destroy_cmd.command == r.commands['vkDestroyDevice']
  assert hi.handle_info('VkPhysicalDevice').destroy_cmd is None
  assert hi.handle_info('VkQueue').destroy_cmd is None
  assert hi.handle_info(
      'VkPipeline').destroy_cmd.command == r.commands['vkDestroyPipeline']
  assert hi.handle_info(
      'VkSurfaceKHR').destroy_cmd.command == r.commands['vkDestroySurfaceKHR']
  assert hi.handle_info('VkDescriptorSet').destroy_cmd.command == r.commands[
      'vkFreeDescriptorSets']
  assert hi.handle_info('VkCommandBuffer').destroy_cmd.command == r.commands[
      'vkFreeCommandBuffers']
  assert hi.handle_info(
      'VkDeviceMemory').destroy_cmd.command == r.commands['vkFreeMemory']

  # Check HandleInfo.reset_pool_cmd
  assert hi.handle_info('VkInstance').reset_pool_cmd is None
  assert hi.handle_info('VkDescriptorSet').reset_pool_cmd.command == r.commands[
      'vkResetDescriptorPool']
  assert hi.handle_info('VkDescriptorPool').reset_pool_cmd is None
  assert hi.handle_info('VkCommandBuffer').reset_pool_cmd is None
  assert hi.handle_info('VkCommandPool').reset_pool_cmd is None
  assert hi.handle_info('VkDeviceMemory').reset_pool_cmd is None

  # Check HandleInfo.object_type
  VkObjectType = r.types['VkObjectType']
  assert hi.handle_info('VkInstance').object_type == VkObjectType.values[
      'VK_OBJECT_TYPE_INSTANCE']
  assert hi.handle_info(
      'VkDevice').object_type == VkObjectType.values['VK_OBJECT_TYPE_DEVICE']
  assert hi.handle_info(
      'VkImage').object_type == VkObjectType.values['VK_OBJECT_TYPE_IMAGE']


def TestHandleCreateCommand(registry_file):
  r = Registry(registry_file,
               platforms=['', 'android', 'ggp'],
               authors=['', 'KHR', 'EXT', 'ANDROID', 'GGP'],
               blocked_extensions=[
                   'VK_KHR_acceleration_structure',
                   'VK_KHR_ray_tracing_pipeline'
               ])
  hi = HandleInfoGlobals(r)

  vkCreateInstance = hi.handle_info('VkInstance').create_cmds[0]
  assert vkCreateInstance.command == r.commands['vkCreateInstance']
  assert vkCreateInstance.parent_param is None
  assert vkCreateInstance.create_info == r.types['VkInstanceCreateInfo']
  assert vkCreateInstance.create_info_param.name == 'pCreateInfo'
  assert vkCreateInstance.pool_member is None
  assert vkCreateInstance.handle_param.name == 'pInstance'
  assert vkCreateInstance.is_create
  assert not vkCreateInstance.is_pool_allocate
  assert not vkCreateInstance.is_get

  vkEnumeratePhysicalDevices = hi.handle_info('VkPhysicalDevice').create_cmds[0]
  assert vkEnumeratePhysicalDevices.command == r.commands[
      'vkEnumeratePhysicalDevices']
  assert vkEnumeratePhysicalDevices.parent_param.name == 'instance'
  assert vkEnumeratePhysicalDevices.create_info is None
  assert vkEnumeratePhysicalDevices.create_info_param is None
  assert vkEnumeratePhysicalDevices.pool_member is None
  assert vkEnumeratePhysicalDevices.handle_param.name == 'pPhysicalDevices'
  assert not vkEnumeratePhysicalDevices.is_create
  assert not vkEnumeratePhysicalDevices.is_pool_allocate
  assert vkEnumeratePhysicalDevices.is_get

  vkAllocateDescriptorSets = hi.handle_info('VkDescriptorSet').create_cmds[0]
  assert vkAllocateDescriptorSets.command == r.commands[
      'vkAllocateDescriptorSets']
  assert vkAllocateDescriptorSets.parent_param.name == 'device'
  assert vkAllocateDescriptorSets.create_info == r.types[
      'VkDescriptorSetAllocateInfo']
  assert vkAllocateDescriptorSets.create_info_param.name == 'pAllocateInfo'
  assert vkAllocateDescriptorSets.pool_member.name == 'descriptorPool'
  assert vkAllocateDescriptorSets.handle_param.name == 'pDescriptorSets'
  assert not vkAllocateDescriptorSets.is_create
  assert vkAllocateDescriptorSets.is_pool_allocate
  assert not vkAllocateDescriptorSets.is_get


def TestHandleDestroyCommand(registry_file):
  r = Registry(registry_file,
               platforms=['', 'android', 'ggp'],
               authors=['', 'KHR', 'EXT', 'ANDROID', 'GGP'],
               blocked_extensions=[
                   'VK_KHR_acceleration_structure',
                   'VK_KHR_ray_tracing_pipeline'
               ])
  hi = HandleInfoGlobals(r)

  vkDestroyInstance = hi.handle_info('VkInstance').destroy_cmd
  assert vkDestroyInstance.command == r.commands['vkDestroyInstance']
  assert vkDestroyInstance.parent_param is None
  assert vkDestroyInstance.pool_param is None
  assert vkDestroyInstance.handle_param.name == 'instance'

  vkFreeDescriptorSets = hi.handle_info('VkDescriptorSet').destroy_cmd
  assert vkFreeDescriptorSets.command == r.commands['vkFreeDescriptorSets']
  assert vkFreeDescriptorSets.parent_param.name == 'device'
  assert vkFreeDescriptorSets.pool_param.name == 'descriptorPool'
  assert vkFreeDescriptorSets.handle_param.name == 'pDescriptorSets'

  vkResetDescriptorPool = hi.handle_info('VkDescriptorSet').reset_pool_cmd
  assert vkResetDescriptorPool.command == r.commands['vkResetDescriptorPool']
  assert vkResetDescriptorPool.parent_param.name == 'device'
  assert vkResetDescriptorPool.pool_param.name == 'descriptorPool'
  assert vkResetDescriptorPool.handle_param is None


registry_file=sys.argv[1] if len(sys.argv) > 1 else 'vk.xml'
TestHandleInfo(registry_file)
TestHandleCreateCommand(registry_file)
TestHandleDestroyCommand(registry_file)
