"""Shared test fixtures."""
import pytest
import duckdb
from pathlib import Path
from pipeline.db import init_schema
from pipeline.transform.normalise import load_lookups

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def conn():
    """In-memory DuckDB connection with schema and lookups initialised."""
    c = duckdb.connect(":memory:")
    init_schema(c)
    load_lookups(c)
    yield c
    c.close()


@pytest.fixture
def nzhs_fixture():
    return FIXTURES_DIR / "nzhs_prevalence_sample.csv"
