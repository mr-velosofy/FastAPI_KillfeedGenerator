import asyncio
import logging
import os
import threading
import time
import urllib.parse
import uuid

log = logging.getLogger("stats")

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

ONLINE_WINDOW = 180.0
PREVIEW_THROTTLE = 10.0
EVENT_FLUSH_INTERVAL = 30.0
PREVIEW_WEIGHT = 0.2


def _repair_db_url(url):
    if "://" not in url or "@" not in url:
        return url
    scheme, rest = url.split("://", 1)
    userinfo, hostpart = rest.rsplit("@", 1)
    if ":" not in userinfo:
        return url
    user, pwd = userinfo.split(":", 1)
    encoded = f"{scheme}://{urllib.parse.quote(user, safe='')}:{urllib.parse.quote(pwd, safe='')}@{hostpart}"
    if encoded != url:
        log.info("stats: repaired DATABASE_URL (encoded credentials)")
    return encoded


if DATABASE_URL:
    DATABASE_URL = _repair_db_url(DATABASE_URL)
    os.environ["DATABASE_URL"] = DATABASE_URL

enabled = bool(DATABASE_URL)

_presence = {}
_presence_lock = threading.Lock()
_last_preview = {}
_public_cache = {"at": 0.0, "data": {"online": 0, "today": 0}}

_event_buf = []
_event_buf_lock = threading.Lock()


def ensure_vid(raw):
    if raw and len(raw) == 36:
        return raw, False
    return str(uuid.uuid4()), True


def _sweep(now):
    cutoff = now - ONLINE_WINDOW
    for k in [k for k, t in _presence.items() if t < cutoff]:
        del _presence[k]


def heartbeat(vid):
    now = time.monotonic()
    with _presence_lock:
        _presence[vid] = now
        _sweep(now)
        return len(_presence)


def online_now():
    with _presence_lock:
        _sweep(time.monotonic())
        return len(_presence)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS events(
    ts           TIMESTAMPTZ NOT NULL DEFAULT now(),
    kind         TEXT NOT NULL,
    vid          TEXT,
    killer_agent TEXT,
    victim_agent TEXT,
    weapon       TEXT,
    mode         TEXT
);
CREATE INDEX IF NOT EXISTS events_kind_ts ON events(kind, ts DESC);
CREATE INDEX IF NOT EXISTS events_ts ON events(ts DESC);
"""


def _connect():
    import psycopg
    from psycopg.rows import dict_row
    return psycopg.connect(DATABASE_URL, connect_timeout=10, row_factory=dict_row)


def ensure_schema():
    if not enabled:
        return
    try:
        with _connect() as c:
            for stmt in _SCHEMA.split(";"):
                stmt = stmt.strip()
                if stmt:
                    c.execute(stmt)
        log.info("stats: schema ready")
    except Exception as e:
        log.warning("stats: schema init failed: %s", e)


def page_hit(vid, referer=None):
    heartbeat(vid)


def _flush_events():
    with _event_buf_lock:
        if not _event_buf:
            return
        batch = list(_event_buf)
        _event_buf.clear()
    try:
        with _connect() as c:
            with c.cursor() as cur:
                cur.executemany(
                    "INSERT INTO events(kind, vid, killer_agent, victim_agent, weapon, mode) "
                    "VALUES (%(kind)s, %(vid)s, %(killer_agent)s, %(victim_agent)s, %(weapon)s, %(mode)s)",
                    batch)
    except Exception as e:
        log.debug("stats: flush_events failed: %s", e)


def log_event(kind, vid="", **fields):
    if not enabled:
        return
    now = time.monotonic()
    if kind == "preview":
        with _presence_lock:
            last = _last_preview.get(vid, 0)
            if now - last < PREVIEW_THROTTLE:
                return
            _last_preview[vid] = now
    rec = {"kind": kind, "vid": vid or "",
           "killer_agent": fields.get("killer_agent"),
           "victim_agent": fields.get("victim_agent"),
           "weapon": fields.get("weapon"),
           "mode": fields.get("mode")}
    with _event_buf_lock:
        _event_buf.append(rec)


def public_stats():
    online = online_now()
    cached = _public_cache["data"]
    if not enabled:
        return {"online": online, "today": cached.get("today", 0)}
    if time.time() - _public_cache["at"] < 60:
        merged = dict(cached)
        merged["online"] = online
        return merged
    try:
        with _connect() as c:
            row = c.execute("""
                SELECT
                    coalesce(sum(CASE WHEN kind='export' THEN 1 ELSE 0 END), 0)
                    + coalesce(sum(CASE WHEN kind='preview' THEN 1 ELSE 0 END), 0) * %s
                    AS n
                FROM events WHERE ts >= date_trunc('day', now())
            """, (PREVIEW_WEIGHT,)).fetchone()
        data = {"online": online, "today": round(float(row["n"]))}
        _public_cache.update(at=time.time(), data=data)
        return data
    except Exception as e:
        log.debug("stats: public_stats failed: %s", e)
        merged = dict(cached)
        merged["online"] = online
        return merged


async def _event_flush_loop():
    while True:
        await asyncio.sleep(EVENT_FLUSH_INTERVAL)
        await asyncio.to_thread(_flush_events)


async def startup():
    global enabled, DATABASE_URL
    DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
    if DATABASE_URL:
        DATABASE_URL = _repair_db_url(DATABASE_URL)
        os.environ["DATABASE_URL"] = DATABASE_URL
    enabled = bool(DATABASE_URL)
    if not enabled:
        log.info("stats: disabled (no DATABASE_URL)")
        return
    await asyncio.to_thread(ensure_schema)
    asyncio.create_task(_event_flush_loop())
    log.info("stats: schema ready")


async def shutdown():
    await asyncio.to_thread(_flush_events)
