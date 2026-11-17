import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture(scope="session")
def audit():
    return json.loads((ROOT / "outputs" / "audit" / "audit.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def con():
    db = ROOT / "outputs" / "opsflow.duckdb"
    if not db.exists():
        pytest.skip("run `python run_pipeline.py` first (needs the 4TU archive in data/raw)")
    import duckdb
    c = duckdb.connect(str(db), read_only=True)
    yield c
    c.close()
