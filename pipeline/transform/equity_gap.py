"""
Equity gap transformer.

Computes gaps vs. European/Other at national level for each indicator × geography × time.
Runs after all fact tables are populated.
"""
from pipeline.transform.base import BaseTransformer

EQUITY_GAP_SQL = """
INSERT INTO equity_gap
SELECT
    nextval('equity_gap_id_seq')                AS id,
    target.indicator_id,
    target.geography_id,
    target.time_id,
    ref.ethnicity_id                            AS reference_ethnicity_id,
    target.ethnicity_id                         AS target_ethnicity_id,
    ref.value                                   AS reference_value,
    target.value                                AS target_value,
    (target.value - ref.value)                  AS absolute_gap,
    ((target.value / NULLIF(ref.value, 0)) - 1) AS relative_gap,
    CASE
        WHEN ind.direction = 'higher_better' AND target.value < ref.value THEN 'adverse'
        WHEN ind.direction = 'lower_better'  AND target.value > ref.value THEN 'adverse'
        WHEN target.value = ref.value THEN 'neutral'
        ELSE 'favourable'
    END AS gap_direction
FROM fact_health_indicator target
JOIN fact_health_indicator ref
    ON  target.indicator_id  = ref.indicator_id
    AND target.time_id       = ref.time_id
    AND ref.geography_id     = (SELECT id FROM dim_geography WHERE level = 'national' LIMIT 1)
    AND ref.ethnicity_id     = (SELECT id FROM dim_ethnicity
                                WHERE name = 'European/Other'
                                  AND response_type = 'total_response'
                                LIMIT 1)
JOIN dim_indicator ind ON target.indicator_id = ind.id
WHERE target.ethnicity_id IS NOT NULL
  AND target.ethnicity_id != ref.ethnicity_id
  AND target.suppressed = FALSE
  AND ref.suppressed = FALSE
  AND target.value IS NOT NULL
  AND ref.value IS NOT NULL
  AND (target.sample_size IS NULL OR target.sample_size >= 30)
"""


class EquityGapTransformer(BaseTransformer):
    source_key = "equity_gap"

    def transform(self, conn, dry_run=False):
        if dry_run:
            self.log("DRY RUN: would compute equity gaps")
            return

        # Clear existing computed gaps for idempotency
        conn.execute("DELETE FROM equity_gap")

        # Check that we have reference population data
        ref_count = conn.execute("""
            SELECT COUNT(*) FROM fact_health_indicator
            WHERE ethnicity_id = (
                SELECT id FROM dim_ethnicity
                WHERE name = 'European/Other' AND response_type = 'total_response'
                LIMIT 1
            )
            AND geography_id = (SELECT id FROM dim_geography WHERE level = 'national' LIMIT 1)
            AND suppressed = FALSE
            AND value IS NOT NULL
        """).fetchone()[0]

        if ref_count == 0:
            self.log("WARNING: No reference population (European/Other, national) values found — equity gap table will be empty")
            return

        self.log(f"Reference population has {ref_count} values")

        # Log missing reference combinations before computing gaps
        missing = conn.execute("""
            SELECT DISTINCT target.indicator_id, target.geography_id, target.time_id
            FROM fact_health_indicator target
            WHERE target.suppressed = FALSE
              AND target.value IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM fact_health_indicator ref
                WHERE ref.indicator_id = target.indicator_id
                  AND ref.time_id = target.time_id
                  AND ref.geography_id = (SELECT id FROM dim_geography WHERE level = 'national' LIMIT 1)
                  AND ref.ethnicity_id = (SELECT id FROM dim_ethnicity
                                          WHERE name = 'European/Other'
                                            AND response_type = 'total_response'
                                          LIMIT 1)
                  AND ref.suppressed = FALSE
                  AND ref.value IS NOT NULL
              )
        """).fetchall()

        if missing:
            self.log(f"WARNING: {len(missing)} indicator×geography×time combinations lack a reference value")

        conn.execute(EQUITY_GAP_SQL)
        count = conn.execute("SELECT COUNT(*) FROM equity_gap").fetchone()[0]
        self.log(f"Done: {count} equity gap rows computed")
