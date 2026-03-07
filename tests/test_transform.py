"""Tests for the transform layer."""
import pytest
import duckdb
from pathlib import Path
from pipeline.transform.nzhs import NZHSTransformer

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_nzhs_transform_idempotent(conn, nzhs_fixture):
    """Running transform twice should produce same row count."""
    transformer = NZHSTransformer()
    transformer.transform(nzhs_fixture, conn)
    count1 = conn.execute("SELECT COUNT(*) FROM fact_health_indicator").fetchone()[0]

    # Delete and re-run to simulate idempotency check
    conn.execute("DELETE FROM fact_health_indicator")
    transformer.transform(nzhs_fixture, conn)
    count2 = conn.execute("SELECT COUNT(*) FROM fact_health_indicator").fetchone()[0]

    assert count1 == count2
    assert count1 > 0


def test_suppression_markers(conn, nzhs_fixture):
    """Rows with *, S, - suppression markers should have suppressed=TRUE and NULL value."""
    transformer = NZHSTransformer()
    transformer.transform(nzhs_fixture, conn)

    suppressed = conn.execute("""
        SELECT COUNT(*) FROM fact_health_indicator WHERE suppressed = TRUE
    """).fetchone()[0]

    assert suppressed >= 3  # fixture has *, S, - rows


def test_suppressed_values_are_null(conn, nzhs_fixture):
    """Suppressed rows must have NULL value."""
    transformer = NZHSTransformer()
    transformer.transform(nzhs_fixture, conn)

    # Any suppressed row with a non-null value is a bug
    bad = conn.execute("""
        SELECT COUNT(*) FROM fact_health_indicator
        WHERE suppressed = TRUE AND value IS NOT NULL
    """).fetchone()[0]
    assert bad == 0


def test_unknown_geography_skipped(conn, tmp_path):
    """Rows with an unrecognised geography should be skipped (no orphan geography)."""
    import io
    csv_content = (
        "indicator,ethnic_group,health_region,year,estimate,lower_ci,upper_ci,sample_size\n"
        "Current smoker,Total,UnknownRegionXYZ,2023,13.5,12.8,14.2,1000\n"
    )
    f = tmp_path / "test.csv"
    f.write_text(csv_content)

    transformer = NZHSTransformer()
    transformer.transform(f, conn)

    count = conn.execute("SELECT COUNT(*) FROM fact_health_indicator").fetchone()[0]
    assert count == 0


def test_unknown_ethnicity_skipped(conn, tmp_path):
    """Rows with an unrecognised ethnicity should be skipped."""
    csv_content = (
        "indicator,ethnic_group,health_region,year,estimate,lower_ci,upper_ci,sample_size\n"
        "Current smoker,UnknownEthnicityXYZ,New Zealand,2023,13.5,12.8,14.2,1000\n"
    )
    f = tmp_path / "test.csv"
    f.write_text(csv_content)

    transformer = NZHSTransformer()
    transformer.transform(f, conn)

    count = conn.execute("SELECT COUNT(*) FROM fact_health_indicator").fetchone()[0]
    assert count == 0


def test_non_suppressed_values_parsed(conn, nzhs_fixture):
    """Non-suppressed rows should have numeric values."""
    transformer = NZHSTransformer()
    transformer.transform(nzhs_fixture, conn)

    non_suppressed = conn.execute("""
        SELECT COUNT(*) FROM fact_health_indicator
        WHERE suppressed = FALSE AND value IS NOT NULL
    """).fetchone()[0]
    assert non_suppressed > 0


def test_ci_bands_loaded(conn, nzhs_fixture):
    """Rows with CI data in fixture should have CI columns populated."""
    transformer = NZHSTransformer()
    transformer.transform(nzhs_fixture, conn)

    with_ci = conn.execute("""
        SELECT COUNT(*) FROM fact_health_indicator
        WHERE value_lower_ci IS NOT NULL AND value_upper_ci IS NOT NULL
    """).fetchone()[0]
    assert with_ci > 0


def test_row_count_logged(conn, nzhs_fixture, capsys):
    """Transformer should log row counts to stdout."""
    transformer = NZHSTransformer()
    transformer.transform(nzhs_fixture, conn)
    captured = capsys.readouterr()
    assert "inserted" in captured.out.lower()
