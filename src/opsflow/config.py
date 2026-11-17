"""Paths and constants shared by every pipeline step."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "outputs"
TABLES = OUT / "tables"
FIGS = OUT / "figures"
EXCEL = OUT / "excel"
AUDIT = OUT / "audit" / "audit.json"
DB = OUT / "opsflow.duckdb"
POWERBI = ROOT / "powerbi"

PRODUCTION_ZIP = RAW / "4tu_production_data.zip"
PRODUCTION_ZIP_MD5 = "46174bf470258f9895dd153c78bc8b61"  # published on the 4TU.ResearchData landing page
PRODUCTION_CSV_IN_ZIP = "Production_Data.csv"
RASFF_CSV = RAW / "rasff_meat_poultry_notifications.csv"
FSAI_CSV = RAW / "fsai_allergen_alerts_listing.csv"

for p in (TABLES, FIGS, EXCEL, AUDIT.parent, POWERBI):
    p.mkdir(parents=True, exist_ok=True)

# Palette (one blue family + one accent, consistent across figures)
BLUE = "#1F5FA6"
LIGHT = "#9DB9DA"
ACCENT = "#D9822B"
GREY = "#8A8F98"
