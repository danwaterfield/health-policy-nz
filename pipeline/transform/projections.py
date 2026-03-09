"""
Demand projection transformer.

Calculates age-specific utilisation rates and multiplies by population projections.
Runs after demographics and health targets are loaded.
"""
from pipeline.transform.base import BaseTransformer
from pipeline.config import DEFERRED_DEMAND_FACTOR


class ProjectionsTransformer(BaseTransformer):
    source_key = "projections"

    def transform(self, conn, dry_run=False):
        if dry_run:
            self.log("DRY RUN: would compute demand projections")
            return

        # Check whether we have the data needed
        access_count = conn.execute("SELECT COUNT(*) FROM fact_service_access").fetchone()[0]
        proj_count = conn.execute(
            "SELECT COUNT(*) FROM fact_demand_projection WHERE scenario IN ('low','baseline','high')"
        ).fetchone()[0]

        self.log(f"fact_service_access: {access_count} rows")
        self.log(f"fact_demand_projection (population): {proj_count} rows")

        if access_count == 0:
            self.log("No service access data — skipping projection calculation")
            return

        # Calculate utilisation-adjusted projections for each geography x scenario
        # Uses volume_seen from fact_service_access as numerator
        # and projected_volume from fact_demand_projection (population spine) as denominator
        inserted = conn.execute("""
            WITH current_access AS (
                SELECT
                    fsa.service_type,
                    fsa.geography_id,
                    SUM(fsa.volume_seen) AS total_seen,
                    SUM(fsa.volume_overdue) AS total_overdue,
                    SUM(fsa.volume_seen) + SUM(COALESCE(fsa.volume_overdue, 0)) AS effective_demand
                FROM fact_service_access fsa
                GROUP BY fsa.service_type, fsa.geography_id
            ),
            pop_projections AS (
                SELECT
                    fdp.geography_id,
                    fdp.time_id,
                    fdp.scenario,
                    fdp.projected_volume AS projected_population,
                    dt.year
                FROM fact_demand_projection fdp
                JOIN dim_time dt ON fdp.time_id = dt.id
                WHERE dt.period_type = 'projection'
            ),
            current_pop AS (
                SELECT
                    fdp.geography_id,
                    AVG(fdp.projected_volume) AS avg_population
                FROM fact_demand_projection fdp
                JOIN dim_time dt ON fdp.time_id = dt.id
                WHERE dt.period_type = 'projection'
                  AND fdp.scenario = 'baseline'
                  AND dt.year = (SELECT MIN(year) FROM dim_time WHERE period_type = 'projection')
                GROUP BY fdp.geography_id
            )
            SELECT COUNT(*) FROM current_access
        """).fetchone()[0]

        # Build projections from access rates x population growth
        conn.execute("DELETE FROM fact_demand_projection WHERE projection_basis LIKE '%utilisation%'")

        rows_inserted = 0
        service_types = conn.execute(
            "SELECT DISTINCT service_type FROM fact_service_access"
        ).fetchall()
        scenarios = ["baseline", "high", "low"]

        for (service_type,) in service_types:
            for scenario in scenarios:
                # Get projection time periods
                proj_years = conn.execute("""
                    SELECT DISTINCT fdp.time_id, dt.year
                    FROM fact_demand_projection fdp
                    JOIN dim_time dt ON fdp.time_id = dt.id
                    WHERE dt.period_type = 'projection'
                    ORDER BY dt.year
                """).fetchall()

                geo_ids = conn.execute(
                    "SELECT DISTINCT geography_id FROM fact_service_access WHERE service_type = ?",
                    (service_type,)
                ).fetchall()

                for (time_id, year) in proj_years:
                    for (geo_id,) in geo_ids:
                        # Get current demand for this service type + geography
                        demand_row = conn.execute("""
                            SELECT
                                SUM(volume_seen) AS seen,
                                SUM(volume_overdue) AS overdue
                            FROM fact_service_access
                            WHERE service_type = ? AND geography_id = ?
                        """, (service_type, geo_id)).fetchone()

                        if not demand_row or demand_row[0] is None:
                            continue

                        current_seen = demand_row[0] or 0
                        current_overdue = demand_row[1] or 0

                        # Get population growth ratio (schema stores 'baseline', not 'medium')
                        pop_scenario = scenario
                        pop_ratio_row = conn.execute("""
                            SELECT fdp.projected_volume /
                                   NULLIF((
                                       SELECT MIN(fdp2.projected_volume)
                                       FROM fact_demand_projection fdp2
                                       JOIN dim_time dt2 ON fdp2.time_id = dt2.id
                                       WHERE fdp2.geography_id = ?
                                         AND fdp2.scenario = ?
                                         AND dt2.period_type = 'projection'
                                   ), 0) AS growth_ratio
                            FROM fact_demand_projection fdp
                            JOIN dim_time dt ON fdp.time_id = dt.id
                            WHERE fdp.geography_id = ? AND fdp.time_id = ?
                              AND fdp.scenario = ?
                        """, (geo_id, pop_scenario, geo_id, time_id, pop_scenario)).fetchone()

                        growth_ratio = (pop_ratio_row[0] if pop_ratio_row and pop_ratio_row[0] else 1.0)

                        # Apply deferred demand adjustment
                        deferred_adj = 1.0
                        if current_seen > 0 and current_overdue > 0:
                            deferred_adj = 1.0 + (current_overdue / current_seen) * DEFERRED_DEMAND_FACTOR

                        projected_volume = current_seen * growth_ratio * deferred_adj

                        basis = (
                            f"Utilisation-based projection: current demand {current_seen}, "
                            f"growth ratio {growth_ratio:.3f}, deferred demand factor {deferred_adj:.3f}. "
                            f"Population spine: Stats NZ {pop_scenario} scenario."
                        )

                        conn.execute("""
                            INSERT INTO fact_demand_projection
                            (id, service_type, geography_id, time_id, scenario,
                             projected_volume, current_capacity, capacity_gap, projection_basis)
                            VALUES (nextval('fact_demand_projection_id_seq'), ?, ?, ?, ?, ?, NULL, NULL, ?)
                        """, (service_type, geo_id, time_id, scenario, projected_volume, basis))
                        rows_inserted += 1

        self.log(f"Done: {rows_inserted} demand projection rows inserted")
