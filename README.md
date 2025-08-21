# variant-repack

<p align="center">
  <em>A tool for transforming standard Python wheels into Wheel Variants compliant with the proposed PEP standard</em>
</p>

---

## 📖 Table of Contents

- [variant-repack](#variant-repack)
  - [📖 Table of Contents](#-table-of-contents)
  - [Overview](#overview)
  - [Why variant-repack?](#why-variant-repack)
  - [Features](#features)
  - [Installation](#installation)
  - [Quick Start](#quick-start)
  - [Configuration](#configuration)
    - [PyProject TOML](#pyproject-toml)
    - [Variant Configuration TOML](#variant-configuration-toml)
  - [Usage](#usage)
    - [Command Line Interface](#command-line-interface)
  - [Architecture](#architecture)
  - [Contributing](#contributing)
    - [Development Setup](#development-setup)
  - [License](#license)

---

## Overview

`variant-repack` is a wheel transformation tool that modifies existing Python wheels to conform to the [Wheel Variant specification](https://wheelnext.dev/proposals/pepxxx_wheel_variant_support/). Similar to how `auditwheel` repairs wheels for compatibility with different Linux platforms, `variant-repack` transforms wheels to support hardware-specific variants, enabling optimized package distribution for diverse computing environments.

The tool addresses the needs of packages that require platform-specific optimizations, such as:
- GPU-accelerated libraries with different CUDA versions
- CPU-optimized packages with specific instruction set support
- Hardware-specific implementations (FPGA, ASIC, TPU)
- Architecture-specific builds (ARM, x86, RISC-V)

## Why variant-repack?

Modern Python packages increasingly require hardware-specific optimizations, particularly in domains like:
- **Machine Learning**: Different builds for various GPU architectures (CUDA versions, ROCm, etc.)
- **High-Performance Computing**: CPU-specific optimizations (AVX, AVX512, etc.)
- **Embedded Systems**: Platform-specific implementations

Current approaches have significant limitations:
- **Multiple Package Names** (`package-gpu`, `package-cpu`): Creates dependency resolution nightmares
- **Mega-wheels**: Bundle all variants, resulting in massive downloads
- **Separate Indexes**: Forces users to manually configure package sources

The Wheel Variant specification provides a standardized solution, and `variant-repack` enables package maintainers to adopt this standard by transforming their existing wheels.

## Features

✨ **Wheel Transformation**
- Converts standard wheels into variant-compliant wheels
- Adds variant metadata and properties
- Generates deterministic variant labels

🔧 **Dependency Management**
- Modifies package dependencies based on variants
- Removes incompatible dependencies
- Adds variant-specific dependencies with proper markers

📦 **Package Normalization**
- Normalizes package names (removes build tags like `-cu126`)
- Normalizes version strings (removes local version identifiers)
- Cleans up metadata for variant compatibility

🏷️ **Flexible Configuration**
- TOML-based configuration for variants and metadata
- Support for multiple variant configurations
- Customizable variant properties and labels

## Installation

```bash
# Install from PyPI (when available)
pip install variant-repack

# Install from source
git clone https://github.com/wheelnext/variant-repack.git
cd variant-repack
pip install -e .

# Install with development dependencies
pip install -e ".[dev]"
```

## Quick Start

1. **Create a variant configuration file** (`config.toml`):

```toml
[metadata_configs.default]
normalize_package_name = true
normalize_version = true
deps_remove_list = ["old-dependency"]
deps_add_list = [
    'new-dependency>=1.0; "my_hw" in variant_namespaces'
]

[variant_configs.my_variant]
variant_label = "opt1"
properties = [
    { namespace = "my_hw", feature = "capability", value = "advanced" }
]
```

2. **Create a pyproject.toml with variant provider information**:

```toml
[variant.default-priorities]
namespace = ["my_hw"]

[variant.providers.my_hw]
requires = ["my-hw-provider>=1.0.0"]
plugin-api = "my_hw_provider.plugin:MyHWPlugin"
enable-if = "platform_system == 'Linux'"
```

3. **Transform your wheel**:

```bash
variant_repack build \
    -i my_package-1.0.0-py3-none-any.whl \
    -o output/ \
    --pyproject-toml pyproject.toml \
    --variant-config-toml config.toml \
    --variant-config-name my_variant \
    --metadata-config-name default
```

## Configuration

### PyProject TOML

The `pyproject.toml` file defines variant provider information using the `[variant]` table:

```toml
[variant.default-priorities]
# Define the priority order for variant namespaces
namespace = ["provider1", "provider2"]

[variant.providers.provider1]
# Python package requirement for the provider plugin
requires = ["provider1-package>=0.0.1,<1.0.0"]
# Entry point for the provider plugin
plugin-api = "provider1_package.plugin:CustomHardwareProvider"
# Condition for enabling this provider
enable-if = "platform_system == 'Linux' or platform_system == 'Windows'"

[variant.providers.provider2]
# Python package requirement for the provider plugin
requires = ["provider2-package>=0.0.1,<1.0.0"]
# Entry point for the provider plugin
plugin-api = "provider2_package.plugin:CustomLibraryProvider"
# Condition for enabling this provider
enable-if = "platform_system == 'Linux'
```

### Variant Configuration TOML

The variant configuration file defines metadata transformations and variant properties:

```toml
# Metadata configurations define how to modify wheel metadata
[metadata_configs.default]
# Normalize package name by removing build tags
normalize_package_name = true
# Normalize version by removing local version identifiers
normalize_version = true
# List of dependencies to remove
deps_remove_list = [
    "old-dependency",
    "legacy-runtime",
]
# List of dependencies to add with proper markers
deps_add_list = [
    'new-dependency==2.0; platform_system == "Linux" and "provider1" in variant_namespaces',
    'new-runtime==12.0; "provider2 :: feature :: value" in variant_properties',
]

# Additional metadata configurations
[metadata_configs.special]
normalize_package_name = false
deps_remove_list = ["specific-dependency"]

# Variant configurations define the properties for each variant
[variant_configs.cfg_name1]
# Optional: Specify a custom variant label (max 16 alphanumeric chars)
variant_label = "variant_label1"
# List of variant properties
properties = [
    { namespace = "provider1", feature = "version", value = "1.2.3" },
    { namespace = "provider1", feature = "arch", value = "newest" },
    { namespace = "provider1", feature = "arch", value = "recent" },
    { namespace = "provider1", feature = "arch", value = "not_so_recent" },
]

[variant_configs.cfg_name2]
# If no variant_label is specified, a hash will be generated
properties = [
    { namespace = "provider2", feature = "library", value = "4.5.6" },
    { namespace = "provider2", feature = "optimization", value = "ABC512" },
]

[variant_configs.cfg_default]
# Empty properties create a null variant (00000000)
properties = []
```

## Usage

### Command Line Interface

`variant-repack` provides a simple command-line interface:

```bash
# Basic usage
variant_repack build -i input.whl -o output_dir/ \
    --pyproject-toml pyproject.toml \
    --variant-config-toml config.toml \
    --variant-config-name my_variant

# With metadata configuration
variant_repack build -i input.whl -o output_dir/ \
    --pyproject-toml pyproject.toml \
    --variant-config-toml config.toml \
    --variant-config-name cfg_name1 \
    --metadata-config-name default

# Enable debug logging
variant_repack build -i input.whl -o output_dir/ \
    --pyproject-toml pyproject.toml \
    --variant-config-toml config.toml \
    --variant-config-name my_variant \
    --debug

# Show version
variant_repack --version
```

## Architecture

`variant-repack` follows a straightforward transformation pipeline:

1. **Unpacking**: Extracts the wheel contents to a temporary directory
2. **Metadata Modification**:
   - Normalizes package name and version if configured
   - Updates dependencies based on configuration
   - Modifies the METADATA file
3. **Variant Injection**:
   - Generates variant properties from configuration
   - Creates the `variants.json` file in the `.dist-info` directory
   - Calculates or uses the specified variant label
4. **Repacking**: Creates a new wheel with the variant label in the filename

The tool integrates with:
- **variantlib**: For variant property management and index generation
- **wheel**: For unpacking and packing wheel files
- **email.parser**: For parsing and modifying wheel metadata

## Contributing

We welcome contributions! We would love to work with you as part of WheelNext

### Development Setup

```bash
# Clone the repository
git clone https://github.com/wheelnext/variant-repack.git
cd variant-repack

# Install the development environmnent
uv sync

# Install pre-commit hooks
pre-commit install

# Run linter
pre-commit run --all
```

## License

This project is licensed under the Apache2 License - see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  Part of the <a href="https://wheelnext.dev">WheelNext Initiative</a> - ReInventing the Wheel.
</p>
