"""Data contracts on the silver and gold layers."""


def test_silver_columns(con):
    cols = {r[0] for r in con.execute("DESCRIBE silver_production").fetchall()}
    assert {"case_id", "activity", "stage", "resource", "worker_id", "part", "report_type",
            "start", "complete", "duration_min", "qty_completed", "qty_rejected"} <= cols


def test_no_negative_or_null_times(con):
    assert con.execute("SELECT COUNT(*) FROM silver_production WHERE start IS NULL OR complete IS NULL OR duration_min < 0").fetchone()[0] == 0


def test_quarantine_has_reasons(con):
    assert con.execute("SELECT COUNT(*) FROM quarantine_production WHERE reasons IS NULL OR reasons = ''").fetchone()[0] == 0


def test_row_balance(con, audit):
    b = con.execute("SELECT COUNT(*) FROM bronze_production").fetchone()[0]
    s = con.execute("SELECT COUNT(*) FROM silver_production").fetchone()[0]
    q = con.execute("SELECT COUNT(*) FROM quarantine_production").fetchone()[0]
    assert b == s + q == audit["production_dq"]["bronze_rows"]


def test_every_activity_has_a_stage(con):
    assert con.execute("SELECT COUNT(*) FROM silver_production WHERE stage = 'Other'").fetchone()[0] == 0


def test_rasff_categories_and_dates(con):
    assert con.execute("SELECT COUNT(DISTINCT meat_group) FROM silver_rasff").fetchone()[0] == 2
    assert con.execute("SELECT COUNT(*) FROM silver_rasff WHERE notified_at IS NULL").fetchone()[0] == 0
