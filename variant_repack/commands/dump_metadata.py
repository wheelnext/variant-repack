from __future__ import annotations

import argparse
import logging
import pathlib
import sys
import zipfile

from variantlib import __package_name__
from variantlib.constants import VALIDATION_WHEEL_NAME_REGEX

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _dump_metadata(whl_file: pathlib.Path, only_dependencies: bool = False) -> None:
    # Input Validation
    if not whl_file.is_file():
        raise FileNotFoundError(f"Input Wheel File `{whl_file}` does not exists.")

    # Input Validation - Wheel Filename is valid and non variant already.
    wheel_info = VALIDATION_WHEEL_NAME_REGEX.fullmatch(whl_file.name)
    if wheel_info is None:
        raise ValueError(f"{whl_file.name!r} is not a valid wheel filename.")

    with zipfile.ZipFile(whl_file, "r") as input_zip:
        for filename in input_zip.namelist():
            components = filename.split("/", 2)
            if (
                len(components) == 2
                and components[0].endswith(".dist-info")
                and components[1] == "METADATA"
            ):
                with input_zip.open(filename, "r") as input_file:
                    if not only_dependencies:
                        sys.stdout.write(input_file.read().decode("utf-8"))
                    else:
                        sys.stdout.write(
                            "".join(
                                line
                                for line in input_file.read()
                                .decode("utf-8")
                                .splitlines(keepends=True)
                                if line.startswith("Requires-Dist:")
                            )
                        )


def dump_metadata(args: list[str]) -> None:
    parser = argparse.ArgumentParser(
        prog=f"{__package_name__} make-variant",
        description="Transform a normal Wheel into a Wheel Variant.",
    )

    parser.add_argument(
        "--only-deps",
        default=False,
        action="store_true",
        help="Only display metadata dependencies",
    )

    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument(
        "-f",
        "--file",
        type=pathlib.Path,
        default=None,
        help="Wheel file to process",
    )

    group.add_argument(
        "-d",
        "--directory",
        type=pathlib.Path,
        help="Wheel file directory to process",
    )

    parsed_args = parser.parse_args(args)

    if whl_f := parsed_args.file:
        _dump_metadata(whl_file=whl_f, only_dependencies=parsed_args.only_deps)

    else:
        for whl_f in sorted(parsed_args.directory.glob("*.whl"), key=lambda f: f.name):
            sys.stdout.write(f"\n# {whl_f.name}\n")
            _dump_metadata(whl_file=whl_f, only_dependencies=parsed_args.only_deps)
