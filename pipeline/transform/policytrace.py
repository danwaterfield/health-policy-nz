"""
PolicyTrace i4i bundle transformer.

Reads the nz-health-policy interop bundle JSON and loads events into
fact_policy_events. Events are used as annotation overlays on the
trends and equity pages (e.g. vertical lines for key policy changes).
"""
import json
from pathlib import Path
from urllib.parse import urlparse
from pipeline.transform.base import BaseTransformer


class PolicyTraceTransformer(BaseTransformer):
    source_key = "policytrace"

    def transform(self, path: Path, conn, dry_run=False):
        if dry_run:
            self.log("DRY RUN: would load PolicyTrace events")
            return

        with open(path, encoding="utf-8") as f:
            bundle = json.load(f)

        events = bundle.get("events", [])
        self.log(f"Loaded {len(events)} events from {path}")

        # Build document URL lookup: doc_id → url
        doc_urls = {
            d["id"]: d.get("url", "")
            for d in bundle.get("documents", [])
        }

        conn.execute("DELETE FROM fact_policy_events")

        inserted = 0
        for evt in events:
            # Resolve first source URL (only allow http/https schemes)
            src_ids = evt.get("source_document_ids", [])
            raw_url = doc_urls.get(src_ids[0], "") if src_ids else ""
            try:
                scheme = urlparse(raw_url).scheme
                source_url = raw_url if scheme in ("http", "https", "") else ""
            except Exception:
                source_url = ""

            # Flatten tags to pipe-separated string
            tags = "|".join(evt.get("tags", []))

            conn.execute("""
                INSERT INTO fact_policy_events
                    (id, date, date_precision, title, actor, category,
                     status, tags, treaty_relevance, confidence_score,
                     timeline_slug, source_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                evt["legacy_id"],
                evt.get("date", ""),
                evt.get("date_precision", ""),
                evt.get("title", ""),
                evt.get("actor", ""),
                evt.get("category", ""),
                evt.get("status", ""),
                tags,
                evt.get("treaty_relevance", ""),
                evt.get("confidence_score"),
                bundle["timeline"]["slug"],
                source_url,
            ))
            inserted += 1

        self.log(f"Done: {inserted} policy events inserted")
