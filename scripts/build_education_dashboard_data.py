"""Build compact JSON data for the education intelligence dashboard.

The source archive is intentionally left outside the project. This script
streams selected indicators from the large CSV files and writes a small JSON
file that the browser dashboard can load quickly.
"""

from __future__ import annotations

import csv
import io
import json
import math
import sys
import zipfile
from collections import defaultdict
from pathlib import Path


DEFAULT_ZIP = Path(r"C:\Users\DELL\Desktop\DS.zip")
OUT_PATH = Path("education_dashboard/data/dashboard_data.json")

START_YEAR = 2000
END_YEAR = 2025

WDI_METRICS = {
    "NY.GDP.PCAP.CD": {
        "group": "Development",
        "label": "GDP per capita",
        "unit": "current US$",
        "format": "currency",
    },
    "SP.DYN.LE00.IN": {
        "group": "Health",
        "label": "Life expectancy",
        "unit": "years",
        "format": "number",
    },
    "SE.XPD.TOTL.GD.ZS": {
        "group": "Education",
        "label": "Government education spending",
        "unit": "% of GDP",
        "format": "percent",
    },
    "SE.PRM.ENRR": {
        "group": "Education",
        "label": "Primary enrollment",
        "unit": "% gross",
        "format": "percent",
    },
    "SE.SEC.ENRR": {
        "group": "Education",
        "label": "Secondary enrollment",
        "unit": "% gross",
        "format": "percent",
    },
    "IT.NET.USER.ZS": {
        "group": "Technology",
        "label": "Internet users",
        "unit": "% of population",
        "format": "percent",
    },
}

UIS_METRICS = {
    "GER.1.GPIA": {
        "group": "Education Equity",
        "label": "Primary gender parity",
        "unit": "index",
        "format": "index",
    },
    "GER.2T3.GPIA": {
        "group": "Education Equity",
        "label": "Secondary gender parity",
        "unit": "index",
        "format": "index",
    },
    "OFST.1T3.CP": {
        "group": "Education Access",
        "label": "Out-of-school children and youth",
        "unit": "people",
        "format": "large",
    },
    "FTP.1": {
        "group": "Education Workforce",
        "label": "Female primary teachers",
        "unit": "%",
        "format": "percent",
    },
    "X.PPP.FSGOV": {
        "group": "Education Finance",
        "label": "Education expenditure",
        "unit": "PPP$ millions",
        "format": "large",
    },
}

SDG_METRICS = {
    "EXPGDP.TOT": {
        "group": "Research Capacity",
        "label": "R&D expenditure",
        "unit": "% of GDP",
        "format": "percent",
    },
    "RESDEN.INHAB.TFTE": {
        "group": "Research Capacity",
        "label": "Researchers",
        "unit": "per million people",
        "format": "number",
    },
}

LEE_METRICS = {
    "Tscore_ML": {
        "group": "Education Quality",
        "label": "Harmonized test score",
        "unit": "score",
        "format": "number",
    },
    "Q_ML": {
        "group": "Education Quality",
        "label": "Working-age education quality",
        "unit": "index",
        "format": "index",
    },
}


def clean_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def csv_reader_from_zip(zf: zipfile.ZipFile, name: str) -> csv.DictReader:
    raw = zf.open(name)
    text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
    return csv.DictReader(text)


def add_record(records: list[dict], source: str, country: str, year: str, metric: str, value: str | None) -> None:
    parsed = clean_float(value)
    if parsed is None:
        return
    try:
        year_int = int(float(year))
    except (TypeError, ValueError):
        return
    if START_YEAR <= year_int <= END_YEAR:
        records.append(
            {
                "source": source,
                "country": country,
                "year": year_int,
                "metric": metric,
                "value": round(parsed, 4),
            }
        )


def load_country_metadata(zf: zipfile.ZipFile) -> dict[str, dict]:
    countries: dict[str, dict] = {}
    reader = csv_reader_from_zip(zf, "DS/Dataset-1/WDI_CSV_2026_04_09/WDICountry.csv")
    for row in reader:
        code = row.get("Country Code", "").strip()
        region = row.get("Region", "").strip()
        if not code or not region:
            continue
        countries[code] = {
            "code": code,
            "name": row.get("Short Name") or row.get("Table Name") or code,
            "region": region,
            "income": row.get("Income Group") or "Unclassified",
        }
    return countries


def collect_wdi(zf: zipfile.ZipFile, countries: dict[str, dict], records: list[dict]) -> None:
    reader = csv_reader_from_zip(zf, "DS/Dataset-1/WDI_CSV_2026_04_09/WDICSV.csv")
    years = [str(year) for year in range(START_YEAR, END_YEAR + 1)]
    for row in reader:
        metric = row.get("Indicator Code")
        country = row.get("Country Code")
        if metric not in WDI_METRICS or country not in countries:
            continue
        for year in years:
            add_record(records, "World Bank WDI", country, year, metric, row.get(year))


def collect_uis(zf: zipfile.ZipFile, countries: dict[str, dict], records: list[dict]) -> None:
    reader = csv_reader_from_zip(zf, "DS/Data UN/uis006.csv")
    for row in reader:
        metric = row.get("INDICATOR_ID")
        country = row.get("COUNTRY_ID")
        if metric in UIS_METRICS and country in countries:
            add_record(records, "UNESCO UIS", country, row.get("YEAR", ""), metric, row.get("VALUE"))


def collect_sdg(zf: zipfile.ZipFile, countries: dict[str, dict], records: list[dict]) -> None:
    reader = csv_reader_from_zip(zf, "DS/Dataset-2/SCN-SDG/SCN-SDG_DATA_NATIONAL.csv")
    for row in reader:
        metric = row.get("INDICATOR_ID")
        country = row.get("COUNTRY_ID")
        if metric in SDG_METRICS and country in countries:
            add_record(records, "UNESCO SDG R&D", country, row.get("YEAR", ""), metric, row.get("VALUE"))


def collect_lee(zf: zipfile.ZipFile, countries: dict[str, dict], records: list[dict]) -> None:
    reader = csv_reader_from_zip(zf, "DS/Dataset-5/16778072/Lee_Lee_2025.csv")
    for row in reader:
        country = row.get("CountryCode")
        if country not in countries:
            continue
        for metric in LEE_METRICS:
            add_record(records, "Lee & Lee 2025", country, row.get("Year", ""), metric, row.get(metric))


def latest_records(records: list[dict]) -> list[dict]:
    best: dict[tuple[str, str], dict] = {}
    for record in records:
        key = (record["country"], record["metric"])
        current = best.get(key)
        if current is None or record["year"] > current["year"]:
            best[key] = record
    return sorted(best.values(), key=lambda item: (item["metric"], item["country"]))


def regional_summary(records: list[dict], countries: dict[str, dict]) -> list[dict]:
    latest = latest_records(records)
    buckets: dict[tuple[str, str], list[float]] = defaultdict(list)
    for record in latest:
        country = countries.get(record["country"])
        if country:
            buckets[(country["region"], record["metric"])].append(record["value"])

    summary = []
    for (region, metric), values in sorted(buckets.items()):
        if not values:
            continue
        summary.append(
            {
                "region": region,
                "metric": metric,
                "countries": len(values),
                "average": round(sum(values) / len(values), 4),
            }
        )
    return summary


def build_payload(zip_path: Path) -> dict:
    if not zip_path.exists():
        raise FileNotFoundError(f"Could not find source archive: {zip_path}")

    with zipfile.ZipFile(zip_path) as zf:
        countries = load_country_metadata(zf)
        records: list[dict] = []
        collect_wdi(zf, countries, records)
        collect_uis(zf, countries, records)
        collect_sdg(zf, countries, records)
        collect_lee(zf, countries, records)

    metric_meta = {}
    for source in (WDI_METRICS, UIS_METRICS, SDG_METRICS, LEE_METRICS):
        metric_meta.update(source)

    used_countries = {record["country"] for record in records}
    country_list = sorted(
        (country for code, country in countries.items() if code in used_countries),
        key=lambda item: item["name"],
    )

    return {
        "generated_from": str(zip_path),
        "year_range": [START_YEAR, END_YEAR],
        "metrics": metric_meta,
        "countries": country_list,
        "records": records,
        "latest": latest_records(records),
        "regions": regional_summary(records, countries),
    }


def main() -> int:
    zip_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ZIP
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else OUT_PATH
    payload = build_payload(zip_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {output_path}")
    print(f"Countries: {len(payload['countries'])}")
    print(f"Records: {len(payload['records'])}")
    print(f"Latest country-metric values: {len(payload['latest'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
