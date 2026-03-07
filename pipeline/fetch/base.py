import time
from pathlib import Path
from pipeline.config import RAW_DIR, STALENESS_DAYS


class BaseFetcher:
    source_key: str  # must match SOURCES key in config

    def is_fresh(self, path: Path) -> bool:
        if not path.exists():
            return False
        age_days = (time.time() - path.stat().st_mtime) / 86400
        return age_days < STALENESS_DAYS

    def fetch(self, dry_run=False) -> Path:
        """Return path to raw file, downloading if necessary."""
        raise NotImplementedError

    def log(self, msg):
        print(f"[{self.__class__.__name__}] {msg}")

    def strip_bom(self, path: Path):
        """Strip UTF-8 BOM from file if present, in-place."""
        content = path.read_bytes()
        if content.startswith(b"\xef\xbb\xbf"):
            path.write_bytes(content[3:])
            self.log("Stripped BOM from file")
