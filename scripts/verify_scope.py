"""Fail fast when the analytical table violates the assignment scope."""
import json
import os

import psycopg2

from earthquake_etl.boundaries import BOUNDARY_PATH, province_for_point

with open(BOUNDARY_PATH, encoding="utf-8") as stream:
    boundaries = json.load(stream)

with psycopg2.connect(os.environ["EARTHQUAKE_DB_URL"]) as conn, conn.cursor() as cur:
    cur.execute("SELECT event_uid,occurred_at,latitude,longitude,province,sources FROM earthquake_events")
    rows = cur.fetchall()

assert len(rows) >= 100, f"only {len(rows)} rows"
covered_sources = set()
for uid, occurred, latitude, longitude, province, sources in rows:
    assert 2021 <= occurred.year <= 2026, f"{uid}: year {occurred.year} out of scope"
    polygon_province = province_for_point(latitude, longitude, boundaries)
    assert polygon_province == province, f"{uid}: {province!r} != polygon {polygon_province!r}"
    covered_sources.update(sources)
assert covered_sources == {"tmd", "usgs", "geofon"}, covered_sources
print(f"PASS: {len(rows)} polygon-verified rows, years 2021-2026, sources={sorted(covered_sources)}")

