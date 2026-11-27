"""Settings for the Parking Lot + Dashboard. Stdlib only.
Reads config.json next to this file (or the file named by $PARKING_CONFIG). Missing keys use the defaults below.
$DASH_DATA_DIR overrides data_dir (handy for tests).
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULTS = {
    "data_dir": "data",          # where your JSON files live (relative paths are relative to this folder)
    "port": 8765,
    "owner_name": "",            # shown as "Hello, <name>" on the dashboard (optional)
    "helper_name": "",           # label for the notes tile, e.g. "Sam" gives "Sam's Notes" (optional)
    "weather": {"enabled": False, "latitude": None, "longitude": None, "place": "", "timezone": "America/Chicago"},
    "oura_adapter": "",          # optional path to a Python file with api(path, params); see oura_adapter.example.py
}


def _load():
    cfg = json.loads(json.dumps(DEFAULTS))
    path = os.environ.get("PARKING_CONFIG") or os.path.join(HERE, "config.json")
    try:
        with open(path, encoding="utf-8") as f:
            user = json.load(f)
    except FileNotFoundError:
        user = {}
    for k, v in user.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k].update(v)
        else:
            cfg[k] = v
    return cfg


CFG = _load()


def data_dir():
    d = os.environ.get("DASH_DATA_DIR") or CFG["data_dir"]
    d = os.path.expanduser(d)
    return d if os.path.isabs(d) else os.path.join(HERE, d)
