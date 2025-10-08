from __future__ import annotations

from typing import TYPE_CHECKING

from variant_repack.commands.build import format_dict
from variant_repack.commands.build import read_configuration
from variant_repack.commands.build import replace_from_end
from variant_repack.commands.build import sanitize_wheel_filename

if TYPE_CHECKING:
    import pathlib


def test_format_dict_and_replace_from_end(tmp_path: pathlib.Path) -> None:
    input_dict = {"b": 2, "a": 1.23, "c": "x"}
    formatted = format_dict(input_dict, prefix="", postfix=";")
    assert formatted.splitlines() == [
        "- a: 1.2;",
        "- b: 2;",
        "- c: x;",
    ]

    assert replace_from_end("hello_cpu", "_cpu", "") == "hello"
    assert replace_from_end("hello", "_cpu", "") == "hello"


def test_sanitize_wheel_filename() -> None:
    fname = "mypkg-1.0.0+cu126-py3-none-any.whl"
    assert sanitize_wheel_filename(fname) == "mypkg-1.0.0-py3-none-any.whl"

    try:
        sanitize_wheel_filename("badname.whl")
    except ValueError:
        pass
    else:  # pragma: no cover - guard
        raise AssertionError("Expected ValueError for invalid filename")


def test_read_configuration_success_and_missing(tmp_path: pathlib.Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        """
        [metadata_configs.default]
        normalize_package_name = true
        deps_remove_list = ["old"]
        deps_add_list = ["new"]

        [variant_configs.myv]
        variant_label = "v1"
        properties = [
          { namespace = "ns", feature = "feat", value = "val" }
        ]
        """
    )

    md, vc = read_configuration(cfg, "default", "myv")
    assert md["normalize_package_name"] is True
    assert vc["variant_label"] == "v1"

    try:
        read_configuration(cfg, "missing", None)
    except KeyError:
        pass
    else:  # pragma: no cover
        raise AssertionError("Expected KeyError for missing metadata config")

    try:
        read_configuration(cfg, None, "missing")
    except KeyError:
        pass
    else:  # pragma: no cover
        raise AssertionError("Expected KeyError for missing variant config")
