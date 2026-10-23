import os

TMD_URL = "https://earthquake.tmd.go.th/inside.html"
TMD_ROBOTS_URL = "https://earthquake.tmd.go.th/robots.txt"
USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
GEOFON_URL = "https://geofon.gfz.de/fdsnws/event/1/query"
USER_AGENT = "CMU-BigData-StudentProject/1.0 (academic; no-personal-data)"

# Bounding box used by the public APIs. Exact political borders are handled by
# the dashboard label; the assignment intentionally studies Thailand vicinity.
THAILAND_BBOX = {"minlatitude": 5.5, "maxlatitude": 20.6,
                 "minlongitude": 97.3, "maxlongitude": 105.7}
REQUEST_TIMEOUT = (10, 45)
# Fixed assignment scope: Buddhist years 2564-2569 (Gregorian 2021-2026).
SOURCE_START_DATE = "2021-01-01T00:00:00+00:00"
SOURCE_END_DATE = "2026-12-31T23:59:59+00:00"
TMD_MAX_ROWS = min(int(os.getenv("TMD_MAX_ROWS", "200")), 200)
TMD_MAX_PAGES = min(int(os.getenv("TMD_MAX_PAGES", "5")), 5)
DB_URL = os.environ["EARTHQUAKE_DB_URL"]
