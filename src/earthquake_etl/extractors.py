import csv
import io
import re
import time
import urllib.robotparser
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from .config import (
    GEOFON_URL,
    REQUEST_TIMEOUT,
    SOURCE_END_DATE,
    SOURCE_START_DATE,
    THAILAND_BBOX,
    TMD_MAX_PAGES,
    TMD_MAX_ROWS,
    TMD_ROBOTS_URL,
    TMD_URL,
    USER_AGENT,
    USGS_URL,
)

HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json,text/plain,text/html"}


def _time_window():
    start = datetime.fromisoformat(SOURCE_START_DATE)
    end = min(datetime.now(timezone.utc), datetime.fromisoformat(SOURCE_END_DATE))
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%dT%H:%M:%S")


def _robots_allows_tmd(session: requests.Session) -> bool:
    """Honor robots.txt. TMD currently returns a branded no-rules 404 page."""
    response = session.get(TMD_ROBOTS_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(TMD_ROBOTS_URL)
    parser.parse(response.text.splitlines())
    return parser.can_fetch(USER_AGENT, TMD_URL)


def extract_tmd():
    """Scrape a small bounded set of public HTML pages (no Selenium)."""
    with requests.Session() as session:
        if not _robots_allows_tmd(session):
            raise PermissionError("TMD robots.txt does not permit this scraper")
        rows, seen = [], set()
        for page in range(TMD_MAX_PAGES):
            time.sleep(1.0)
            response = session.get(
                TMD_URL,
                params={"ps": TMD_MAX_ROWS, "pageNum_thaievent": page},
                headers=HEADERS,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")
            added = 0
            for tr in soup.select("tr.tbis_leq1, tr.tbis_leq2, tr.tbis_leq3"):
                cells = tr.find_all("td", recursive=False)
                if len(cells) < 7:
                    continue
                onclick = tr.get("onclick", "")
                event_match = re.search(r"/EQ(\d+)", onclick)
                utc_match = re.search(
                    r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s*UTC",
                    cells[0].get_text(" ", strip=True),
                )
                if not utc_match:
                    continue
                event_id = event_match.group(1) if event_match else utc_match.group(1)
                if event_id in seen:
                    continue
                seen.add(event_id)
                added += 1
                location_parts = [s.strip() for s in cells[6].stripped_strings if s.strip()]
                rows.append({
                    "id": event_id,
                    "time_utc": utc_match.group(1),
                    "magnitude": cells[1].get_text(" ", strip=True),
                    "latitude": cells[2].get_text(" ", strip=True),
                    "longitude": cells[3].get_text(" ", strip=True),
                    "depth_km": cells[4].get_text(" ", strip=True),
                    "phase_count": cells[5].get_text(" ", strip=True),
                    "place": " / ".join(dict.fromkeys(location_parts)),
                })
            if added == 0:
                break
    if not rows:
        raise ValueError("TMD page structure changed: no event rows found")
    return rows


def extract_usgs():
    start, end = _time_window()
    params = {
        "format": "geojson",
        "starttime": start,
        "endtime": end,
        "eventtype": "earthquake",
        "orderby": "time-asc",
        "limit": 20000,
        **THAILAND_BBOX,
    }
    response = requests.get(USGS_URL, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json().get("features", [])


def extract_geofon():
    start, end = _time_window()
    params = {
        "format": "text",
        "start": start,
        "end": end,
        "minlat": THAILAND_BBOX["minlatitude"],
        "maxlat": THAILAND_BBOX["maxlatitude"],
        "minlon": THAILAND_BBOX["minlongitude"],
        "maxlon": THAILAND_BBOX["maxlongitude"],
        "orderby": "time-asc",
    }
    response = requests.get(GEOFON_URL, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    if response.status_code == 204:
        return []
    response.raise_for_status()
    # FDSN text is pipe-delimited; comments start with '#'.
    lines = [line.lstrip("#").strip() for line in response.text.splitlines() if line.strip()]
    if not lines:
        return []
    return list(csv.DictReader(io.StringIO("\n".join(lines)), delimiter="|"))


EXTRACTORS = {"tmd": extract_tmd, "usgs": extract_usgs, "geofon": extract_geofon}

