import json
from pathlib import Path

import requests

from .config import REQUEST_TIMEOUT, USER_AGENT

BOUNDARY_API = "https://www.geoboundaries.org/api/current/gbOpen/THA/ADM1/"
BOUNDARY_PATH = Path("/opt/airflow/data/thailand_adm1.geojson")


def prepare_thailand_boundaries() -> str:
    """Cache CC BY 4.0 ADM1 geometry for country filtering and province lookup."""
    if BOUNDARY_PATH.exists():
        payload = json.loads(BOUNDARY_PATH.read_text(encoding="utf-8"))
        if payload.get("type") == "FeatureCollection" and len(payload.get("features", [])) >= 70:
            return str(BOUNDARY_PATH)
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    metadata = requests.get(BOUNDARY_API, headers=headers, timeout=REQUEST_TIMEOUT)
    metadata.raise_for_status()
    meta = metadata.json()
    download_url = meta.get("simplifiedGeometryGeoJSON") or meta["gjDownloadURL"]
    response = requests.get(download_url, headers=headers, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    if payload.get("type") != "FeatureCollection" or len(payload.get("features", [])) < 70:
        raise ValueError("Thailand ADM1 boundary payload is incomplete")
    BOUNDARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = BOUNDARY_PATH.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    temp.replace(BOUNDARY_PATH)
    return str(BOUNDARY_PATH)


def _point_in_ring(x, y, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][:2]
        xj, yj = ring[j][:2]
        if ((yi > y) != (yj > y)) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _point_in_polygon(x, y, polygon):
    return bool(polygon and _point_in_ring(x, y, polygon[0])
                and not any(_point_in_ring(x, y, hole) for hole in polygon[1:]))


def province_for_point(latitude, longitude, feature_collection):
    """Return ADM1 name only when the coordinate is inside a Thai polygon."""
    for feature in feature_collection["features"]:
        geometry = feature.get("geometry") or {}
        coords = geometry.get("coordinates") or []
        if geometry.get("type") == "Polygon":
            hit = _point_in_polygon(longitude, latitude, coords)
        elif geometry.get("type") == "MultiPolygon":
            hit = any(_point_in_polygon(longitude, latitude, polygon) for polygon in coords)
        else:
            hit = False
        if hit:
            props = feature.get("properties") or {}
            return props.get("shapeName") or props.get("NAME_1") or props.get("name")
    return None


def filter_and_enrich(events, boundary_path):
    boundaries = json.loads(Path(boundary_path).read_text(encoding="utf-8"))
    inside, outside = [], []
    for event in events:
        province = province_for_point(event["latitude"], event["longitude"], boundaries)
        if province:
            event["province"] = province
            event["is_in_thailand"] = True
            inside.append(event)
        else:
            outside.append({"source": event.get("source"), "reason": "outside Thailand ADM1 polygons", "payload": event})
    return inside, outside
