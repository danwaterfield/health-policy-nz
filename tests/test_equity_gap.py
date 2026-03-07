"""Tests for the equity gap calculation."""
import pytest
import duckdb
from pipeline.transform.equity_gap import EquityGapTransformer


def _insert_indicator(conn, ind_id, slug, direction):
    conn.execute("""
        INSERT OR IGNORE INTO dim_indicator (id, name, slug, category, direction, unit)
        VALUES (?, ?, ?, 'outcomes', ?, '%')
    """, (ind_id, slug, slug, direction))


def _insert_time(conn, time_id, year):
    conn.execute("""
        INSERT OR IGNORE INTO dim_time (id, year, period_label, period_type)
        VALUES (?, ?, ?, 'annual')
    """, (time_id, year, str(year)))


def _insert_fact(conn, indicator_id, geography_id, ethnicity_id, time_id,
                  value, suppressed=False, sample_size=100):
    conn.execute("""
        INSERT INTO fact_health_indicator
        (id, indicator_id, geography_id, ethnicity_id, time_id, data_source_id,
         value, suppressed, sample_size)
        VALUES (nextval('fact_health_indicator_id_seq'), ?, ?, ?, ?, 1, ?, ?, ?)
    """, (indicator_id, geography_id, ethnicity_id, time_id, value, suppressed, sample_size))


def test_adverse_gap_higher_better(conn):
    """For higher_better indicator, target < reference = adverse."""
    _insert_indicator(conn, 100, "test_higher", "higher_better")
    _insert_time(conn, 100, 2023)

    # Reference: European/Other (id=5), national (id=1)
    _insert_fact(conn, 100, 1, 5, 100, value=80.0)
    # Target: Maori (id=2), national (id=1)
    _insert_fact(conn, 100, 1, 2, 100, value=60.0)

    EquityGapTransformer().transform(conn)

    row = conn.execute("""
        SELECT gap_direction, absolute_gap FROM equity_gap
        WHERE target_ethnicity_id = 2 AND indicator_id = 100
    """).fetchone()

    assert row is not None
    assert row[0] == "adverse"
    assert abs(row[1] - (-20.0)) < 0.001


def test_adverse_gap_lower_better(conn):
    """For lower_better indicator, target > reference = adverse."""
    _insert_indicator(conn, 101, "test_lower", "lower_better")
    _insert_time(conn, 101, 2023)

    # Reference: European/Other, national
    _insert_fact(conn, 101, 1, 5, 101, value=10.0)
    # Target: Maori
    _insert_fact(conn, 101, 1, 2, 101, value=25.0)

    EquityGapTransformer().transform(conn)

    row = conn.execute("""
        SELECT gap_direction, absolute_gap FROM equity_gap
        WHERE target_ethnicity_id = 2 AND indicator_id = 101
    """).fetchone()

    assert row is not None
    assert row[0] == "adverse"
    assert abs(row[1] - 15.0) < 0.001


def test_favourable_gap(conn):
    """Target better than reference = favourable."""
    _insert_indicator(conn, 102, "test_fav", "higher_better")
    _insert_time(conn, 102, 2023)

    _insert_fact(conn, 102, 1, 5, 102, value=70.0)
    _insert_fact(conn, 102, 1, 2, 102, value=85.0)

    EquityGapTransformer().transform(conn)

    row = conn.execute("""
        SELECT gap_direction FROM equity_gap WHERE indicator_id = 102
    """).fetchone()

    assert row is not None
    assert row[0] == "favourable"


def test_no_gap_when_reference_suppressed(conn):
    """No equity gap should be computed when reference value is suppressed."""
    _insert_indicator(conn, 103, "test_suppressed_ref", "higher_better")
    _insert_time(conn, 103, 2023)

    # Reference suppressed
    _insert_fact(conn, 103, 1, 5, 103, value=None, suppressed=True)
    _insert_fact(conn, 103, 1, 2, 103, value=60.0, suppressed=False)

    EquityGapTransformer().transform(conn)

    count = conn.execute(
        "SELECT COUNT(*) FROM equity_gap WHERE indicator_id = 103"
    ).fetchone()[0]
    assert count == 0


def test_no_gap_when_target_suppressed(conn):
    """No equity gap when target value is suppressed."""
    _insert_indicator(conn, 104, "test_suppressed_target", "higher_better")
    _insert_time(conn, 104, 2023)

    _insert_fact(conn, 104, 1, 5, 104, value=80.0, suppressed=False)
    _insert_fact(conn, 104, 1, 2, 104, value=None, suppressed=True)

    EquityGapTransformer().transform(conn)

    count = conn.execute(
        "SELECT COUNT(*) FROM equity_gap WHERE indicator_id = 104"
    ).fetchone()[0]
    assert count == 0


def test_no_gap_when_sample_size_too_small(conn):
    """No gap when target sample_size < 30."""
    _insert_indicator(conn, 105, "test_small_n", "higher_better")
    _insert_time(conn, 105, 2023)

    _insert_fact(conn, 105, 1, 5, 105, value=80.0, sample_size=500)
    _insert_fact(conn, 105, 1, 2, 105, value=60.0, sample_size=15)  # < 30

    EquityGapTransformer().transform(conn)

    count = conn.execute(
        "SELECT COUNT(*) FROM equity_gap WHERE indicator_id = 105"
    ).fetchone()[0]
    assert count == 0


def test_maori_is_indigenous(conn):
    """The target ethnicity for Maori gaps should have is_indigenous=TRUE."""
    _insert_indicator(conn, 106, "test_indigenous", "higher_better")
    _insert_time(conn, 106, 2023)

    _insert_fact(conn, 106, 1, 5, 106, value=80.0)
    _insert_fact(conn, 106, 1, 2, 106, value=60.0)

    EquityGapTransformer().transform(conn)

    is_indigenous = conn.execute("""
        SELECT e.is_indigenous
        FROM equity_gap eg
        JOIN dim_ethnicity e ON eg.target_ethnicity_id = e.id
        WHERE eg.indicator_id = 106
    """).fetchone()

    assert is_indigenous is not None
    assert is_indigenous[0] is True


def test_equity_gap_idempotent(conn):
    """Running equity gap twice should give same count (DELETE + recompute)."""
    _insert_indicator(conn, 107, "test_idem", "higher_better")
    _insert_time(conn, 107, 2023)
    _insert_fact(conn, 107, 1, 5, 107, value=80.0)
    _insert_fact(conn, 107, 1, 2, 107, value=60.0)

    EquityGapTransformer().transform(conn)
    count1 = conn.execute("SELECT COUNT(*) FROM equity_gap WHERE indicator_id = 107").fetchone()[0]

    EquityGapTransformer().transform(conn)
    count2 = conn.execute("SELECT COUNT(*) FROM equity_gap WHERE indicator_id = 107").fetchone()[0]

    assert count1 == count2
