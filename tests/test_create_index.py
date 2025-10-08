from __future__ import annotations

from typing import TYPE_CHECKING

from variant_repack.commands.create_index import create_index
from variant_repack.commands.create_index import sha256sum

if TYPE_CHECKING:
    import pathlib


def test_sha256sum_and_template_rendering(tmp_path: pathlib.Path) -> None:
    # Prepare artifacts
    json_file = tmp_path / "a-variant.json"
    whl_file = tmp_path / "mypkg-1.0.0-py3-none-any.whl"
    json_file.write_text("{}\n")
    whl_file.write_bytes(b"wheel-bytes")

    # Verify checksum helper
    checksum = sha256sum(whl_file)
    assert len(checksum) == 64
    assert checksum == sha256sum(whl_file)

    # Run command to generate index.html
    create_index(["-d", str(tmp_path)])

    index_fp = tmp_path / "index.html"
    content = index_fp.read_text()
    assert json_file.name in content
    assert whl_file.name in content
    # checksum included in links
    assert checksum in content
