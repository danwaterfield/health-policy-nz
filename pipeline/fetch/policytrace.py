"""
PolicyTrace i4i bundle fetcher.

Downloads the nz-health-policy interop bundle from the PolicyTrace
GitHub Pages site (or reads from a local path if POLICYTRACE_LOCAL_PATH
is set in the environment). Falls back to any existing cached copy.

The bundle URL is the published GitHub Pages path:
  https://<owner>.github.io/policytrace/data/nz-health-policy.interop.v1.json

Set POLICYTRACE_BUNDLE_URL to override. Set POLICYTRACE_LOCAL_PATH to
point at a local policytrace checkout's site/data/ directory instead.
"""
import os
import shutil
from pathlib import Path

import requests

from pipeline.config import RAW_DIR, LOOKUP_DIR, STALENESS_DAYS
from pipeline.fetch.base import BaseFetcher

BUNDLE_FILENAME = "nz-health-policy.interop.v1.json"
DEFAULT_BUNDLE_URL = os.getenv(
    "POLICYTRACE_BUNDLE_URL",
    "https://danwaterfield.github.io/policytrace/data/nz-health-policy.interop.v1.json",
)
LOCAL_PATH = os.getenv("POLICYTRACE_LOCAL_PATH", "")


class PolicyTraceFetcher(BaseFetcher):
    source_key = "policytrace"

    def fetch(self, dry_run=False) -> Path:
        dest = RAW_DIR / BUNDLE_FILENAME
        RAW_DIR.mkdir(parents=True, exist_ok=True)

        if self.is_fresh(dest):
            self.log(f"Cache fresh: {dest}")
            return dest

        if dry_run:
            self.log(f"DRY RUN: would fetch PolicyTrace bundle to {dest}")
            return dest

        # 1. Try local path (dev mode) — must be an existing directory
        if LOCAL_PATH and Path(LOCAL_PATH).is_dir():
            local_file = Path(LOCAL_PATH).resolve() / BUNDLE_FILENAME
            if local_file.exists():
                shutil.copy(local_file, dest)
                self.log(f"Copied from local path: {local_file}")
                return dest
            self.log(f"POLICYTRACE_LOCAL_PATH set but file not found: {local_file}")

        # 2. HTTP download from published GitHub Pages
        try:
            self.log(f"Downloading {DEFAULT_BUNDLE_URL}")
            r = requests.get(DEFAULT_BUNDLE_URL, timeout=30)
            r.raise_for_status()
            dest.write_bytes(r.content)
            self.log(f"Downloaded to {dest}")
            return dest
        except Exception as e:
            self.log(f"HTTP download failed: {e}")

        # 3. Use existing cached file
        if dest.exists():
            self.log("Using existing cached bundle")
            return dest

        seed = LOOKUP_DIR / BUNDLE_FILENAME
        if seed.exists():
            self.log(f"Falling back to committed seed bundle: {seed}")
            return seed

        self.log(
            "WARNING: PolicyTrace bundle unavailable — policy event annotations will be skipped. "
            f"Set POLICYTRACE_LOCAL_PATH or ensure {DEFAULT_BUNDLE_URL} is reachable."
        )
        return None
