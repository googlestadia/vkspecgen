## Overview

VkSpecGen is a toolkit for generating code from the Vulkan secification XML.

This is not an officially supported Google product.

## Examples

### vklayerprint.py

Generates the code for a Vulkan layer that will print all parameters to stdout.

## Setup

1. Install Jinja2

    ``` pip install Jinja2 ```

2. Download [vk.xml](https://raw.githubusercontent.com/KhronosGroup/Vulkan-Docs/main/xml/vk.xml) and put in the root folder


3. Generate the C++ code with

    ``` python examples/vklayerprint.py ```

    The code will be generated in the root folder. You need `python3` to run the code.
    You can pass the path to the `vk.xml` file using `-s` or `--spec`.
    You can pass the target platform for the layer using `-p` or `--platform`. The default platform is `win32`. For the list of valid Vulkan platforms see `<platforms>` node in `vk.xml` file.

4. Run Cmake and compile the code.

### VSCode

VSCode formatting:

```
"python.formatting.provider": "yapf",
"python.formatting.yapfArgs": [
  "--style",
  "{based_on_style: google, indent_width: 2}"
],
```

## Test

The tests currently require a real vk.xml, which makes them version-dependent.
The supported version is
[v1.2.202](https://github.com/KhronosGroup/Vulkan-Docs/releases/tag/v1.2.202).

Run tests with:
```
./run_tests.sh <path to vk.xml>
```
