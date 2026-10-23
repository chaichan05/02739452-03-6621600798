from datetime import datetime, timedelta, timezone

from airflow.decorators import dag, task
from airflow.utils.task_group import TaskGroup
from airflow.utils.trigger_rule import TriggerRule

from earthquake_etl.boundaries import filter_and_enrich, prepare_thailand_boundaries
from earthquake_etl.database import load_quality_failure, load_success, start_pipeline_run
from earthquake_etl.extractors import EXTRACTORS
from earthquake_etl.io_utils import read_json, write_json
from earthquake_etl.transform import deduplicate, normalize, validate


DEFAULT_ARGS = {"owner": "6621600798", "retries": 2, "retry_delay": timedelta(minutes=2)}


@dag(
    dag_id="thailand_earthquake_etl",
    description="TMD + USGS + GEOFON resilient earthquake ETL",
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    schedule="0 1 * * *",
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["earthquake", "level-3", "6621600798"],
)
def earthquake_etl():
    @task
    def begin(**context):
        run_id = context["run_id"]
        start_pipeline_run(run_id)
        return run_id

    run_id = begin()

    @task
    def prepare_boundaries():
        return prepare_thailand_boundaries()

    boundary_path = prepare_boundaries()

    def source_group(source):
        with TaskGroup(group_id=f"{source}_pipeline", tooltip=f"Extract and transform {source.upper()}"):
            @task(task_id="extract")
            def extract(run_id_value, source_name):
                try:
                    rows = EXTRACTORS[source_name]()
                    payload = {"ok": True, "source": source_name, "rows": rows, "error": None}
                except Exception as exc:  # isolation is deliberate: one source must not stop the DAG
                    payload = {"ok": False, "source": source_name, "rows": [],
                               "error": f"{type(exc).__name__}: {exc}"}
                return write_json(f"{run_id_value.replace(':', '_')}_{source_name}_raw.json", payload)

            @task(task_id="transform")
            def transform(raw_path, run_id_value, source_name, boundary_file):
                raw = read_json(raw_path)
                transformed = normalize(source_name, raw["rows"])
                scoped, outside = filter_and_enrich(transformed["events"], boundary_file)
                transformed["events"] = scoped
                transformed["status"] = {"ok": raw["ok"], "count": len(raw["rows"]),
                                         "inside_count": len(scoped), "outside_count": len(outside),
                                         "error": raw["error"]}
                return write_json(f"{run_id_value.replace(':', '_')}_{source_name}_normalized.json", transformed)

            return transform(extract(run_id, source), run_id, source, boundary_path)

    # Three TaskGroups are independent and therefore execute in parallel.
    source_outputs = [source_group(name) for name in ("tmd", "usgs", "geofon")]

    @task(trigger_rule=TriggerRule.ALL_DONE)
    def merge_and_check(paths, run_id_value):
        all_events, rejected, statuses, extracted = [], [], {}, 0
        for path in paths:
            if not path:
                continue
            result = read_json(path)
            all_events.extend(result["events"])
            rejected.extend(result["rejected"])
            source = path.rsplit("_", 2)[-2] if False else None
            # Source is reliably present on every normalized event; empty sources use filename.
            filename = path.replace("\\", "/").split("/")[-1]
            source = next((s for s in ("tmd", "usgs", "geofon") if f"_{s}_normalized" in filename), "unknown")
            statuses[source] = result["status"]
            extracted += result["status"]["count"]

        valid, invalid = validate(all_events)
        rejected.extend(invalid)
        merged, dupes = deduplicate(valid)
        ratio = len(valid) / max(len(all_events), 1)
        thailand_count = len(merged)
        all_have_province = all(bool(e.get("province")) for e in merged)
        enough = thailand_count >= 100 and all_have_province
        passed = ratio >= 0.95 and enough
        quality_message = (f"valid_ratio={ratio:.3f}; merged_rows={len(merged)}; "
                           f"thailand_rows={thailand_count}; minimum_thailand_rows=100")
        payload = {
            "events": merged, "rejected": rejected, "source_status": statuses,
            "extracted_count": extracted, "duplicate_count": dupes,
            "quality_passed": passed, "quality_message": quality_message,
        }
        return write_json(f"{run_id_value.replace(':', '_')}_merged.json", payload)

    merged_path = merge_and_check(source_outputs, run_id)

    @task.branch
    def quality_gate(path):
        return "load_valid_events" if read_json(path)["quality_passed"] else "quarantine_invalid_batch"

    @task
    def load_valid_events(path, run_id_value):
        return load_success(run_id_value, read_json(path))

    @task
    def quarantine_invalid_batch(path, run_id_value):
        result = read_json(path)
        load_quality_failure(run_id_value, result)
        return result["quality_message"]

    @task(trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS)
    def finish():
        return "pipeline completed"

    choice = quality_gate(merged_path)
    good = load_valid_events(merged_path, run_id)
    bad = quarantine_invalid_batch(merged_path, run_id)
    choice >> [good, bad]
    [good, bad] >> finish()


earthquake_etl()

