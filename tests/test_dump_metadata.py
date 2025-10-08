from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING

from variant_repack.commands.dump_metadata import _dump_metadata

if TYPE_CHECKING:
    import pathlib


def make_wheel_with_metadata(tmp_path: pathlib.Path, name: str) -> pathlib.Path:
    whl = tmp_path / name
    with zipfile.ZipFile(whl, "w") as zf:
        zf.writestr(
            "pkg-1.0.0.dist-info/METADATA",
            """Name: pkg\nRequires-Dist: a\nRequires-Dist: b\n""",
        )
    return whl


def test_dump_metadata_validations_and_only_deps(
    tmp_path: pathlib.Path, capsys
) -> None:
    # invalid filename
    bad = tmp_path / "bad.whl"
    bad.write_bytes(b"x")
    try:
        _dump_metadata(bad)
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("Expected ValueError for invalid wheel filename")

    # valid minimal wheel
    whl = make_wheel_with_metadata(tmp_path, "pkg-1.0.0-py3-none-any.whl")
    _dump_metadata(whl, only_dependencies=True)
    out = capsys.readouterr().out
    assert out.strip().splitlines() == [
        "Requires-Dist: a",
        "Requires-Dist: b",
    ]
