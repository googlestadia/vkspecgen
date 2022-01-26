#!/bin/bash

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

registry_file=$1
if [[ -z "${registry_file}" ]]; then
  registry_file="vk.xml"
fi

if [[ ! -f "${registry_file}" ]]; then
  echo "Error: Registry file ${registry_file} does not exist!"
  exit 1
fi
registry_file=$(realpath "${registry_file}")

# Current script directory
script_dir=$( cd ${0%/*} && pwd -P )

pushd ${script_dir} > /dev/null

had_failures=false

python3 tests/test_registry.py "${registry_file}" || had_failures=true
python3 tests/test_handle_info.py "${registry_file}" || had_failures=true

popd > /dev/null

if [[ "$had_failures" = true ]]; then
  echo "Tests failed!"
  exit 1
else
  echo "All tests pass"
  exit 0
fi
