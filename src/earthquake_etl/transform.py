import hashlib
import math
from datetime import datetime, timezone

from .config import SOURCE_END_DATE, SOURCE_START_DATE, THAILAND_BBOX


def _float(value):
    if value in (None, "", "None"):
        return None
    return float(str(value).strip())


def _iso(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()
    text = str(value).strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _in_bbox(lat, lon):
    b = THAILAND_BBOX
    return b["minlatitude"] <= lat <= b["maxlatitude"] and b["minlongitude"] <= lon <= b["maxlongitude"]


def normalize_tmd(row):
    lat, lon = _float(row["latitude"]), _float(row["longitude"])
    return {
        "source": "tmd", "source_id": str(row["id"]),
        "occurred_at": _iso(row["time_utc"]), "latitude": lat, "longitude": lon,
        "depth_km": _float(row.get("depth_km")), "magnitude": _float(row.get("magnitude")),
        "magnitude_type": None, "place": row.get("place") or "Thailand vicinity",
        "is_in_thailand": _in_bbox(lat, lon),
    }


def normalize_usgs(row):
    props, coords = row.get("properties", {}), row.get("geometry", {}).get("coordinates", [])
    lon, lat = _float(coords[0]), _float(coords[1])
    return {
        "source": "usgs", "source_id": str(row.get("id")),
        "occurred_at": _iso(props.get("time")), "latitude": lat, "longitude": lon,
        "depth_km": _float(coords[2]) if len(coords) > 2 else None,
        "magnitude": _float(props.get("mag")), "magnitude_type": props.get("magType"),
        "place": props.get("place") or "Thailand vicinity", "is_in_thailand": _in_bbox(lat, lon),
    }


def normalize_geofon(row):
    # Header spelling follows the FDSN text standard used by SeisComP.
    lower = {str(k).strip().lower(): v for k, v in row.items()}
    lat, lon = _float(lower.get("latitude")), _float(lower.get("longitude"))
    return {
        "source": "geofon", "source_id": str(lower.get("eventid") or lower.get("event id")),
        "occurred_at": _iso(lower.get("time")), "latitude": lat, "longitude": lon,
        "depth_km": _float(lower.get("depth/km") or lower.get("depth")),
        "magnitude": _float(lower.get("magnitude")),
        "magnitude_type": lower.get("magnitude type") or lower.get("magnitudetype"),
        "place": lower.get("region name") or lower.get("regionname") or "Thailand vicinity",
        "is_in_thailand": _in_bbox(lat, lon),
    }


NORMALIZERS = {"tmd": normalize_tmd, "usgs": normalize_usgs, "geofon": normalize_geofon}


def normalize(source, rows):
    result, rejected = [], []
    for row in rows:
        try:
            result.append(NORMALIZERS[source](row))
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            rejected.append({"source": source, "reason": f"normalize: {exc}", "payload": row})
    return {"events": result, "rejected": rejected}


def validate(events):
    valid, rejected = [], []
    for event in events:
        reasons = []
        if not (-90 <= event["latitude"] <= 90): reasons.append("invalid latitude")
        if not (-180 <= event["longitude"] <= 180): reasons.append("invalid longitude")
        if event["depth_km"] is not None and not (0 <= event["depth_km"] <= 800): reasons.append("invalid depth")
        if event["magnitude"] is None or not (-2 <= event["magnitude"] <= 10): reasons.append("invalid magnitude")
        try: datetime.fromisoformat(event["occurred_at"])
        except (TypeError, ValueError): reasons.append("invalid occurred_at")
        else:
            occurred = datetime.fromisoformat(event["occurred_at"])
            if not (datetime.fromisoformat(SOURCE_START_DATE) <= occurred <= datetime.fromisoformat(SOURCE_END_DATE)):
                reasons.append("outside 2021-2026 scope")
        if not event.get("province"): reasons.append("missing province")
        if reasons:
            rejected.append({"source": event.get("source"), "reason": "; ".join(reasons), "payload": event})
        else:
            present = sum(event.get(k) not in (None, "") for k in ("magnitude", "depth_km", "place"))
            event["quality_score"] = round(0.7 + present * 0.1, 2)
            valid.append(event)
    return valid, rejected


def _distance_km(a, b):
    p1, p2 = math.radians(a["latitude"]), math.radians(b["latitude"])
    dp = p2 - p1
    dl = math.radians(b["longitude"] - a["longitude"])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371 * 2 * math.atan2(math.sqrt(h), math.sqrt(1 - h))


def _uid(event):
    dt = datetime.fromisoformat(event["occurred_at"]).astimezone(timezone.utc)
    # Stable fuzzy fingerprint: minute plus ~1 km coordinate cells.
    key = f"{dt:%Y%m%d%H%M}|{event['latitude']:.2f}|{event['longitude']:.2f}"
    return hashlib.sha256(key.encode()).hexdigest()[:24]


def deduplicate(events, seconds=90, kilometers=25):
    events = sorted(events, key=lambda e: e["occurred_at"])
    merged, duplicate_count = [], 0
    priority = {"tmd": 3, "usgs": 2, "geofon": 1}
    for event in events:
        event_dt = datetime.fromisoformat(event["occurred_at"])
        match = None
        for existing in reversed(merged[-30:]):
            delta = abs((event_dt - datetime.fromisoformat(existing["occurred_at"])).total_seconds())
            if delta <= seconds and _distance_km(event, existing) <= kilometers:
                match = existing
                break
        if match is None:
            item = dict(event)
            item["sources"] = [event["source"]]
            item["source_ids"] = {event["source"]: event["source_id"]}
            item["event_uid"] = _uid(event)
            merged.append(item)
            continue
        duplicate_count += 1
        match["sources"] = sorted(set(match["sources"] + [event["source"]]))
        match["source_ids"][event["source"]] = event["source_id"]
        match["quality_score"] = max(match["quality_score"], event["quality_score"])
        if priority[event["source"]] > priority[match["source"]]:
            for field in ("source", "occurred_at", "latitude", "longitude", "depth_km", "magnitude", "magnitude_type", "place", "province", "is_in_thailand"):
                match[field] = event[field]
    return merged, duplicate_count

