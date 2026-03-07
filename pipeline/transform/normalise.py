"""
Load lookup tables from CSVs and seed dimension tables.
"""
import csv
from pathlib import Path
from pipeline.config import LOOKUP_DIR


def load_lookups(conn):
    """Populate lookup + dimension tables from CSV files in data/lookups/."""
    _seed_dim_geography(conn)
    _seed_dim_ethnicity(conn)
    _seed_dim_data_source(conn)
    _load_ethnicity_map(conn)
    _load_geography_map(conn)
    _load_indicator_catalogue(conn)
    print("[normalise] Lookups loaded")


def _seed_dim_geography(conn):
    """Seed canonical geography dimension (national + regions + districts)."""
    # National record first (parent_id = NULL)
    conn.execute("""
        INSERT OR IGNORE INTO dim_geography (id, name, code, level)
        VALUES (1, 'New Zealand', 'NZ', 'national')
    """)

    regions = [
        (2,  'Te Tai Tokerau / Northland',        'TTT', 'health_region', 1),
        (3,  'Waitematā',                          'WMT', 'health_region', 1),
        (4,  'Auckland',                           'AKL', 'health_region', 1),
        (5,  'Counties Manukau',                   'CMK', 'health_region', 1),
        (6,  'Waikato',                            'WKT', 'health_region', 1),
        (7,  'Lakes',                              'LKS', 'health_region', 1),
        (8,  'Bay of Plenty',                      'BOP', 'health_region', 1),
        (9,  'Tairāwhiti',                         'TAI', 'health_region', 1),
        (10, 'Hawke\'s Bay',                       'HKB', 'health_region', 1),
        (11, 'Taranaki',                           'TRK', 'health_region', 1),
        (12, 'MidCentral',                         'MDC', 'health_region', 1),
        (13, 'Whanganui',                          'WHU', 'health_region', 1),
        (14, 'Capital, Coast & Hutt Valley',       'CCH', 'health_region', 1),
        (15, 'Wairarapa',                          'WRP', 'health_region', 1),
        (16, 'Nelson Marlborough',                 'NLM', 'health_region', 1),
        (17, 'West Coast',                         'WCO', 'health_region', 1),
        (18, 'Canterbury',                         'CTB', 'health_region', 1),
        (19, 'South Canterbury',                   'SCT', 'health_region', 1),
        (20, 'Te Whatu Ora Southern',              'STH', 'health_region', 1),
        # NZHS four survey health regions (super-regions grouping the 20 districts)
        (21, 'Northern | Te Tai Tokerau',           'NZHS_N',   'health_region', 1),
        (22, 'Midland | Te Manawa Taki',            'NZHS_M',   'health_region', 1),
        (23, 'Central | Te Ikaroa',                 'NZHS_C',   'health_region', 1),
        (24, 'South Island | Te Waipounamu',        'NZHS_S',   'health_region', 1),
    ]

    for row in regions:
        conn.execute("""
            INSERT OR IGNORE INTO dim_geography (id, name, code, level, parent_id)
            VALUES (?, ?, ?, ?, ?)
        """, row)


def _seed_dim_ethnicity(conn):
    ethnicities = [
        (1,  'Total',            None, None, False, 'total_response'),
        (2,  'Maori',            '1',  None, True,  'total_response'),
        (3,  'Pacific',          '2',  None, False, 'total_response'),
        (4,  'Asian',            '3',  None, False, 'total_response'),
        (5,  'European/Other',   '4',  None, False, 'total_response'),
        (6,  'MELAA',            '5',  None, False, 'total_response'),
        (7,  'Other',            '6',  None, False, 'total_response'),
        (8,  'Maori',            '1',  None, True,  'prioritised'),
        (9,  'Pacific',          '2',  None, False, 'prioritised'),
        (10, 'Asian',            '3',  None, False, 'prioritised'),
        (11, 'European/Other',   '4',  None, False, 'prioritised'),
    ]
    for row in ethnicities:
        conn.execute("""
            INSERT OR IGNORE INTO dim_ethnicity (id, name, level1_code, level2_code, is_indigenous, response_type)
            VALUES (?, ?, ?, ?, ?, ?)
        """, row)


def _seed_dim_data_source(conn):
    sources = [
        (1, 'NZ Health Survey', 'nzhs',
         'https://minhealthnz.shinyapps.io/nz-health-survey-2024-25-annual-data-explorer/',
         'Ministry of Health NZ', 'annual',
         'Total response ethnicity. Geography is health region only.',
         'No district-level breakdown. Small-area estimates suppressed when n<30.',
         'CC BY 4.0'),
        (2, 'Health NZ Quarterly Health Targets', 'health_targets',
         'https://www.tewhatuora.govt.nz',
         'Health New Zealand', 'quarterly',
         'Seed data from manually extracted quarterly performance reports.',
         'Historical DHB-level data mapped to current health regions.',
         'Crown Copyright'),
        (3, 'Stats NZ Subnational Population Projections', 'demographics',
         'https://www.stats.govt.nz/information-releases/subnational-population-projections',
         'Stats NZ', '5-yearly',
         '2023-based projections. Three scenarios: low/medium/high.',
         'Projections become less certain further into future.',
         'CC BY 4.0'),
        (4, 'Health Workforce Seed Data', 'workforce',
         'https://www.tewhatuora.govt.nz',
         'Health New Zealand / Medical Council NZ', 'annual',
         'Manually compiled from workforce reports and Medical Council publications.',
         'Coverage varies by role type; nursing vacancy data is patchier than GP.',
         'Crown Copyright'),
    ]
    for row in sources:
        conn.execute("""
            INSERT OR IGNORE INTO dim_data_source
            (id, name, slug, url, publisher, cadence, methodology_notes, coverage_limitations, license)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, row)


def _load_ethnicity_map(conn):
    path = LOOKUP_DIR / "ethnicity_map.csv"
    if not path.exists():
        print(f"[normalise] WARNING: {path} not found — skipping ethnicity map")
        return
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            conn.execute("""
                INSERT OR IGNORE INTO ethnicity_map (source_label, canonical_ethnicity_id)
                VALUES (?, ?)
            """, (row["source_label"], int(row["canonical_ethnicity_id"])))


def _load_geography_map(conn):
    path = LOOKUP_DIR / "geography_map.csv"
    if not path.exists():
        print(f"[normalise] WARNING: {path} not found — skipping geography map")
        return
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            conn.execute("""
                INSERT OR IGNORE INTO geography_map (source_label, source_type, canonical_geography_id)
                VALUES (?, ?, ?)
            """, (row["source_label"], row["source_type"], int(row["canonical_geography_id"])))


def _load_indicator_catalogue(conn):
    path = LOOKUP_DIR / "indicator_catalogue.csv"
    if not path.exists():
        print(f"[normalise] WARNING: {path} not found — skipping indicator catalogue")
        return
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            conn.execute("""
                INSERT OR IGNORE INTO dim_indicator (id, name, slug, category, direction, unit, gps_priority)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                int(row["id"]),
                row["name"],
                row["slug"],
                row["category"],
                row["direction"],
                row.get("unit", ""),
                row.get("gps_priority", None),
            ))


def coerce_suppressed(value: str) -> tuple:
    """
    Return (python_value_or_None, is_suppressed).
    Suppression markers: '-', '*', 'S', '..', '...'
    """
    if isinstance(value, str):
        stripped = value.strip()
        if stripped in ("-", "*", "S", "..", "..."):
            return None, True
        if stripped in ("", "NA", "N/A", "nan"):
            return None, False
    return value, False
