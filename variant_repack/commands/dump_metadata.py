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


def _dump_metadata(
    input_filepath: pathlib.Path,
) -> None:
    # Input Validation
    if not input_filepath.is_file():
        raise FileNotFoundError(f"Input Wheel File `{input_filepath}` does not exists.")

    # Input Validation - Wheel Filename is valid and non variant already.
    wheel_info = VALIDATION_WHEEL_NAME_REGEX.fullmatch(input_filepath.name)
    if wheel_info is None:
        raise ValueError(f"{input_filepath.name!r} is not a valid wheel filename.")

    with zipfile.ZipFile(input_filepath, "r") as input_zip:
        for filename in input_zip.namelist():
            components = filename.split("/", 2)
            if (
                len(components) == 2
                and components[0].endswith(".dist-info")
                and components[1] == "METADATA"
            ):
                with input_zip.open(filename, "r") as input_file:
                    sys.stdout.write(input_file.read().decode("utf-8"))


def dump_metadata(args: list[str]) -> None:
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

    parsed_args = parser.parse_args(args)

    input_filepath: pathlib.Path = parsed_args.input_filepath

    _dump_metadata(input_filepath=input_filepath)
