"""Regression test for core/utils.py write_image_sidecar's failure path.

Review finding I1 (2026-08-29 sprite-video-route final review): the except
clause named ``json.JSONEncodeError``, which does not exist in the standard
library, so a sidecar-write failure raised an unclassified ``AttributeError``
instead of the documented "never abort the caller" silent behaviour. Fixed to
catch ``(TypeError, ValueError, OSError)`` and log a warning.
"""
import json
import logging

import pytest

from core.utils import write_image_sidecar


def test_write_image_sidecar_swallows_write_failure_and_logs_warning(tmp_path, monkeypatch, caplog):
    image_path = tmp_path / "sprite.png"
    image_path.write_bytes(b"fake-png")

    def _boom(*args, **kwargs):
        raise TypeError("disk full")

    monkeypatch.setattr(json, "dumps", _boom)

    with caplog.at_level(logging.WARNING, logger="core.utils"):
        result = write_image_sidecar(image_path, {"prompt": "a hero"})

    assert result is None  # never raises, documented contract
    assert not (tmp_path / "sprite.png.json").exists()
    assert any("sprite.png" in rec.message and "disk full" in rec.message
              for rec in caplog.records)


def test_write_image_sidecar_swallows_os_error_and_logs_warning(tmp_path, monkeypatch, caplog):
    image_path = tmp_path / "sprite.png"
    image_path.write_bytes(b"fake-png")

    def _boom(*args, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr("pathlib.Path.write_text", _boom)

    with caplog.at_level(logging.WARNING, logger="core.utils"):
        result = write_image_sidecar(image_path, {"prompt": "a hero"})

    assert result is None
    assert any("permission denied" in rec.message for rec in caplog.records)


def test_write_image_sidecar_succeeds_on_the_happy_path(tmp_path):
    image_path = tmp_path / "sprite.png"
    image_path.write_bytes(b"fake-png")
    write_image_sidecar(image_path, {"prompt": "a hero"})
    sidecar = tmp_path / "sprite.png.json"
    assert sidecar.exists()
    assert json.loads(sidecar.read_text(encoding="utf-8"))["prompt"] == "a hero"
