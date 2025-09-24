from __future__ import annotations

import argparse
import dataclasses
import hashlib
import logging
import pathlib
from functools import cached_property

import jinja2

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def sha256sum(path: pathlib.Path, chunk_size: int = 8192) -> str:
    """Compute the SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclasses.dataclass(frozen=True)
class Artifact:
    fp: pathlib.Path

    @cached_property
    def checksum(self):
        return sha256sum(self.fp)


def create_index(args: list[str]) -> None:
    parser = argparse.ArgumentParser(
        prog="variant-repack",
        description="Generate a variant project index page.",
    )

    parser.add_argument(
        "-d",
        "--directory",
        type=pathlib.Path,
        required=True,
        help="Wheel file directory to process",
    )

    parsed_args = parser.parse_args(args)

    project_dir: pathlib.Path = parsed_args.directory

    logger.info("Processing `%s` ...", project_dir.name)
    assert project_dir.exists()

    # Load template
    jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(pathlib.Path(__file__).parent / "templates"),
        autoescape=True,
    )
    template = jinja_env.get_template("index.j2")

    variant_json_files = sorted(
        [Artifact(f) for f in project_dir.glob("*.json")],
        key=lambda f: f.fp.name,
    )

    wheel_files = sorted(
        [Artifact(f) for f in project_dir.glob("*.whl")],
        key=lambda f: f.fp.name,
    )

    output = template.render(
        project_name=project_dir.name,
        variants_json_files=variant_json_files,
        wheel_variant_files=wheel_files,
    )

    with (project_dir / "index.html").open(mode="w") as f:
        f.write(output)
