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

from .vkapi import *
from typing import Dict, List, Optional, Callable, Tuple, Union
import dataclasses
from dataclasses import dataclass


@dataclass
class HandleCreateCommand:
  """Information about a handle-creation command

  Args:
    command: handle creation command (e.g. vkCreateImage)
    parent_param: parameter of command for the parent (e.g. device in
      vkCreateImage)
    create_info: type of the *CreateInfo struct (e.g. VkImageCreateInfo)
    create_info_param: parameter of command that holds the pointer to the
      create_info struct
    pool_member: field of create_info struct that holds the pool for the newly
      created handle (e.g. descriptorPool in VkDescriptorSetAllocateInfo)
    handle_param: output parameter of command for the newly created handles
    is_create: indicates this is a `vkCreate*`-style command--new handle(s)
      are created, and they do not belong to any pool
    is_pool_allocate: indicates this is a command that creates new handles in
      a pool (e.g. vkAllocateDescriptorSets)
    is_get: indicates this is a command that returns existing handles, rather
      than creating new handles. E.g. `vkGetDeviceQueue` or
      `vkEnumeratePhysicalDevices`
  """
  command: Command
  parent_param: Optional[Field] = None
  create_info: Optional[Struct] = None
  create_info_param: Optional[Field] = None
  pool_member: Optional[Field] = None
  handle_param: Optional[Field] = None
  is_create: bool = False
  is_pool_allocate: bool = False
  is_get: bool = False


@dataclass
class HandleDestroyCommand:
  """Information about a handle-destruction command

  Args:
    command: handle destruction command (e.g. vkDestroyImage)
    parent_param: parameter of command that holds the parent (e.g. device in
      vkDestroyImage)
    pool_param: parameter of command for the pool containing the destroyed
      handles (e.g. descriptorPool in vkFreeDescriptorSets). None for handles
      that don't belong to pools
    handle_param: parameter of command for the handle(s) being destroyed
  """
  command: Command
  parent_param: Optional[Field]
  pool_param: Optional[Field]
  handle_param: Optional[Field]


@dataclass
class HandleInfo:
  """Information about the commands that create/destroy a handle type

  Args:
    handle: handle type
    parent: parent handle type (e.g. VkDevice is the parent for VkImage)
    pool: pool handle type (e.g. VkDescriptorPool is the pool for
      VkDescriptorSet)
    pool_elem: handle type of elements in *this* pool (e.g. VkDescriptorSet is
      the pool_elem for VkDescriptorPool). None for non-pool handles.
    create_cmds: list of commands that create this handle type
    destroy_cmd: command that destroys this handle type
    reset_pool_cmd: command that destroys all handles of this type within a
      pool (e.g. vkResetDescriptorPool is reset_pool_cmd for VkDescriptorSet)
      *Note:* vkResetCommandPool is *not* reset_pool_cmd for VkCommandBuffer,
      because vkResetCommandPool does not free the command buffers, merely
      moves the command buffers back to the initial state.
    object_type: the VkObjectType enum value for this handle type
  """
  handle: Handle
  parent: Optional[Handle] = None
  pool: Optional[Handle] = None
  pool_elem: Optional[Handle] = None
  create_cmds: List[HandleCreateCommand] = dataclasses.field(
      default_factory=list)
  destroy_cmd: Optional[HandleDestroyCommand] = None
  reset_pool_cmd: Optional[HandleDestroyCommand] = None
  object_type: Optional[EnumValue] = None


class HandleInfoGlobals:
  """Functions for templates to access information about handles

  Example Usage:

    env = vkapi.JinjaEnvironment(registry)
    handle_infos = vkapi.HandleInfoGlobals(registry)
    env.globals.update(handle_infos.globals)
  """

  def __init__(self, registry: Registry):
    self._registry = registry
    self._build_handle_infos()

  @property
  def globals(self) -> Dict[str, Callable]:
    """Returns a dict to add to the jinja Environment globals"""
    return {
        f: getattr(self, f)
        for f in dir(self)
        if not f.startswith('_') and f != 'globals'
    }

  def handle_info(self, h: Union[str, Handle]) -> Optional[HandleInfo]:
    """Find HandleInfo for a given handle type"""
    if isinstance(h, Handle):
      h = h.name
    return self._handle_infos.get(h)

  def command_handle_created(
      self, cmd: Command
  ) -> Tuple[Optional[HandleInfo], Optional[HandleCreateCommand]]:
    """Find info about the handle type created by a command

    Returns: A pair (handle_info, handle_create_command). If cmd is not
      a handle-creation command, both handle_info and handle_create_command
      are None
    """
    for p in cmd.parameters:
      if not (isinstance(p.type, Pointer) or isinstance(p.type, DynamicArray)):
        continue
      if p.type.is_const:
        continue
      info = self.handle_info(p.type.base_type)
      if info is None:
        continue
      for create_cmd in info.create_cmds:
        if cmd is create_cmd.command and p is create_cmd.handle_param:
          return info, create_cmd
      continue
    return None, None

  def is_create_command(self, cmd: Command) -> bool:
    """Indicates whether the command is a handle-creation command

    E.g. vkCreateImage
    """
    info, create_cmd = self.command_handle_created(cmd)
    if create_cmd is not None:
      return create_cmd.is_create
    else:
      return False

  def is_pool_allocate_command(self, cmd: Command) -> bool:
    """Indicates whether the command allocates handles in a pool

    E.g. vkAllocateDescriptorSets
    """
    info, create_cmd = self.command_handle_created(cmd)
    if create_cmd is not None:
      return create_cmd.is_pool_allocate
    else:
      return False

  def is_get_command(self, cmd: Command) -> bool:
    """Indicates whether the command gets existing handles

    E.g. vkGetDeviceQueue or vkEnumeratePhysicalDevices
    """
    info, create_cmd = self.command_handle_created(cmd)
    if create_cmd is not None:
      return create_cmd.is_get
    else:
      return False

  def command_handle_destroyed(self, cmd: Command) -> Optional[HandleInfo]:
    """Find info about the handle type destroyed by a command

    Returns: Info about the destroyed handle type, or None if the command is
      not a handle-destruction command.
    """
    for p in cmd.parameters:
      t = p.type
      if isinstance(t, DynamicArray):
        t = t.base_type
      if not isinstance(t, Handle):
        continue
      info = self.handle_info(t)
      if info is None:
        continue
      if info.destroy_cmd is not None and cmd is info.destroy_cmd.command:
        return info

  def is_destroy_command(self, cmd: Command) -> bool:
    """Indicates whether the command is a handle-destruction command"""
    return self.command_handle_destroyed(cmd) is not None

  def command_pool_reset(
      self, cmd: Command) -> Tuple[Optional[HandleInfo], Optional[HandleInfo]]:
    """Find info about the handle type destroyed by a pool reset command

    Returns: Info about the destroyed handle type, or None if the command is
      not a pool reset command.

      E.g., for command_pool_reset(vkResetDescriptorPool) returns VkDescriptorSet
    """
    for p in cmd.parameters:
      pool_info = self.handle_info(p.type)
      if pool_info is None or pool_info.pool_elem is None:
        continue
      elem_info = self.handle_info(pool_info.pool_elem)
      if elem_info.reset_pool_cmd is not None and cmd is elem_info.reset_pool_cmd.command:
        return pool_info, elem_info
    return None, None

  def is_reset_pool_command(self, cmd: Command) -> bool:
    """Indicates whether the command is a pool-reset command"""
    pool_info, elem_info = self.command_pool_reset(cmd)
    return elem_info is not None

  def _build_handle_infos(self) -> None:
    registry = self._registry
    self._handle_infos = {}
    for name, cmd in registry.commands.items():
      if cmd.name != name:
        continue  # alias
      if name.startswith('vkCreate') or name.startswith('vkAllocate'):
        self._add_handle_create_command(name)
    self._add_handle_create_command('vkEnumeratePhysicalDevices')
    self._add_handle_create_command('vkGetDeviceQueue')
    self._add_handle_create_command('vkGetDeviceQueue2')
    self._add_handle_create_command('vkGetSwapchainImagesKHR')
    self._add_handle_create_command('vkGetDisplayPlaneSupportedDisplaysKHR')
    for name, t in registry.types.items():
      if t.name != name:
        continue  # alias
      if isinstance(t, Handle):
        if name not in self._handle_infos:
          print(f'Warning: Could not find create command for {name}')
          info = HandleInfo(
              handle=t,
              parent=t.parent,
          )
          self._handle_infos[name] = info

    for name, cmd in registry.commands.items():
      if cmd.name != name:
        continue  # alias
      if name.startswith('vkDestroy'):
        self._add_handle_destroy_command(name)
      elif name.startswith('vkFree'):
        self._add_handle_free_command(name)

    self._add_handle_reset_command('vkResetDescriptorPool')

    VkObjectType = registry.types['VkObjectType']
    for v in VkObjectType.values.values():
      if isinstance(v, TypeAlias):
        continue
      if v.name == 'VK_OBJECT_TYPE_UNKNOWN':
        continue
      handle_name = v.comment
      if handle_name not in self._handle_infos:
        words = v.name[len("VK_OBJECT_TYPE_"):].split('_')
        words = [w.capitalize() for w in words]
        if words[-1].upper() in {'EXT', 'KHR'}:
          words[-1] = words[-1].upper()
        handle_name = "Vk" + ''.join(words)
      self._handle_infos[handle_name].object_type = v

    for info in self._handle_infos.values():
      if info.object_type is None:
        print(f'ERROR: No VkObjectType found for {info.handle.name}')
        assert (info.object_type is not None)

    for info in self._handle_infos.values():
      if info.pool:
        self._handle_infos[info.pool.name].pool_elem = info.handle

  def _add_handle_create_command(self, name: str) -> None:
    cmd = self._registry.commands[name]
    parent_param = None
    create_info_param = None
    handle_param = None
    VkAllocationCallbacks = self._registry.types['VkAllocationCallbacks']
    for p in cmd.parameters:
      is_pointer = isinstance(p.type, Pointer) or isinstance(
          p.type, DynamicArray)
      is_pointer_to_struct = is_pointer and isinstance(p.type.base_type, Struct)
      is_pointer_to_handle = is_pointer and isinstance(p.type.base_type, Handle)
      if isinstance(p.type, Handle):
        if parent_param is None:
          parent_param = p
      if is_pointer_to_struct and p.type.is_const and p.type.base_type != VkAllocationCallbacks:
        assert (create_info_param is None)
        create_info_param = p
      elif is_pointer_to_handle and not p.type.is_const:
        assert (handle_param is None)
        handle_param = p
    if handle_param is None:
      print(f'Warning: no handle parameter found for {cmd.name}. Skipping.')
      return
    assert (parent_param is not None or name == 'vkCreateInstance')
    assert (handle_param is not None)
    parent = parent_param.type if parent_param is not None else None
    create_info = create_info_param.type.base_type if create_info_param is not None else None
    pool_member = None
    is_create = name.startswith('vkCreate')
    is_pool_allocate = False
    pool = None
    if name.startswith('vkAllocate'):
      for m in create_info.members:
        if isinstance(m.type, Handle):
          assert (pool_member is None)
          pool_member = m
      if pool_member is not None:
        is_pool_allocate = True
        pool = pool_member.type
      else:
        # vkAllocateMemory is actually a create command, not a pool allocation command
        is_create = True
    is_get = not (is_create or is_pool_allocate)
    handle = handle_param.type.base_type
    create_cmd = HandleCreateCommand(
        command=cmd,
        parent_param=parent_param,
        pool_member=pool_member,
        create_info=create_info,
        create_info_param=create_info_param,
        handle_param=handle_param,
        is_create=is_create,
        is_pool_allocate=is_pool_allocate,
        is_get=is_get,
    )
    if handle.name in self._handle_infos:
      info = self._handle_infos[handle.name]
      info.create_cmds.append(create_cmd)
      assert (info.handle is handle)
      assert (info.parent is parent)
      assert (info.pool is pool)
    else:
      info = HandleInfo(
          handle=handle,
          parent=parent,
          pool=pool,
          create_cmds=[create_cmd],
      )
      self._handle_infos[handle.name] = info

  def _add_handle_destroy_command(self, name: str) -> None:
    cmd = self._registry.commands[name]
    params = list(cmd.parameters)

    assert (2 <= len(params) and len(params) <= 3)

    parent_param = None
    if len(params) == 3:
      parent_param = params[0]
      params = params[1:]
      parent = parent_param.type
      assert (isinstance(parent, Handle))

    handle_param = params[0]
    handle = handle_param.type
    assert (isinstance(handle, Handle))

    alloc_param = params[1]
    assert (isinstance(alloc_param.type, Pointer))
    assert (isinstance(alloc_param.type.base_type, Struct))

    info = self._handle_infos[handle.name]
    assert (info.destroy_cmd is None)
    info.destroy_cmd = HandleDestroyCommand(
        command=cmd,
        parent_param=parent_param,
        pool_param=None,
        handle_param=handle_param,
    )

  def _add_handle_free_command(self, name: str) -> None:
    if name == 'vkFreeMemory':
      self._add_handle_destroy_command(name)
      return
    cmd = self._registry.commands[name]
    assert (len(cmd.parameters) == 4)

    parent_param = cmd.parameters[0]
    parent = parent_param.type
    assert (isinstance(parent, Handle))

    pool_param = cmd.parameters[1]
    pool = pool_param.type
    assert (isinstance(pool, Handle))

    count_param = cmd.parameters[2]
    count = count_param.type
    assert (count.name == 'uint32_t')

    handle_param = cmd.parameters[3]
    assert (isinstance(handle_param.type, DynamicArray))
    handle = handle_param.type.base_type
    assert (isinstance(handle, Handle))

    info = self._handle_infos[handle.name]
    assert (info.destroy_cmd is None)
    info.destroy_cmd = HandleDestroyCommand(
        command=cmd,
        parent_param=parent_param,
        pool_param=pool_param,
        handle_param=handle_param,
    )

  def _add_handle_reset_command(self, name: str) -> None:
    cmd = self._registry.commands[name]
    assert (len(cmd.parameters) >= 2)

    parent_param = cmd.parameters[0]
    parent = parent_param.type
    assert (isinstance(parent, Handle))

    pool_param = cmd.parameters[1]
    pool = pool_param.type
    if not isinstance(pool, Handle):
      return

    handle = None
    for info in self._handle_infos.values():
      if info.pool is not None and info.pool.name == pool.name:
        handle = info.handle
        break
    if handle is None:
      return
    assert (info.pool.name == pool.name)

    assert (info.reset_pool_cmd is None)
    info.reset_pool_cmd = HandleDestroyCommand(
        command=cmd,
        parent_param=parent_param,
        pool_param=pool_param,
        handle_param=None,
    )
