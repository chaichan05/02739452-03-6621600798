from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import Json, execute_batch

from .config import DB_URL


UPSERT_SQL = """
INSERT INTO earthquake_events (
  event_uid, occurred_at, latitude, longitude, depth_km, magnitude,
  magnitude_type, place, province, is_in_thailand, sources, source_ids, quality_score
) VALUES (
  %(event_uid)s, %(occurred_at)s, %(latitude)s, %(longitude)s, %(depth_km)s,
  %(magnitude)s, %(magnitude_type)s, %(place)s, %(province)s, %(is_in_thailand)s,
  %(sources)s, %(source_ids)s, %(quality_score)s
)
ON CONFLICT (event_uid) DO UPDATE SET
  occurred_at = EXCLUDED.occurred_at,
  latitude = EXCLUDED.latitude,
  longitude = EXCLUDED.longitude,
  depth_km = EXCLUDED.depth_km,
  magnitude = EXCLUDED.magnitude,
  magnitude_type = COALESCE(EXCLUDED.magnitude_type, earthquake_events.magnitude_type),
  place = COALESCE(EXCLUDED.place, earthquake_events.place),
  province = EXCLUDED.province,
  is_in_thailand = EXCLUDED.is_in_thailand,
  sources = (SELECT ARRAY(SELECT DISTINCT unnest(earthquake_events.sources || EXCLUDED.sources) ORDER BY 1)),
  source_ids = earthquake_events.source_ids || EXCLUDED.source_ids,
  quality_score = GREATEST(earthquake_events.quality_score, EXCLUDED.quality_score),
  updated_at = NOW()
"""


def start_pipeline_run(run_id):
    with psycopg2.connect(DB_URL) as conn, conn.cursor() as cur:
        cur.execute("ALTER TABLE earthquake_events ADD COLUMN IF NOT EXISTS province TEXT")
        cur.execute(
            """INSERT INTO pipeline_runs(run_id, started_at, status)
               VALUES (%s, %s, 'running')
               ON CONFLICT (run_id) DO UPDATE SET started_at=EXCLUDED.started_at,
                 finished_at=NULL, status='running', message=NULL""",
            (run_id, datetime.now(timezone.utc)),
        )


def _load_rejected(cur, run_id, rejected):
    if not rejected:
        return
    cur.execute("DELETE FROM rejected_events WHERE run_id=%s", (run_id,))
    execute_batch(
        cur,
        "INSERT INTO rejected_events(run_id, source, reason, payload) VALUES (%s,%s,%s,%s)",
        [(run_id, r.get("source"), r["reason"], Json(r.get("payload", {}))) for r in rejected],
        page_size=200,
    )


def load_success(run_id, result):
    with psycopg2.connect(DB_URL) as conn, conn.cursor() as cur:
        rows = []
        for event in result["events"]:
            item = dict(event)
            item["source_ids"] = Json(item["source_ids"])
            rows.append(item)
        if rows:
            execute_batch(cur, UPSERT_SQL, rows, page_size=200)
            if all(v["ok"] for v in result["source_status"].values()):
                # A fully healthy run replaces the analytical scope, removing old
                # bbox-only or out-of-period rows left by earlier project versions.
                cur.execute("DELETE FROM earthquake_events WHERE NOT (event_uid = ANY(%s))",
                            ([event["event_uid"] for event in result["events"]],))
        _load_rejected(cur, run_id, result["rejected"])
        cur.execute(
            """UPDATE pipeline_runs SET finished_at=NOW(), status=%s,
               source_status=%s, extracted_count=%s, valid_count=%s,
               rejected_count=%s, duplicate_count=%s, upserted_count=%s,
               message=%s WHERE run_id=%s""",
            (
                "success" if all(v["ok"] for v in result["source_status"].values()) else "degraded",
                Json(result["source_status"]), result["extracted_count"], len(result["events"]),
                len(result["rejected"]), result["duplicate_count"], len(rows),
                "UPSERT complete; repeat runs do not add identical event_uid values", run_id,
            ),
        )
    return len(rows)


def load_quality_failure(run_id, result):
    with psycopg2.connect(DB_URL) as conn, conn.cursor() as cur:
        _load_rejected(cur, run_id, result["rejected"])
        cur.execute(
            """UPDATE pipeline_runs SET finished_at=NOW(), status='quality_failed',
               source_status=%s, extracted_count=%s, valid_count=%s,
               rejected_count=%s, duplicate_count=%s, message=%s WHERE run_id=%s""",
            (Json(result["source_status"]), result["extracted_count"], len(result["events"]),
             len(result["rejected"]), result["duplicate_count"], result["quality_message"], run_id),
        )

