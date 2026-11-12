from lab.runner import attach_capture_evidence, capture_evidence
import pytest

from lab.captures import write_screenshot
from tests_browser.scenarios import _wait_for_csrf_effect


def test_capture_metadata_uses_explicit_filenames_and_rejects_unrelated_paths(tmp_path):
    (tmp_path / "before.png").write_bytes(b"before")
    (tmp_path / "after.png").write_bytes(b"after")
    captures = [
        {"filename": "after.png", "phase": "after", "label": "Después", "description": "Estado final"},
        {"filename": "../before.png", "phase": "before", "label": "Inválido", "description": "Fuera"},
        {"filename": "before.png", "phase": "before", "label": "Antes", "description": "Estado inicial"},
    ]
    result = capture_evidence(tmp_path, "run", captures)
    assert [item["phase"] for item in result] == ["after", "before"]
    assert result[0]["url"] == "/lab/artifacts/run/" + tmp_path.name + "/after.png"
    assert all("filename" not in item for item in result)
    # A PNG left behind by an interrupted worker is not declared evidence.
    (tmp_path / "partial.png").write_bytes(b"partial")
    assert capture_evidence(tmp_path, "run", []) == []
    assert all("partial.png" not in item["url"] for item in capture_evidence(tmp_path, "run", captures))


def test_undeclared_partial_capture_is_not_exposed_as_legacy_screenshot(tmp_path):
    (tmp_path / "after.png").write_bytes(b"partial")
    evidence = {"captures": [], "screenshots": ["after.png"]}
    attach_capture_evidence(evidence, tmp_path, "run")
    assert evidence["captures"] == []
    assert evidence["screenshots"] == []


def test_csrf_visual_timeout_is_not_accepted_as_evidence():
    class StalePage:
        def wait_for_function(self, expression, *, arg, timeout):
            assert arg == {"expected": 97500, "previous": "$ 1.000,00"}
            raise TimeoutError("La pantalla no se actualizó")

    with pytest.raises(TimeoutError):
        _wait_for_csrf_effect(StalePage(), 97500, "$ 1.000,00")


def test_failed_screenshot_or_publish_never_leaves_a_final_or_temporary_file(tmp_path, monkeypatch):
    class Page:
        def screenshot(self, **options):
            assert options["type"] == "png"
            return b"complete image"

    def fail_publish(*args):
        raise OSError("falló la publicación")

    monkeypatch.setattr("lab.captures.os.replace", fail_publish)
    with pytest.raises(OSError):
        write_screenshot(Page(), tmp_path, "after.png")
    assert list(tmp_path.iterdir()) == []

    class FailedPage:
        def screenshot(self, **options):
            raise RuntimeError("falló la captura")

    with pytest.raises(RuntimeError):
        write_screenshot(FailedPage(), tmp_path, "after.png")
    assert list(tmp_path.iterdir()) == []
