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

cmake_minimum_required(VERSION 3.0)

project(printlayer LANGUAGES CXX C)

# Determine Vulkan's include directory
if (NOT VULKAN_INCLUDE_DIR)
  if (UNIX)
    if (GGP)
      set(VULKAN_INCLUDE_DIR "${GGP_SYSROOT_PATH}/usr/include/vulkan12")
    elseif(APPLE)
      if (DEFINED ENV{VULKAN_SDK})
        set(VULKAN_INCLUDE_DIR "$ENV{VULKAN_SDK}/include")
      endif()
    else()
      if (DEFINED ENV{VULKAN_SDK})
        set(VULKAN_INCLUDE_DIR "$ENV{VULKAN_SDK}/x86_64/include")
      endif()
    endif()
  elseif (WIN32)
    if (DEFINED ENV{VULKAN_SDK})
      set(VULKAN_INCLUDE_DIR "$ENV{VULKAN_SDK}/Include")
    endif()
  endif()
endif()

# Determine Vulkan's library directory
if (NOT VULKAN_LIBRARY_DIR)
  if (UNIX)
    if (GGP)
      set(VULKAN_LIBRARY_DIR "${GGP_SYSROOT_PATH}/usr/local/lib")
    elseif(APPLE)
      if (DEFINED ENV{VULKAN_SDK})
        set(VULKAN_LIBRARY_DIR "${VULKAN_SDK}/lib")
      endif()
    else()
      if (DEFINED ENV{VULKAN_SDK})
        set(VULKAN_LIBRARY_DIR "$ENV{VULKAN_SDK}/x86_64/lib")
      endif()
    endif()
  elseif (WIN32)
    if (DEFINED ENV{VULKAN_SDK})
      set(VULKAN_LIBRARY_DIR "$ENV{VULKAN_SDK}/Lib")
    endif()
  endif()
endif()

# Bail if Vulkan's include directory is not set
if (NOT VULKAN_INCLUDE_DIR)
  message(FATAL_ERROR "VULKAN_INCLUDE_DIR not specified and could not be determined using environment variable VULKAN_SDK")
endif()

# Bail if Vulkan's library directory is not set
if (NOT VULKAN_LIBRARY_DIR)
  message(FATAL_ERROR "VULKAN_LIBRARY_DIR not specified and could not be determined using environment variable VULKAN_SDK")
endif()

message(STATUS "Vulkan Found ${VULKAN_INCLUDE_DIR}")
message(STATUS "Vulkan Found ${VULKAN_LIBRARY_DIR}")

include_directories(${VULKAN_INCLUDE_DIR})

set(CMAKE_CXX_STANDARD 17)

file(GLOB_RECURSE HDR_FILES "${CMAKE_CURRENT_SOURCE_DIR}/*.h")
file(GLOB_RECURSE SRC_FILES "${CMAKE_CURRENT_SOURCE_DIR}/*.cc")

set(target_name VkLayer_printer)
add_library(${target_name} SHARED ${HDR_FILES}
                                  ${SRC_FILES}
)
