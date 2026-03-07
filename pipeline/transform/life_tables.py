"""
Stats NZ period life tables transformer.

Parses the 2017-19 national period life tables Excel, extracting Māori,
non-Māori, and total life tables by age band and sex. Stores in
fact_life_tables for display and future age-standardisation use.

The Stats NZ Excel typically has sheets named e.g.:
  "Table 1", "Maori males", "Maori females", "Non-Maori males", ...
Sheet naming is inconsistent across releases so we use fuzzy matching.
"""
import re
import pandas as pd
from pathlib import Path
from pipeline.transform.base import BaseTransformer


# Known age-band ordering for sorting
AGE_ORDER = ["0", "1-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34",
             "35-39", "40-44", "45-49", "50-54", "55-59", "60-64", "65-69",
             "70-74", "75-79", "80-84", "85+"]

# Fallback headline life expectancy values from published Stats NZ tables
# Source: Stats NZ 2017-19 period life tables publication
FALLBACK_ROWS = [
    # (ethnicity_group, sex, age_band, age_from, qx, lx, ex)
    ("Maori",     "male",   "0",   0,  0.00830, 100000, 73.0),
    ("Maori",     "female", "0",   0,  0.00670, 100000, 76.8),
    ("Maori",     "total",  "0",   0,  0.00750, 100000, 75.1),
    ("non-Maori", "male",   "0",   0,  0.00490, 100000, 80.7),
    ("non-Maori", "female", "0",   0,  0.00380, 100000, 84.1),
    ("non-Maori", "total",  "0",   0,  0.00430, 100000, 82.5),
    ("total",     "male",   "0",   0,  0.00520, 100000, 79.9),
    ("total",     "female", "0",   0,  0.00400, 100000, 83.4),
    ("total",     "total",  "0",   0,  0.00460, 100000, 81.7),
]


class LifeTablesTransformer(BaseTransformer):
    source_key = "life_tables"

    def transform(self, path: Path, conn, dry_run=False):
        if dry_run:
            self.log("DRY RUN: would load Stats NZ life tables")
            return

        conn.execute("DELETE FROM fact_life_tables")

        rows = self._parse(path)
        if not rows:
            self.log("No rows parsed from Excel; inserting fallback headline values")
            rows = self._fallback_rows()

        for row in rows:
            conn.execute("""
                INSERT INTO fact_life_tables
                    (id, ethnicity_group, sex, age_band, age_from, qx, lx, ex, year_range, source)
                VALUES (nextval('fact_life_tables_id_seq'), ?, ?, ?, ?, ?, ?, ?, '2017-19',
                        'Stats NZ National and Subnational Period Life Tables 2017-19')
            """, row)

        self.log(f"Done: {len(rows)} life table rows inserted")

    # Stats NZ 2017-19 Excel structure (confirmed from inspection):
    #   Row 2  (0-based): Title, e.g. "Māori male population period life table, 2017–2019"
    #   Row 10:           Column identifiers: x, lx, Lx, dx, px, qx, mx, ex
    #   Row 12:           Percentile labels: 0.025, 50% (Median), 0.975 per field
    #   Row 13+:          Data (one row per single age year)
    # Each statistical field (lx, qx, ex, …) occupies 3 columns: lower/median/upper.
    # Fixed column indices (0-based): age=0, lx_med=2, qx_med=14, ex_med=20

    # Title → (ethnicity_group, sex)
    # non-Māori entries MUST come before Māori entries: "māori" is a substring of "non-māori"
    TITLE_MAP = [
        ("non-māori male", ("non-Maori", "male")),
        ("non-maori male", ("non-Maori", "male")),
        ("non-mäori male", ("non-Maori", "male")),
        ("non-māori female", ("non-Maori", "female")),
        ("non-maori female", ("non-Maori", "female")),
        ("non-mäori female", ("non-Maori", "female")),
        ("māori male", ("Maori", "male")),
        ("maori male", ("Maori", "male")),
        ("mäori male", ("Maori", "male")),
        ("māori female", ("Maori", "female")),
        ("maori female", ("Maori", "female")),
        ("mäori female", ("Maori", "female")),
        ("pacific male", ("Pacific", "male")),
        ("pacific female", ("Pacific", "female")),
        ("asian male", ("Asian", "male")),
        ("asian female", ("Asian", "female")),
        ("european or other male", ("European/Other", "male")),
        ("european or other female", ("European/Other", "female")),
        ("total male", ("total", "male")),
        ("total female", ("total", "female")),
    ]

    def _parse(self, path: Path) -> list:
        try:
            xl = pd.ExcelFile(path, engine="openpyxl")
        except Exception as e:
            self.log(f"Could not open Excel: {e}")
            return []

        self.log(f"Sheets: {xl.sheet_names}")
        rows = []

        for sheet in xl.sheet_names:
            if sheet == "Contents":
                continue
            try:
                # Read full sheet without headers to inspect title row
                raw = xl.parse(sheet, header=None)
                if raw.shape[0] < 14:
                    continue

                # Title is in row 2 (0-based index)
                title = str(raw.iloc[2, 0]).strip()
                grp, sex = self._classify_title(title)
                if grp is None:
                    continue

                # Data starts at row 13 (0-based); columns are at fixed positions
                data = raw.iloc[13:].reset_index(drop=True)
                parsed = self._extract_rows(data, grp, sex)
                rows.extend(parsed)
                self.log(f"  Sheet '{sheet}' → {grp}/{sex}: {len(parsed)} age rows")
            except Exception as e:
                self.log(f"  Sheet '{sheet}' failed: {e}")

        return rows

    def _classify_title(self, title: str):
        t = title.lower()
        for pattern, result in self.TITLE_MAP:
            if pattern in t:
                return result
        return None, None

    def _extract_rows(self, data: pd.DataFrame, grp: str, sex: str) -> list:
        rows = []
        for _, r in data.iterrows():
            age_val = r.iloc[0]
            if pd.isna(age_val) or str(age_val).strip() in ("", "nan"):
                continue
            try:
                age = int(float(age_val))
            except (ValueError, TypeError):
                continue

            qx = self._safe_float(r.iloc[14])
            lx = self._safe_float(r.iloc[2])
            ex = self._safe_float(r.iloc[20])

            rows.append((grp, sex, str(age), age, qx, lx, ex))
        return rows

    @staticmethod
    def _safe_float(val) -> float | None:
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    def _fallback_rows(self) -> list:
        return [
            (grp, sex, age_band, age_from, qx, lx, ex)
            for grp, sex, age_band, age_from, qx, lx, ex in FALLBACK_ROWS
        ]
