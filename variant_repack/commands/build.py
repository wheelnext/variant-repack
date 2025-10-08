from __future__ import annotations

import argparse
import email.parser
import email.policy
import logging
import pathlib
import pprint
import re
import shutil
import tempfile
import tomllib
from functools import lru_cache
from typing import TYPE_CHECKING

from frozendict import frozendict
from variantlib import __package_name__
from variantlib.api import VariantDescription
from variantlib.api import VariantProperty
from variantlib.api import make_variant_dist_info
from variantlib.constants import VALIDATION_VARIANT_LABEL_REGEX
from variantlib.constants import VALIDATION_WHEEL_NAME_REGEX
from variantlib.constants import VARIANT_DIST_INFO_FILENAME
from variantlib.constants import VARIANT_LABEL_LENGTH
from variantlib.pyproject_toml import VariantPyProjectToml
from wheel.cli.pack import pack as wheel_pack
from wheel.cli.unpack import unpack as wheel_unpack

if TYPE_CHECKING:
    from email.message import Message
    from typing import Any

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

METADATA_POLICY = email.policy.EmailPolicy(
    utf8=True,
    mangle_from_=False,
    refold_source="none",
)


def format_dict(
    input_dict: dict[str, Any], prefix: str = "\t", postfix: str = ""
) -> str:
    rslt_str = ""
    for key, _val in sorted(input_dict.items()):
        val = f"{_val:.1f}" if isinstance(_val, float) else _val
        tmp_str = f"{prefix}- {key}: {val}{postfix}"
        rslt_str += f"{tmp_str}\n"

    return rslt_str.rstrip()


def sanitize_wheel_filename(filename: str) -> str:
    parts = filename.split("-")
    if len(parts) < 2:
        raise ValueError(f"Invalid wheel filename: {filename}")

    # Remove +<build_tag> from the version part (index 1)
    parts[1] = re.sub(r"\+[a-zA-Z0-9_\.]+", "", parts[1])

    return "-".join(parts)


def rename_package(
    metadata_f: pathlib.Path, metadata: Message[str, str], new_pkg_name: str
) -> pathlib.Path:
    # Rename the package name in the metadata
    old_pkg_name = metadata["Name"]
    logger.debug(f"Renaming package directory: {old_pkg_name} -> {new_pkg_name}")

    metadata.replace_header("Name", new_pkg_name)

    # Rename the .dist-info directory name
    dist_info_dir = metadata_f.parent

    _, pkg_version = dist_info_dir.name.split("-", maxsplit=1)

    new_dist_info_dir = dist_info_dir.with_name(
        f"{new_pkg_name.replace('-', '_')}-{pkg_version}"
    )
    dist_info_dir.rename(new_dist_info_dir)

    metadata_f = new_dist_info_dir / metadata_f.name

    logger.debug(f"Renamed dist-info directory: {dist_info_dir} -> {new_dist_info_dir}")

    return new_dist_info_dir


@lru_cache
def read_configuration(
    config_toml_filepath: pathlib.Path,
    metadata_config_name: str | None,
    variant_config_name: str | None,
) -> tuple[frozendict[str, Any], frozendict[str, Any]]:
    with config_toml_filepath.open("rb") as f:
        config = tomllib.load(f)

    # ===================== Dependency Config ===================== #
    base_metadata_config = config.get("metadata_configs", {})
    if metadata_config_name is not None:
        try:
            metadata_config = base_metadata_config[metadata_config_name]
            logger.debug(
                f"Found metadata config '{metadata_config_name}' in "
                f"{config_toml_filepath}"
            )
        except KeyError as e:
            raise KeyError(
                f"Config '{metadata_config_name}' not found in `metadata_configs`. "
                f"Available configs: {base_metadata_config.keys()}"
            ) from e

    else:
        metadata_config = {}

    # ====================== Variant Config ======================= #
    base_variant_configs = config.get("variant_configs", {})
    if variant_config_name is not None:
        try:
            variant_config = base_variant_configs[variant_config_name]
            logger.debug(
                f"Found variant config '{variant_config_name}' in "
                f"{config_toml_filepath}"
            )
        except KeyError as e:
            raise KeyError(
                f"Config '{variant_config_name}' not found in `variant_configs`. "
                f"Available configs: {base_variant_configs.keys()}"
            ) from e

    else:
        variant_config = {}

    logger.debug("Metadata Config:")
    logger.debug(pprint.pformat(metadata_config, indent=4, width=80))
    logger.debug("Variant Config:")
    logger.debug(pprint.pformat(variant_config, indent=4, width=80))

    return frozendict(metadata_config), frozendict(variant_config)


def replace_from_end(s: str, old: str, new: str) -> str:
    """
    Replace `old` with `new` only if `s` ends with `old`.
    """
    if s.endswith(old):
        return s[: -len(old)] + new if old else s + new
    return s


def repack_variant(
    metadata_config_name: str | None,
    variant_config_name: str | None,
    config_toml_filepath: pathlib.Path,
    metadata_f: pathlib.Path,
) -> None:
    # Input Validation
    if not metadata_f.exists() or not metadata_f.is_file():
        raise FileNotFoundError(f"METADATA file `{metadata_f}` does not exists.")

    if not config_toml_filepath.exists() or not config_toml_filepath.is_file():
        raise FileNotFoundError(
            f"Config TOML File `{config_toml_filepath}` does not exists."
        )

    # ========================= CHECKING CONFIG TOML FILE ========================= #

    # Load and verify the TOML configuration
    metadata_config, _ = read_configuration(
        config_toml_filepath,
        metadata_config_name,
        variant_config_name,
    )

    with metadata_f.open(mode="rb") as fp:
        # Parse the metadata
        metadata_parser = email.parser.BytesParser()
        metadata = metadata_parser.parse(fp)

    # =========================== RENAMING PACKAGE NAME =========================== #

    dist_info_dir: pathlib.Path

    if new_pkg_name := metadata_config.get("rename_package_to", False):
        dist_info_dir = rename_package(
            metadata_f=metadata_f, metadata=metadata, new_pkg_name=new_pkg_name
        )

    elif metadata_config.get("normalize_package_name", False):
        normalize_patterns = [
            # NVIDIA GPU
            "cu11",
            "cu12",
            "cu13",
            "cu118",
            "cu126",
            "cu128",
            "cu129",
            "cuda11x",
            "cuda12x",
            "cuda13x",
            # CPU pattern
            "cpu",
        ]

        package_name = metadata["Name"]

        for pattern in normalize_patterns:
            package_name = replace_from_end(package_name, f"-{pattern}", "")
            package_name = replace_from_end(package_name, f"_{pattern}", "")

        dist_info_dir = rename_package(
            metadata_f=metadata_f, metadata=metadata, new_pkg_name=package_name
        )

    else:
        dist_info_dir = metadata_f.parent

    # ========================= CHECKING CONFIG TOML FILE ========================= #

    if metadata_config.get("normalize_version", False):
        metadata.replace_header("Version", metadata["Version"].split("+")[0])

    input_dependencies: list[str] = metadata.get_all("Requires-Dist", [])
    output_dependencies: list[str] = []

    dependencies_to_remove = metadata_config.get("deps_remove_list", [])
    dependencies_to_add = metadata_config.get("deps_add_list", [])

    for dep in input_dependencies:
        if any(dep.startswith(d) for d in dependencies_to_remove):
            continue
        output_dependencies.append(dep)

    output_dependencies.extend(dependencies_to_add)
    output_dependencies = sorted(output_dependencies)

    logger.debug(f"Total dependencies entries: {len(output_dependencies)}")
    for i, dep in enumerate(output_dependencies):
        logger.debug(f"  [{i + 1:02d}] {dep}")

    del metadata["Requires-Dist"]
    for dep in output_dependencies:
        metadata["Requires-Dist"] = dep

    with (dist_info_dir / metadata_f.name).open(mode="wb") as fp:
        fp.write(metadata.as_bytes(policy=METADATA_POLICY))


def make_variant(
    # Make Variant Parameters
    input_filepath: pathlib.Path,
    output_directory: pathlib.Path,
    variant_info: VariantPyProjectToml,
    # Variant Pack Parameters
    metadata_config_name: str | None,
    variant_config_name: str | None,
    config_toml_filepath: pathlib.Path,
) -> None:
    # Input Validation
    if not input_filepath.is_file():
        raise FileNotFoundError(f"Input Wheel File `{input_filepath}` does not exists.")

    # Input Validation - Wheel Filename is valid and non variant already.
    wheel_info = VALIDATION_WHEEL_NAME_REGEX.fullmatch(input_filepath.name)
    if wheel_info is None:
        raise ValueError(f"{input_filepath.name!r} is not a valid wheel filename.")

    if not output_directory.is_dir():
        raise FileNotFoundError(
            f"Output Directory `{output_directory}` does not exists."
        )

    # Load and verify the TOML configuration
    _, variant_config = read_configuration(
        config_toml_filepath,
        metadata_config_name,
        variant_config_name,
    )

    # Extract relevant information - 1. Variant Label
    variant_label = variant_config.get("variant_label", None)

    # Extract relevant information - 2. Variant Properties
    properties = [
        VariantProperty(**vprop) for vprop in variant_config.get("properties", [])
    ]

    vdesc = (
        VariantDescription(properties=properties)
        if properties
        else VariantDescription()
    )

    if variant_label is None:
        variant_label = vdesc.hexdigest

    if not VALIDATION_VARIANT_LABEL_REGEX.fullmatch(variant_label):
        raise ValueError(
            f"invalid variant label (must be up to {VARIANT_LABEL_LENGTH} alphanumeric "
            f"characters): {variant_label!r}"
        )

    # ============================================== #

    with tempfile.TemporaryDirectory() as _tmpdir:
        tmpdir = pathlib.Path(_tmpdir)
        # tmpdir = Path("tmp_folder")
        wheel_unpack(str(input_filepath), _tmpdir)

        unpacked_dir = next(tmpdir.iterdir())
        assert unpacked_dir.is_dir()

        distinfo_dir = None
        for _dir in unpacked_dir.iterdir():
            if _dir.is_dir() and _dir.name.endswith(".dist-info"):
                distinfo_dir = _dir
                break
        else:
            raise FileNotFoundError("No *.dist-info directory found in unpacked wheel")

        # Remove version suffix patterns like +cu126, +cpu, etc. from dist-info
        # directory name
        new_dir_name = re.sub(r"\+[a-zA-Z0-9_\.]+\.", ".", distinfo_dir.name)
        if new_dir_name != distinfo_dir.name:
            new_distinfo_dir = distinfo_dir.parent / new_dir_name
            distinfo_dir.rename(new_distinfo_dir)
            logger.debug(
                f"Renamed dist-info directory from {distinfo_dir.name} to "
                f"{new_dir_name}"
            )
            distinfo_dir = new_distinfo_dir

        # 1. Generate the `variants.json` file
        with (distinfo_dir / VARIANT_DIST_INFO_FILENAME).open(mode="wb") as fp:
            dist_info_data = make_variant_dist_info(
                vdesc, variant_info=variant_info, variant_label=variant_label
            )
            fp.write(dist_info_data.encode("utf-8"))

        # 2. Edit the METADATA file
        repack_variant(
            metadata_config_name=metadata_config_name,
            variant_config_name=variant_config_name,
            config_toml_filepath=config_toml_filepath,
            metadata_f=distinfo_dir / "METADATA",
        )

        # 3. Repacking the wheel
        wheel_pack(str(unpacked_dir), _tmpdir, None)
        tmp_whl_filepath = next(tmpdir.glob("*.whl"))

        output_wheel_info = VALIDATION_WHEEL_NAME_REGEX.fullmatch(tmp_whl_filepath.name)
        if output_wheel_info is None:
            raise ValueError(
                f"{tmp_whl_filepath.name!r} is not a valid wheel filename."
            )

        # Determine output wheel filename
        output_filepath = (
            output_directory
            / f"{output_wheel_info.group('base_wheel_name')}-{variant_label}.whl"
        )

        output_filepath = output_directory / sanitize_wheel_filename(
            f"{output_wheel_info.group('base_wheel_name')}-{variant_label}.whl"
        )
        shutil.move(tmp_whl_filepath, output_filepath)

    logger.info("Variant Wheel Created: `%s`", output_filepath.resolve())


def build(args: list[str]) -> None:
    parser = argparse.ArgumentParser(
        prog=f"{__package_name__} make-variant",
        description="Transform a normal Wheel into a Wheel Variant.",
    )

    parser.add_argument(
        "-i",
        "--input_file",
        dest="input_filepath",
        type=pathlib.Path,
        required=True,
        help="Wheel file to process",
    )

    parser.add_argument(
        "-o",
        "--output-directory",
        type=pathlib.Path,
        required=True,
        help="Output Directory to use to store the Wheel Variant",
    )

    parser.add_argument(
        "--pyproject-toml",
        type=pathlib.Path,
        default="./pyproject.toml",
        help=(
            "pyproject.toml to read variant variant info from (default: "
            "./pyproject.toml)"
        ),
    )

    parser.add_argument(
        "--variant-config-toml",
        type=pathlib.Path,
        help="TOML file to configure this script",
    )

    parser.add_argument(
        "--metadata-config-name",
        default=None,
        type=str,
        help="Metadata config name to be used from the `--variant-config-toml` file",
    )

    parser.add_argument(
        "--variant-config-name",
        type=str,
        help="Variant config name to be used from the `--variant-config-toml` file",
    )

    parser.add_argument(
        "--debug",
        default=False,
        action="store_true",
        help="Enable debug logging",
    )

    parsed_args = parser.parse_args(args)

    if parsed_args.debug:
        logger.setLevel(logging.DEBUG)

    logger.debug("\n==================== Parsed Arguments ====================")
    logger.debug(format_dict(vars(parsed_args)))
    logger.debug("==========================================================\n")

    try:
        pyproject_toml = VariantPyProjectToml.from_path(parsed_args.pyproject_toml)
    except FileNotFoundError:
        parser.error(f"{str(parsed_args.pyproject_toml)!r} does not exist")

    input_filepath: pathlib.Path = parsed_args.input_filepath
    output_directory: pathlib.Path = parsed_args.output_directory

    variant_config_toml: pathlib.Path = parsed_args.variant_config_toml
    metadata_config_name: str | None = parsed_args.metadata_config_name
    variant_config_name: str | None = parsed_args.variant_config_name

    make_variant(
        # Make Variant Parameters
        input_filepath=input_filepath,
        output_directory=output_directory,
        variant_info=pyproject_toml,
        # Variant Repack Parameters
        metadata_config_name=metadata_config_name,
        variant_config_name=variant_config_name,
        config_toml_filepath=variant_config_toml,
    )
