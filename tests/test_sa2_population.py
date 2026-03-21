"""Test SA2 population aggregation from SA1 data."""
import shutil
import duckdb
import pytest
from pipeline.db import init_schema
from pipeline.transform.sa2_boundaries import SA2BoundariesTransformer
from pathlib import Path

needs_mapshaper = pytest.mark.skipif(
    not shutil.which("mapshaper"),
    reason="mapshaper not installed"
)
needs_nzdep = pytest.mark.skipif(
    not Path("data/raw/nzdep2018.xlsx").exists(),
    reason="NZDep Excel not available"
)

@needs_mapshaper
@needs_nzdep
def test_population_aggregated():
    """SA2 NZDep rows should have non-null population from SA1 aggregation."""
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    t = SA2BoundariesTransformer()
    t.transform(Path("data/lookups/sa2_2025_simplified.geojson"), conn)
    rows = conn.execute(
        "SELECT COUNT(*) as total, "
        "COUNT(population) as with_pop, "
        "SUM(population) as total_pop "
        "FROM fact_sa2_nzdep"
    ).fetchone()
    conn.close()
    assert rows[0] > 2000, f"Expected >2000 SA2 NZDep rows, got {rows[0]}"
    assert rows[1] == rows[0], f"All rows should have population, {rows[0] - rows[1]} missing"
    assert rows[2] > 4_000_000, f"Total NZ pop should be >4M, got {rows[2]}"

@needs_mapshaper
@needs_nzdep
def test_region_assigned_to_all():
    """All SA2 NZDep rows should have a health_region."""
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    t = SA2BoundariesTransformer()
    t.transform(Path("data/lookups/sa2_2025_simplified.geojson"), conn)
    missing = conn.execute(
        "SELECT COUNT(*) FROM fact_sa2_nzdep WHERE health_region = '' OR health_region IS NULL"
    ).fetchone()[0]
    conn.close()
    assert missing == 0, f"{missing} SA2s missing health_region"
