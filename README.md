## Overview

VkSpecGen is a toolkit for generating code from the Vulkan secification XML.
While VkSpecGen can be used by it's own, to generate flatbuffers schema for
example, it also supports Jinja2 template rendering enging.
Support for other or custom template rendering engines can be added and to
VkSpecGen conveniently.

Please note that VkSpecGen is not an officially supported Google product.

## Setup

1. Install Jinja2

    ``` pip install Jinja2 ```

2. Download [Vulkan API registry](https://raw.githubusercontent.com/KhronosGroup/Vulkan-Docs/main/xml/vk.xml)


3. Generate the C++ code with

    ``` python3 generator_script.py ```

## Examples

Multiple examples are provided in `examples` directory.
The code will be generated in the root folder. You need `python3` to run the examples.
You can pass the path to the Vulkan API registry file (`vk.xml`) using `-s` or `--spec`. If the path
is not provided, the generator scripts expect to find the registry file in the root directory of
the VkSpecGen.
You can pass the target platform for the layer using `-p` or `--platform`. The default platform is the core platform. For the list of valid Vulkan platforms please see `<platforms>` node in `vk.xml` file.

### Generate Flatbuffers Schema

`examples/flatbuffer/vkflat.py` generates flatbuffers schema for Vulkan types in C++.
The schema is printed to stdout. Note that this script is not accompanied with a
Jinja2 template and uses VkSpecGen to directly generate the output code.

### Generate Vulkan Layer to Print Vulkan Call Parameters

`examples/print_layer/vklayerpint.py` generates the code for a Vulkan layer
that intercepts all the Vulkan calls and prints the parameters to stdout.
The generator script uses multiple Jinja2 templates in `templates` directory
to generate the layer dispatch tables and the interceptors.

You can use `CMake` to build the layer from the example folder. However note that
for the build to be successful, you need to have the proper version of the
Vulkan headers installed. The headers should match the version of the `vk.xml`
that you used to generate the layer.

## Test

The tests currently require a real `vk.xml`, which makes them version-dependent.
The supported version is
[v1.2.202](https://github.com/KhronosGroup/Vulkan-Docs/releases/tag/v1.2.202).

Run tests with:
```
./run_tests.sh <path to vk.xml>
```

### Code formatting

This project uses `yapf` Python formatter. The settings for VSCode is as
follows:

```
"python.formatting.provider": "yapf",
"python.formatting.yapfArgs": [
  "--style",
  "{based_on_style: google, indent_width: 2}"
],
```

