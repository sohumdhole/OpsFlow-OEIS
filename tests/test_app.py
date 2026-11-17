"""Smoke test: the dashboard renders every tab without errors."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_app_runs():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=120).run()
    assert not at.exception
    assert len(at.tabs) == 7
