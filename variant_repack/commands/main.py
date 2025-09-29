# #!/usr/bin/env python3

from __future__ import annotations

import argparse
import logging
from importlib.metadata import entry_points

import variant_repack
from variant_repack import __package_name__


def main() -> None:
    logger = logging.getLogger(__package_name__)
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    registered_commands = entry_points(group=f"{__package_name__}.actions")

    parser = argparse.ArgumentParser(prog=__package_name__)
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s version: {variant_repack.__version__}",
    )
    parser.add_argument(
        "command",
        choices=sorted(registered_commands.names),
    )
    parser.add_argument(
        "args",
        help=argparse.SUPPRESS,
        nargs=argparse.REMAINDER,
    )

    namespace = argparse.Namespace()
    parser.parse_args(namespace=namespace)

    main_fn = registered_commands[namespace.command].load()
    return main_fn(namespace.args)
