"""Dashboard: Notes + Small Win stars + optional Weather and Oura tiles. Stdlib only, additive to park_server.py.
Data: <data_dir>/dashboard.json (see config.py).
Stars: only ever added, never removed or scored. Max 3 per day: 1 'day' star (carries the small win) + up to 2 'extra'.
Notes: from a helper to the owner; status open | answered | later | tucked. Star offers are notes with offer=true.
"""
import json, os, uuid, datetime, threading

HERE = os.path.dirname(os.path.abspath(__file__))
import config
DIR = config.data_dir()
DATA = os.path.join(DIR, "dashboard.json")
LOCK = threading.Lock()
MAX_STARS = 3
GENTLE_DEFAULT = [
    "Drink a full glass of water.",
    "Five things: find 5 things that belong somewhere else and put them there.",
    "Stand up and stretch for one song.",
    "Step outside for two minutes of air.",
    "Clear one surface. Just one.",
    "Ten-minute tidy timer. Stop when it rings.",
    "Put on something comfortable.",
    "Eat something with protein.",
    "Take the trash out of one room.",
    "Wipe one counter.",
    "Start a load of laundry, or move one along.",
    "Three slow breaths and a shoulder roll.",
    "Walk to the mailbox, or around the yard.",
    "Stretch whatever feels tight, gently.",
]
DEFAULT = {"extra_list": ["Shower", "Walk or stretch", "Handled a scary thing"], "notes": [], "stars": [], "wins": [],
           "gentle_list": GENTLE_DEFAULT, "gentle_log": []}


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def today():
    return datetime.date.today().isoformat()


def load():
    try:
        with open(DATA, encoding="utf-8") as f:
            d = json.load(f)
    except FileNotFoundError:
        d = {}
    for k, v in DEFAULT.items():
        d.setdefault(k, json.loads(json.dumps(v)))
    return d


def save(d):
    os.makedirs(DIR, exist_ok=True)
    tmp = DATA + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
    os.replace(tmp, DATA)


def add_note(text, by="helper", offer=False):
    with LOCK:
        d = load()
        n = {"id": uuid.uuid4().hex[:8], "text": text.strip()[:600], "by": by[:20], "offer": bool(offer),
             "status": "open", "reply": "", "created": now(), "updated": now()}
        d["notes"].append(n)
        save(d)
        return n


def view():
    d = load()
    t = today()
    d["today"] = t
    d["owner"] = config.CFG["owner_name"]
    d["helper"] = config.CFG["helper_name"]
    d["today_stars"] = [s for s in d["stars"] if s["date"] == t]
    d["notes"] = [n for n in d["notes"] if n["status"] != "tucked"]
    return d


# ---- Oura (read-only, cached) ------------------------------------------------
OURA_TTL = 45 * 60
OURA_CACHE = os.path.join(DIR, "oura_cache.json")
OURA_LOCK = threading.Lock()
_oa = None


def _oura_mod():
    """Load the optional adapter named in config (a Python file exposing api(path, params) -> dict).
    Secrets stay inside the adapter and are never part of this project."""
    global _oa
    if _oa is None:
        import importlib.util
        path = os.path.expanduser(config.CFG["oura_adapter"])
        spec = importlib.util.spec_from_file_location("oura_adapter", path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _oa = m
    return _oa


def _oura_fetch():
    oa = _oura_mod()
    end = datetime.date.today() + datetime.timedelta(days=1)
    start = end - datetime.timedelta(days=9)
    p = {"start_date": start.isoformat(), "end_date": end.isoformat()}
    rd = {x["day"]: x for x in oa.api("daily_readiness", p).get("data", [])}
    ds = {x["day"]: x for x in oa.api("daily_sleep", p).get("data", [])}
    act = {x["day"]: x for x in oa.api("daily_activity", p).get("data", [])}
    sl = {}
    for x in oa.api("sleep", p).get("data", []):
        if x.get("type") == "long_sleep" or x["day"] not in sl:
            sl[x["day"]] = x
    if not (rd or ds or sl or act):
        raise RuntimeError("empty response")

    def hrs(d):
        t = (sl.get(d) or {}).get("total_sleep_duration")
        return round(t / 3600, 1) if t else None

    t = today()
    night = None
    if t in sl or t in ds:
        s = sl.get(t) or {}
        night = {"day": t, "sleep_hours": hrs(t), "sleep_score": (ds.get(t) or {}).get("score"),
                 "readiness": (rd.get(t) or {}).get("score"), "hrv": s.get("average_hrv"),
                 "resting_hr": s.get("lowest_heart_rate")}
    a = act.get(t)
    today_act = {"steps": a.get("steps"), "active_calories": a.get("active_calories")} if a and a.get("steps") else None
    days = [(datetime.date.today() - datetime.timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    last7 = [{"day": d, "sleep_hours": hrs(d), "hrv": (sl.get(d) or {}).get("average_hrv"),
              "readiness": (rd.get(d) or {}).get("score"), "resting_hr": (sl.get(d) or {}).get("lowest_heart_rate")}
             for d in days]
    if night and night["sleep_hours"]:
        h, r = night["sleep_hours"], night["readiness"]
        if h < 6.5 or (r is not None and r < 70):
            note = f"About {h:g}h of sleep. Body's recovering, so go gentle today."
        else:
            note = f"About {h:g}h of sleep. A steady base for today."
    else:
        note = "Last night isn't synced yet. Opening the Oura app on your phone usually brings it in."
    return {"synced": bool(night), "night": night, "today": today_act, "last7": last7, "note": note,
            "fetched": now(), "stale": False}


def oura_view():
    if not config.CFG["oura_adapter"]:
        return 200, {"enabled": False}
    with OURA_LOCK:
        cache = None
        try:
            with open(OURA_CACHE, encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            pass
        if cache and cache.get("fetched_day") == today():
            age = (datetime.datetime.now() - datetime.datetime.fromisoformat(cache["fetched"])).total_seconds()
            # a not-yet-synced night is re-checked sooner, so it appears once the phone syncs
            if age < (OURA_TTL if cache.get("synced") else 5 * 60):
                return 200, cache
        try:
            d = _oura_fetch()
            d["fetched_day"] = today()
            os.makedirs(DIR, exist_ok=True)
            tmp = OURA_CACHE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False)
            os.replace(tmp, OURA_CACHE)
            return 200, d
        except Exception:
            if cache:
                cache["stale"] = True
                return 200, cache
            return 200, {"synced": False, "night": None, "today": None, "last7": [], "stale": True,
                         "note": "Oura isn't answering right now. Try again in a little while."}


# ---- Weather (Open-Meteo, no key, city-level coordinates, cached) -------------
WX_TTL = 60 * 60
WX_CACHE = os.path.join(DIR, "weather_cache.json")
WX_LOCK = threading.Lock()
def _wx_cfg():
    return config.CFG["weather"]


def _wx_url():
    w = _wx_cfg()
    import urllib.parse
    return ("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s" % (w["latitude"], w["longitude"]) +
            "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max"
            "&current=apparent_temperature,temperature_2m&temperature_unit=fahrenheit&wind_speed_unit=mph"
            "&timezone=" + urllib.parse.quote(w.get("timezone") or "auto", safe="") + "&forecast_days=7")


def _wx_kind(c):
    if c in (0, 1):
        return "clear"
    if c in (2, 3):
        return "cloudy"
    if c in (45, 48):
        return "fog"
    if c in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return "rain"
    if c in (71, 73, 75, 77, 85, 86):
        return "snow"
    if c in (95, 96, 99):
        return "storm"
    return "cloudy"


def _wx_fetch():
    import urllib.request
    with urllib.request.urlopen(_wx_url(), timeout=20) as r:
        j = json.load(r)
    dy = j["daily"]
    days = [{"day": dy["time"][i], "kind": _wx_kind(dy["weather_code"][i]),
             "hi": round(dy["temperature_2m_max"][i]), "lo": round(dy["temperature_2m_min"][i]),
             "rain": dy["precipitation_probability_max"][i], "wind": round(dy["wind_speed_10m_max"][i])}
            for i in range(len(dy["time"]))]
    t = days[0]
    feels = round(j["current"]["apparent_temperature"])
    tips = []
    if t["rain"] is not None and t["rain"] >= 40:
        tips.append("rain looks likely, so an umbrella or rain jacket")
    if t["lo"] <= 40 or feels <= 45:
        tips.append("a warm layer")
    if t["wind"] >= 20:
        tips.append("it's windy")
    if t["kind"] == "storm":
        tips.append("storms are possible, so keep plans flexible")
    if t["hi"] >= 90:
        tips.append("water and shade")
    note = f"Feels like {feels}°F right now; today's high is {t['hi']}°." + (" Maybe: " + ", ".join(tips) + "." if tips else "")
    return {"days": days, "note": note, "place": _wx_cfg().get("place") or "", "fetched": now(), "stale": False}


def weather_view():
    w = _wx_cfg()
    if not (w.get("enabled") and w.get("latitude") is not None and w.get("longitude") is not None):
        return 200, {"enabled": False}
    with WX_LOCK:
        cache = None
        try:
            with open(WX_CACHE, encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            pass
        if cache:
            age = (datetime.datetime.now() - datetime.datetime.fromisoformat(cache["fetched"])).total_seconds()
            if age < WX_TTL and cache["days"] and cache["days"][0]["day"] == today():
                return 200, cache
        try:
            d = _wx_fetch()
            os.makedirs(DIR, exist_ok=True)
            tmp = WX_CACHE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False)
            os.replace(tmp, WX_CACHE)
            return 200, d
        except Exception:
            if cache:
                cache["stale"] = True
                return 200, cache
            return 200, {"days": [], "note": "The forecast isn't answering right now. Try again in a little while.",
                         "place": _wx_cfg().get("place") or "", "stale": True}


# ---- One gentle thing: one small suggested step a day. Never graded, skipping is fine. ----
def _gentle_pick(d, extra=0):
    import hashlib
    lst = [x for x in d["gentle_list"] if x.strip()]
    if not lst:
        return ""
    recent = [e["text"] for e in d["gentle_log"][-5:]]
    pool = [x for x in lst if x not in recent] or lst
    h = int(hashlib.sha256(f"{today()}:{extra}".encode()).hexdigest(), 16)
    return pool[h % len(pool)]


def _gentle_today(d):
    """Return today's log entry, creating it from the list when none exists yet."""
    t = today()
    cur = next((e for e in reversed(d["gentle_log"]) if e["date"] == t), None)
    if cur is None:
        txt = _gentle_pick(d)
        if not txt:
            return None
        cur = {"date": t, "text": txt, "status": "open", "swaps": 0, "at": now()}
        d["gentle_log"].append(cur)
    return cur


def gentle_state(d):
    cur = _gentle_today(d)
    t = today()
    mine = [s for s in d["stars"] if s["date"] == t]
    return {"item": cur, "can_star": bool(cur and cur["status"] == "done" and len(mine) < MAX_STARS
                                         and sum(s["kind"] == "extra" for s in mine) < 2
                                         and not any(s.get("label") == cur["text"][:80] for s in mine)),
            "list": d["gentle_list"]}


def gentle_act(body):
    act = body.get("action")
    with LOCK:
        d = load()
        cur = _gentle_today(d)
        if act == "add":
            txt = (body.get("text") or "").strip()[:140]
            if not txt:
                return 400, {"error": "text required"}
            if txt not in d["gentle_list"]:
                d["gentle_list"].append(txt)
        elif act == "remove":
            d["gentle_list"] = [x for x in d["gentle_list"] if x != body.get("text")]
        elif cur is None:
            return 400, {"error": "the list is empty"}
        elif act == "done":
            cur["status"], cur["done_at"] = "done", now()
        elif act == "skip":
            cur["status"] = "skipped"
        elif act == "another":
            if cur["status"] == "done":
                return 400, {"error": "that one is already done"}
            cur["swaps"] += 1
            cur["text"] = _gentle_pick(d, extra=cur["swaps"] + 1) or cur["text"]
            cur["status"] = "open"
        elif act == "undo":
            cur["status"] = "open"
        else:
            return 400, {"error": "unknown action"}
        save(d)
        return 200, gentle_state(d)


def handle(method, path, body):
    """Return (code, payload, ctype) or None if not ours."""
    if method == "GET" and path == "/api/dash/gentle":
        with LOCK:
            d = load()
            st = gentle_state(d)
            save(d)
        return 200, st, "application/json"
    if method == "POST" and path == "/api/dash/gentle":
        c, p = gentle_act(body)
        return c, p, "application/json"
    if method == "GET" and path == "/api/weather":
        c, d = weather_view()
        return c, d, "application/json"
    if method == "GET" and path == "/api/oura":
        c, d = oura_view()
        return c, d, "application/json"
    if method == "GET" and path == "/dash-manifest.json":
        return 200, {"name": (config.CFG["owner_name"] + "'s Dashboard") if config.CFG["owner_name"] else "Dashboard", "short_name": "Dashboard", "start_url": "/dashboard",
                     "scope": "/", "display": "standalone", "background_color": "#1b2a3a",
                     "theme_color": "#2b2347",
                     "icons": [{"src": "/dash-icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
                               {"src": "/dash-icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}]}, "application/manifest+json"
    if method == "GET" and path in ("/dash-icon-192.png", "/dash-icon-512.png", "/apple-touch-icon.png"):
        with open(os.path.join(HERE, path.lstrip("/")), "rb") as f:
            return 200, f.read(), "image/png"
    if method == "GET" and path in ("/dashboard", "/dashboard/"):
        with open(os.path.join(HERE, "dashboard.html"), "rb") as f:
            return 200, f.read(), "text/html"
    if method == "GET" and path == "/api/dash":
        return 200, view(), "application/json"
    if method == "POST" and path == "/api/dash/win":
        text = (body.get("text") or "").strip()[:300]
        with LOCK:
            d = load()
            t = today()
            d["wins"] = [w for w in d["wins"] if w["date"] != t]
            if text:
                d["wins"].append({"date": t, "text": text, "at": now()})
            save(d)
        return 200, {"ok": True}, "application/json"
    if method == "POST" and path == "/api/dash/star":
        kind = "extra" if body.get("kind") == "extra" else "day"
        label = (body.get("label") or "").strip()[:80]
        with LOCK:
            d = load()
            t = today()
            mine = [s for s in d["stars"] if s["date"] == t]
            if len(mine) >= MAX_STARS:
                return 400, {"error": "that's all three stars for today"}, "application/json"
            if kind == "day" and any(s["kind"] == "day" for s in mine):
                return 400, {"error": "today's star is already placed"}, "application/json"
            if kind == "extra" and sum(s["kind"] == "extra" for s in mine) >= 2:
                return 400, {"error": "both extra stars are placed"}, "application/json"
            s = {"id": uuid.uuid4().hex[:8], "date": t, "kind": kind, "label": label, "at": now()}
            d["stars"].append(s)
            save(d)
        return 201, s, "application/json"
    if method == "POST" and path == "/api/dash/notes":
        if not (body.get("text") or "").strip():
            return 400, {"error": "text required"}, "application/json"
        return 201, add_note(body["text"], body.get("by") or "helper", body.get("offer")), "application/json"
    if method == "POST" and path.startswith("/api/dash/notes/"):
        nid = path.rsplit("/", 1)[-1]
        st = body.get("status")
        if st not in ("open", "answered", "later", "tucked"):
            return 400, {"error": "bad status"}, "application/json"
        with LOCK:
            d = load()
            for n in d["notes"]:
                if n["id"] == nid:
                    n["status"], n["updated"] = st, now()
                    if "reply" in body:
                        n["reply"] = str(body["reply"])[:600]
                    save(d)
                    return 200, n, "application/json"
        return 404, {"error": "no such note"}, "application/json"
    return None
