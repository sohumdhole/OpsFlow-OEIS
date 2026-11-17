"""Documents are generated from the audit record and follow the writing rules."""
from pathlib import Path

from opsflow.step7_docs import methodology, readme

ROOT = Path(__file__).resolve().parents[1]


def test_readme_rendered_from_audit(audit):
    assert (ROOT / "README.md").read_text(encoding="utf-8") == readme(audit)


def test_methodology_rendered_from_audit(audit):
    assert (ROOT / "docs" / "methodology.md").read_text(encoding="utf-8") == methodology(audit)


def test_all_checks_passed(audit):
    assert audit["validation"]["passed"] == audit["validation"]["checks"]


def test_no_em_dashes_anywhere():
    files = [p for p in ROOT.rglob("*") if p.suffix in {".md", ".py", ".dax"} and ".git" not in p.parts]
    bad = [str(p.relative_to(ROOT)) for p in files if chr(0x2014) in p.read_text(encoding="utf-8")]
    assert not bad, bad


def test_raw_production_data_not_tracked():
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "data/raw/4tu_production_data.zip" in ignore
    assert "outputs/opsflow.duckdb" in ignore
