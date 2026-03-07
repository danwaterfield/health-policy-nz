"""Tests for the fetch layer."""
import time
import pytest
from pathlib import Path
from unittest.mock import patch
import tempfile
import os


def test_is_fresh_new_file(tmp_path):
    """A newly created file should be considered fresh."""
    from pipeline.fetch.base import BaseFetcher

    class DummyFetcher(BaseFetcher):
        source_key = "test"
        def fetch(self, dry_run=False):
            pass

    f = tmp_path / "test.csv"
    f.write_text("data")
    fetcher = DummyFetcher()

    with patch("pipeline.fetch.base.STALENESS_DAYS", 7):
        assert fetcher.is_fresh(f) is True


def test_is_fresh_missing_file(tmp_path):
    """A missing file is not fresh."""
    from pipeline.fetch.base import BaseFetcher

    class DummyFetcher(BaseFetcher):
        source_key = "test"
        def fetch(self, dry_run=False):
            pass

    fetcher = DummyFetcher()
    assert fetcher.is_fresh(tmp_path / "nonexistent.csv") is False


def test_is_fresh_old_file(tmp_path):
    """A file older than STALENESS_DAYS should not be fresh."""
    from pipeline.fetch.base import BaseFetcher

    class DummyFetcher(BaseFetcher):
        source_key = "test"
        def fetch(self, dry_run=False):
            pass

    f = tmp_path / "old.csv"
    f.write_text("data")
    # Set mtime to 10 days ago
    old_time = time.time() - (10 * 86400)
    os.utime(f, (old_time, old_time))

    fetcher = DummyFetcher()
    with patch("pipeline.fetch.base.STALENESS_DAYS", 7):
        assert fetcher.is_fresh(f) is False


def test_bom_stripping(tmp_path):
    """BOM should be stripped from file."""
    from pipeline.fetch.base import BaseFetcher

    class DummyFetcher(BaseFetcher):
        source_key = "test"
        def fetch(self, dry_run=False):
            pass

    f = tmp_path / "bom.csv"
    # Write file with UTF-8 BOM
    f.write_bytes(b"\xef\xbb\xbfindicator,value\ntest,1.0\n")

    fetcher = DummyFetcher()
    fetcher.strip_bom(f)

    content = f.read_bytes()
    assert not content.startswith(b"\xef\xbb\xbf")
    assert content.startswith(b"indicator")


def test_bom_strip_idempotent(tmp_path):
    """Stripping BOM from a file without BOM should be a no-op."""
    from pipeline.fetch.base import BaseFetcher

    class DummyFetcher(BaseFetcher):
        source_key = "test"
        def fetch(self, dry_run=False):
            pass

    f = tmp_path / "no_bom.csv"
    original = b"indicator,value\ntest,1.0\n"
    f.write_bytes(original)

    fetcher = DummyFetcher()
    fetcher.strip_bom(f)
    assert f.read_bytes() == original


def test_nzhs_fetcher_dry_run(tmp_path):
    """Dry run should not download anything."""
    from pipeline.fetch.nzhs import NZHSFetcher

    fetcher = NZHSFetcher()
    with patch("pipeline.fetch.nzhs.RAW_DIR", tmp_path):
        with patch("pipeline.config.STALENESS_DAYS", 7):
            # Should not raise even though file doesn't exist in dry_run
            dest = tmp_path / "nzhs_prevalence.csv"
            result = fetcher.fetch(dry_run=True)
            # In dry run, returns path without downloading
            assert result == dest


def test_health_targets_fetcher_uses_seed(tmp_path):
    """HealthTargetsFetcher should return the seed CSV path."""
    from pipeline.fetch.health_targets import HealthTargetsFetcher

    seed = tmp_path / "health_targets_seed.csv"
    seed.write_text("year,district,service_type\n2023,NZ,ed\n")

    fetcher = HealthTargetsFetcher()
    with patch("pipeline.fetch.health_targets.LOOKUP_DIR", tmp_path):
        result = fetcher.fetch()
    assert result == seed
