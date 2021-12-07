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

# vklayerprint is a sample generator that creates a Vulkan layer
# that will print out Vulkan command parmeters to console.

# This is meant to be an example of how to use the vkcodgen registry with
# a variety of different template techniques.

import jinja2
import argparse
import os
import sys

currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)

import vkapi  # noqa


def visit_type(t: vkapi.TypeModifier, visited: dict):
  if t.name not in visited:
    if isinstance(t, vkapi.Struct):
      for p in t.members:
        visit_type(p.type, visited)
      visited[t.name] = t
    elif isinstance(t, vkapi.Pointer) or isinstance(
        t, vkapi.DynamicArray) or isinstance(t, vkapi.FixedArray):
      visit_type(t.base_type, visited)
    else:
      visited[t.name] = t


# Return the set of types referenced by a command list.
def referenced_types(commands: list):
  visited = {}
  for cmd in commands:
    for p in cmd.parameters:
      visit_type(p.type, visited)

  return visited


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

# Figure out which types we need to understand based on our command set.
types = referenced_types(registry.commands.values())

# Create a Jinja2 templating environment
env = vkapi.JinjaEnvironment(
    registry, loader=jinja2.FileSystemLoader(searchpath='examples/templates'))

platform_structs = {
    k: [t for t in v.types.values() if isinstance(t, vkapi.Struct)
       ] for (k, v) in registry.platforms.items()
}

parameters = {
    'enums': [t for t in types.values() if isinstance(t, vkapi.Enum)],
    'platform_structs': platform_structs,
    'layer_prefix': 'Printer',
}

tmp = env.from_string(open('examples/templates/layerprint.cpp.jinja2').read())
out = tmp.render(parameters)
with open("print.cc", "w") as text_file:
  text_file.write(out)

tmp = env.from_string(open('examples/templates/layer_base.cpp.jinja2').read())
out = tmp.render(parameters)
with open("layer_base.cc", "w") as text_file:
  text_file.write(out)

tmp = env.from_string(open('examples/templates/dispatch.h.jinja2').read())
out = tmp.render(parameters)
with open("dispatch.h", "w") as text_file:
  text_file.write(out)

tmp = env.from_string(open('examples/templates/dispatch.cpp.jinja2').read())
out = tmp.render(parameters)
with open("dispatch.cc", "w") as text_file:
  text_file.write(out)

os.system("clang-format -i -style=google print.cc")
os.system("clang-format -i -style=google layer_base.cc")
os.system("clang-format -i -style=google dispatch.h")
os.system("clang-format -i -style=google dispatch.cc")
