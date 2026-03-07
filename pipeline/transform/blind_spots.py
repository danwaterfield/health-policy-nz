"""
Blind spots transformer.

Seeds the known data gaps into the blind_spots table. Upserts on domain.
"""
from pipeline.transform.base import BaseTransformer

BLIND_SPOTS = [
    {
        "domain": "mental_health_primary",
        "title": "Mental Health Presentations in Primary Care",
        "description": "Mental health and addiction presentations in GP and primary care settings are substantially undercounted in routinely collected data.",
        "why_missing": "MH presentations in GP settings are coded under other diagnoses; PHO data is not publicly released. PRIMHD captures secondary/tertiary MH only.",
        "proxy_limitation": "Secondary care MH admissions undercount primary care burden by an estimated 4:1 ratio.",
        "severity": "high",
        "further_reading_url": "https://www.health.govt.nz/publication/te-rau-hinengaro-new-zealand-mental-health-survey",
    },
    {
        "domain": "disability_under18",
        "title": "Disability Among Children Under 18",
        "description": "The 2023 Household Disability Survey excludes children from its depth analysis, leaving a major gap in understanding disabled children's health system use.",
        "why_missing": "2023 Household Disability Survey excludes children from depth analysis. IDI-linked analyses exist but require accreditation.",
        "proxy_limitation": "NASC data captures disability support need but not health system utilisation patterns.",
        "severity": "high",
        "further_reading_url": "https://www.stats.govt.nz/information-releases/results-from-the-2023-disability-survey",
    },
    {
        "domain": "pacific_subgroup",
        "title": "Pacific Peoples Subgroup Disaggregation",
        "description": "Most national datasets aggregate all Pacific peoples into a single group, masking significant heterogeneity between Samoan, Tongan, Cook Island, Niuean, Fijian, and other communities.",
        "why_missing": "Small sample sizes at subgroup level trigger suppression rules in most public datasets. NZ Pacific Health Survey (2006) is outdated.",
        "proxy_limitation": "Aggregated 'Pacific' category has different health profiles by subgroup — using aggregate can misallocate resources.",
        "severity": "high",
        "further_reading_url": "https://www.health.govt.nz/our-work/populations/pacific-health",
    },
    {
        "domain": "rural_gp_access_cost",
        "title": "Rural GP Access: Cost and Travel Time Barriers",
        "description": "GP density data exists at district level but cost and travel-time barriers to access are only captured in surveys with small rural sample sizes.",
        "why_missing": "GP density data exists; cost/travel-time access difficulty is survey-derived only with small-n at district level. No administrative data captures foregone care.",
        "proxy_limitation": "GP-per-population is a supply proxy; does not capture affordability or geographic accessibility for specific populations.",
        "severity": "medium",
        "further_reading_url": "https://www.health.govt.nz/publication/primary-care-rural-access",
    },
    {
        "domain": "not_on_the_list",
        "title": "Unmet Need: People Who Never Reach Specialist Care",
        "description": "Waiting list data only captures people who have been referred and accepted. People who never receive a referral — often in deprived communities — are entirely invisible.",
        "why_missing": "People who never reach a GP or specialist never appear in waiting list data. This 'hidden' unmet demand has no direct administrative measure.",
        "proxy_limitation": "Amenable mortality and ED presentations can proxy for unmet need but with long attribution lags and confounding.",
        "severity": "high",
        "further_reading_url": "https://www.hqsc.govt.nz/resources/resource-library/atlas-of-healthcare-variation/",
    },
    {
        "domain": "aged_care_quality",
        "title": "Residential Aged Care Quality",
        "description": "Quality data for residential aged care facilities is fragmented across audit reports, complaints data, and staffing records — none systematically structured for analysis.",
        "why_missing": "Inspection reports are not systematically structured for analysis. Staffing ratios are reported but not publicly linked to outcomes. Complaints data is partial.",
        "proxy_limitation": "Audit certification levels are a binary pass/fail — they do not capture continuous quality variation.",
        "severity": "medium",
        "further_reading_url": "https://www.health.govt.nz/our-work/regulation-health-and-disability-system/certifying-health-care-services",
    },
    {
        "domain": "maori_disability_intersect",
        "title": "Maori and Disabled: Intersectional Data Gap",
        "description": "The intersection of Maori ethnicity and disability barely exists at district level in any public NZ health data source.",
        "why_missing": "Suppression rules eliminate most small-n cells at the Maori x disabled x district level. IDI linkage exists but requires accreditation. Most public datasets choose one dimension.",
        "proxy_limitation": "Separate Maori health and disability datasets cannot be combined without individual-level linkage.",
        "severity": "high",
        "further_reading_url": "https://www.stats.govt.nz/information-releases/results-from-the-2023-disability-survey",
    },
]


class BlindSpotsTransformer(BaseTransformer):
    source_key = "blind_spots"

    def transform(self, conn, dry_run=False):
        if dry_run:
            self.log(f"DRY RUN: would upsert {len(BLIND_SPOTS)} blind spot rows")
            return

        upserted = 0
        for spot in BLIND_SPOTS:
            conn.execute("""
                INSERT INTO blind_spots
                    (id, domain, title, description, why_missing,
                     best_proxy_indicator_id, proxy_limitation, severity, further_reading_url)
                VALUES (nextval('blind_spots_id_seq'), ?, ?, ?, ?, NULL, ?, ?, ?)
                ON CONFLICT (domain) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    why_missing = excluded.why_missing,
                    proxy_limitation = excluded.proxy_limitation,
                    severity = excluded.severity,
                    further_reading_url = excluded.further_reading_url
            """, (
                spot["domain"],
                spot["title"],
                spot["description"],
                spot["why_missing"],
                spot["proxy_limitation"],
                spot["severity"],
                spot["further_reading_url"],
            ))
            upserted += 1

        self.log(f"Done: {upserted} blind spot rows upserted")
