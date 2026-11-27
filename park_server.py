"""Parking Lot: tiny LAN web app + JSON store. Stdlib only.
Data: <data_dir>/parking_lot.json  (see config.py; default ./data)
API:  GET /api/items | POST /api/items {text, by} | POST /api/items/<id> {status: parked|forward|done}
      DELETE /api/items/<id>
CLI:  python park_server.py add "text" [by]   |  python park_server.py list   |  python park_server.py serve
"""
import json, os, sys, uuid, datetime, threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
DATA = os.path.join(config.data_dir(), "parking_lot.json")
HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PARK_PORT") or config.CFG["port"])
import dash  # dashboard v0 (notes + stars)
LOCK = threading.Lock()


def load():
    try:
        with open(DATA, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"items": []}


def save(d):
    tmp = DATA + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
    os.replace(tmp, DATA)


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


STICK = os.path.join(os.path.dirname(DATA), "stickers.json")
DEFAULT_REWARDS = [
    {"id": "story", "emoji": "📖", "text": "An hour with a good book"},
    {"id": "choc", "emoji": "🍫", "text": "A treat of your choice"},
    {"id": "sheet", "emoji": "✨", "text": "A new sheet of real stickers"},
    {"id": "late", "emoji": "🌙", "text": "A slow, unscheduled evening"},
    {"id": "pick", "emoji": "🎀", "text": "Your pick"},
]


def sload():
    try:
        with open(STICK, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"goal": 10, "stickers": [], "claims": [], "rewards": DEFAULT_REWARDS}


def ssave(d):
    tmp = STICK + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
    os.replace(tmp, STICK)


def sview():
    d = sload()
    d["progress"] = len(d["stickers"]) - d["goal"] * len(d["claims"])
    return d


def award(reason, emoji="🌟"):
    with LOCK:
        d = sload()
        s = {"id": uuid.uuid4().hex[:8], "emoji": emoji, "reason": reason.strip()[:200], "at": now()}
        d["stickers"].append(s)
        ssave(d)
        return s


def add(text, by="me"):
    with LOCK:
        d = load()
        item = {"id": uuid.uuid4().hex[:8], "text": text.strip()[:500], "by": by[:20],
                "status": "parked", "created": now(), "updated": now()}
        d["items"].append(item)
        save(d)
        return item


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        b = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def log_message(self, *a):
        pass

    def _dash(self, method):
        try:
            b = self._body() if method == "POST" else {}
        except Exception:
            self._send(400, {"error": "bad json"})
            return True
        r = dash.handle(method, self.path, b)
        if r is None:
            return False
        self._send(*r)
        return True

    def do_GET(self):
        if self._dash("GET"):
            return
        if self.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                return self._send(200, f.read(), "text/html")
        if self.path == "/manifest.json":
            return self._send(200, {"name": "Parking Lot", "short_name": "Parking", "start_url": "/",
                                    "display": "standalone", "background_color": "#fdf2f8",
                                    "theme_color": "#f9a8d4"})
        if self.path == "/api/items":
            return self._send(200, load())
        if self.path == "/api/stickers":
            return self._send(200, sview())
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path.startswith("/api/dash") and self._dash("POST"):
            return
        try:
            b = self._body()
        except Exception:
            return self._send(400, {"error": "bad json"})
        if self.path == "/api/claim":
            with LOCK:
                d = sload()
                prog = len(d["stickers"]) - d["goal"] * len(d["claims"])
                r = next((x for x in d["rewards"] if x["id"] == b.get("reward")), None)
                if not r:
                    return self._send(400, {"error": "no such reward"})
                if prog < d["goal"]:
                    return self._send(400, {"error": "not enough stickers yet"})
                c = {"reward": r["id"], "text": r["text"], "at": now()}
                d["claims"].append(c)
                ssave(d)
                return self._send(200, c)
        if self.path == "/api/items":
            if not (b.get("text") or "").strip():
                return self._send(400, {"error": "text required"})
            return self._send(201, add(b["text"], b.get("by") or "me"))
        if self.path.startswith("/api/items/"):
            iid = self.path.rsplit("/", 1)[-1]
            st = b.get("status")
            if st not in ("parked", "forward", "done"):
                return self._send(400, {"error": "bad status"})
            with LOCK:
                d = load()
                for it in d["items"]:
                    if it["id"] == iid:
                        it["status"], it["updated"] = st, now()
                        save(d)
                        return self._send(200, it)
            return self._send(404, {"error": "no such item"})
        self._send(404, {"error": "not found"})

    def do_DELETE(self):
        if self.path.startswith("/api/items/"):
            iid = self.path.rsplit("/", 1)[-1]
            with LOCK:
                d = load()
                n = len(d["items"])
                d["items"] = [i for i in d["items"] if i["id"] != iid]
                save(d)
            return self._send(200 if len(d["items"]) < n else 404, {"ok": len(d["items"]) < n})
        self._send(404, {"error": "not found"})


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"
    if cmd == "add":
        print(json.dumps(add(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "me"), ensure_ascii=True))
    elif cmd == "sticker":
        print(json.dumps(award(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "🌟"), ensure_ascii=True))
    elif cmd == "stickers":
        v = sview()
        print("total", len(v["stickers"]), "progress", v["progress"], "/", v["goal"], "claims", len(v["claims"]))
        for s in v["stickers"]:
            print(s["at"][:10], "|", s["reason"].encode("ascii", "replace").decode())
    elif cmd == "list":
        for i in load()["items"]:
            print(i["id"], i["status"], i["by"], "|", i["text"].encode("ascii", "replace").decode())
    else:
        ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
