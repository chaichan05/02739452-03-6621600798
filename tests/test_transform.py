from earthquake_etl.boundaries import province_for_point
from earthquake_etl.transform import deduplicate, normalize, validate


def test_usgs_normalization_and_quality():
    raw = [{"id": "x1", "properties": {"time": 1700000000000, "mag": 3.2, "magType": "mb", "place": "Thailand"},
            "geometry": {"coordinates": [100.1, 18.2, 10.0]}}]
    result = normalize("usgs", raw)
    result["events"][0]["province"] = "Chiang Mai"
    valid, rejected = validate(result["events"])
    assert len(valid) == 1
    assert rejected == []
    assert valid[0]["is_in_thailand"] is True


def test_cross_source_duplicates_are_merged():
    base = {"occurred_at": "2026-01-01T00:00:00+00:00", "latitude": 18.0, "longitude": 100.0,
            "depth_km": 10.0, "magnitude": 3.0, "magnitude_type": None,
            "place": "Thailand", "province": "Chiang Mai", "is_in_thailand": True, "quality_score": 1.0}
    a = {**base, "source": "tmd", "source_id": "1"}
    b = {**base, "occurred_at": "2026-01-01T00:00:30+00:00", "latitude": 18.01,
         "source": "usgs", "source_id": "us1"}
    merged, count = deduplicate([a, b])
    assert count == 1
    assert merged[0]["sources"] == ["tmd", "usgs"]


def test_bad_coordinates_are_rejected():
    event = {"source": "x", "source_id": "1", "occurred_at": "2026-01-01T00:00:00+00:00",
             "latitude": 99.0, "longitude": 100.0, "depth_km": 5.0, "magnitude": 2.0,
             "magnitude_type": None, "place": "bad", "province": None, "is_in_thailand": False}
    valid, rejected = validate([event])
    assert not valid
    assert "latitude" in rejected[0]["reason"]


def test_polygon_not_place_name_decides_country_membership():
    boundaries = {"features": [{"properties": {"shapeName": "Test Province"},
                  "geometry": {"type": "Polygon", "coordinates": [[[99, 17], [101, 17], [101, 19], [99, 19], [99, 17]]]}}]}
    assert province_for_point(18.0, 100.0, boundaries) == "Test Province"
    assert province_for_point(18.0, 102.0, boundaries) is None

