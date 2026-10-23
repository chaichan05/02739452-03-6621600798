import json
from pathlib import Path

DATA_DIR = Path("/opt/airflow/data")


def write_json(name: str, payload) -> str:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / name
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")
    temp.replace(path)
    return str(path)


def read_json(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))
