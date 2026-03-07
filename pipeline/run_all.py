"""
Pipeline orchestrator.

Runs: init schema → load lookups → fetch → transform → derived → export
"""
import argparse
import sys
from pipeline.db import get_conn, init_schema
from pipeline.config import DIST_DIR
from pipeline.fetch.nzhs import NZHSFetcher
from pipeline.fetch.health_targets import HealthTargetsFetcher
from pipeline.fetch.demographics import DemographicsFetcher
from pipeline.fetch.workforce import WorkforceFetcher
from pipeline.fetch.nzdep import NZDepFetcher
from pipeline.fetch.life_tables import LifeTablesFetcher
from pipeline.fetch.electoral import ElectoralFetcher
from pipeline.fetch.corrections import CorrectionsFetcher
from pipeline.fetch.census_age import CensusAgeFetcher
from pipeline.fetch.boundaries import BoundariesFetcher
from pipeline.transform.boundaries import BoundariesTransformer
from pipeline.transform.normalise import load_lookups
from pipeline.transform.nzhs import NZHSTransformer
from pipeline.transform.health_targets import HealthTargetsTransformer
from pipeline.transform.demographics import DemographicsTransformer
from pipeline.transform.workforce import WorkforceTransformer
from pipeline.transform.nzdep import NZDepTransformer
from pipeline.transform.life_tables import LifeTablesTransformer
from pipeline.transform.electoral import ElectoralTransformer
from pipeline.transform.corrections import CorrectionsTransformer
from pipeline.transform.census_age import CensusAgeTransformer
from pipeline.transform.equity_gap import EquityGapTransformer
from pipeline.transform.projections import ProjectionsTransformer
from pipeline.transform.blind_spots import BlindSpotsTransformer
from pipeline.transform.bias_estimates import BiasEstimatesTransformer
import pipeline.export as export_module


def run(dry_run=False):
    print(f"=== NZ Health Pipeline {'(DRY RUN) ' if dry_run else ''}===")

    conn = get_conn()
    init_schema(conn)
    print("[pipeline] Schema initialised")

    load_lookups(conn)

    # Fetch
    fetchers = [
        NZHSFetcher(),
        HealthTargetsFetcher(),
        DemographicsFetcher(),
        WorkforceFetcher(),
        NZDepFetcher(),
        LifeTablesFetcher(),
        ElectoralFetcher(),
        CorrectionsFetcher(),
        CensusAgeFetcher(),
        BoundariesFetcher(),
    ]

    raw_paths = {}
    for fetcher in fetchers:
        try:
            raw_paths[fetcher.source_key] = fetcher.fetch(dry_run=dry_run)
        except Exception as e:
            print(f"[{fetcher.__class__.__name__}] ERROR: {e}")
            raw_paths[fetcher.source_key] = None

    # Transform
    transformers = [
        (NZHSTransformer(), "nzhs_prevalence"),
        (HealthTargetsTransformer(), "health_targets"),
        (DemographicsTransformer(), "demographics"),
        (WorkforceTransformer(), "workforce"),
        (NZDepTransformer(), "nzdep"),
        (LifeTablesTransformer(), "life_tables"),
        (ElectoralTransformer(), "electoral"),
        (CorrectionsTransformer(), "corrections"),
        (CensusAgeTransformer(), "census_age"),
        (BoundariesTransformer(), "boundaries"),
    ]

    for transformer, key in transformers:
        path = raw_paths.get(key)
        if path is None:
            print(f"[{transformer.__class__.__name__}] Skipping — no raw file")
            continue
        try:
            transformer.transform(path, conn, dry_run=dry_run)
        except Exception as e:
            print(f"[{transformer.__class__.__name__}] ERROR: {e}")

    # Derived tables (order matters: equity_gap before bias_estimates)
    for DerivedClass in [EquityGapTransformer, ProjectionsTransformer,
                         BlindSpotsTransformer, BiasEstimatesTransformer]:
        try:
            DerivedClass().transform(conn, dry_run=dry_run)
        except Exception as e:
            print(f"[{DerivedClass.__name__}] ERROR: {e}")

    # Export
    if not dry_run:
        try:
            export_module.run(conn)
        except Exception as e:
            print(f"[export] ERROR: {e}")
            conn.close()
            sys.exit(1)

    conn.close()
    print("=== Pipeline complete ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NZ Health pipeline orchestrator")
    parser.add_argument("--dry-run", action="store_true", help="Log only, no downloads or DB writes")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
