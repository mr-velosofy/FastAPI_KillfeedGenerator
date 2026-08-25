"""Anonymous usage analytics + periodic Discord digest.

Best-effort by design: when DATABASE_URL / DISCORD_WEBHOOK_URL are not
configured, or any call fails, everything degrades to a no-op and the
tool keeps working untouched.

Env vars:
    DATABASE_URL          Postgres URI (Supabase session pooler)
    DISCORD_WEBHOOK_URL   webhook that receives the digest embeds
    STATS_POST_WEBHOOK    "1" on the instance allowed to post digests
    STATS_DIGEST_HOURS    digest interval, default 2
"""

import asyncio
import json
import logging
import os
import threading
import time
import urllib.parse
import uuid
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

log = logging.getLogger("stats")

# ── env config ──────────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
POST_WEBHOOK = os.environ.get("STATS_POST_WEBHOOK", "") == "1"
DIGEST_SECONDS = float(os.environ.get("STATS_DIGEST_HOURS", "2")) * 3600

ONLINE_WINDOW = 180.0
PREVIEW_THROTTLE = 10.0
EVENT_FLUSH_INTERVAL = 30.0
PREVIEW_WEIGHT = 0.2  # 5 previews = 1 generation

# ── auto-repair DATABASE_URL ────────────────────────────────────────────────
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

# ── in-memory state ─────────────────────────────────────────────────────────
_presence = {}
_presence_lock = threading.Lock()
_peak_online = 0
_last_preview = {}
_stats_task = None
_last_digest_at = None
_public_cache = {"at": 0.0, "data": {"online": 0, "today": 0}}

# ── event buffer (batched writes) ───────────────────────────────────────────
_event_buf = []
_event_buf_lock = threading.Lock()
_seen_today = set()
_seen_today_date = None  # resets when UTC date changes


def ensure_vid(raw):
    if raw and len(raw) == 36:
        return raw, False
    return str(uuid.uuid4()), True


# ── presence ────────────────────────────────────────────────────────────────
def _sweep(now):
    cutoff = now - ONLINE_WINDOW
    for k in [k for k, t in _presence.items() if t < cutoff]:
        del _presence[k]


def heartbeat(vid):
    now = time.monotonic()
    with _presence_lock:
        _presence[vid] = now
        _sweep(now)
        global _peak_online
        if len(_presence) > _peak_online:
            _peak_online = len(_presence)
        return len(_presence)


def online_now():
    with _presence_lock:
        _sweep(time.monotonic())
        return len(_presence)


# ── database ────────────────────────────────────────────────────────────────
_SCHEMA = """
CREATE TABLE IF NOT EXISTS visitors(
    vid        TEXT PRIMARY KEY,
    first_seen TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS daily_visits(
    day          DATE NOT NULL,
    vid          TEXT NOT NULL,
    is_returning BOOLEAN NOT NULL,
    PRIMARY KEY(day, vid)
);
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
CREATE TABLE IF NOT EXISTS referrers(
    day   DATE NOT NULL,
    host  TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(day, host)
);
"""


def _connect():
    import psycopg
    from psycopg.rows import dict_row
    return psycopg.connect(DATABASE_URL, connect_timeout=10, row_factory=dict_row)


def _run_bg(fn, *args):
    threading.Thread(target=fn, args=args, daemon=True).start()


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


# ── visit tracking (deduped per day) ────────────────────────────────────────
def _track_visit(vid, ref_host):
    try:
        with _connect() as c:
            row = c.execute(
                "INSERT INTO visitors(vid) VALUES (%s) "
                "ON CONFLICT (vid) DO UPDATE SET last_seen = now() "
                "RETURNING first_seen",
                (vid,)).fetchone()
            is_ret = row["first_seen"].date() < datetime.now(timezone.utc).date()
            c.execute(
                "INSERT INTO daily_visits(day, vid, is_returning) "
                "VALUES (CURRENT_DATE, %s, %s) ON CONFLICT DO NOTHING",
                (vid, is_ret))
            if ref_host:
                ref_host = ref_host[:100].lower()
                c.execute(
                    "INSERT INTO referrers(day, host, count) "
                    "VALUES (CURRENT_DATE, %s, 1) "
                    "ON CONFLICT (day, host) DO UPDATE SET count = referrers.count + 1",
                    (ref_host,))
    except Exception as e:
        log.debug("stats: track_visit failed: %s", e)


def page_hit(vid, referer=None):
    heartbeat(vid)
    if not enabled:
        return
    global _seen_today_date
    today = datetime.now(timezone.utc).date()
    with _presence_lock:
        if _seen_today_date != today:
            _seen_today.clear()
            _seen_today_date = today
        if vid in _seen_today:
            return
        _seen_today.add(vid)
    host = None
    if referer:
        try:
            from urllib.parse import urlparse
            host = urlparse(referer).netloc or None
        except Exception:
            pass
    _run_bg(_track_visit, vid, host)


# ── event batching ──────────────────────────────────────────────────────────
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
        log.debug("stats: flushed %d events", len(batch))
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


# ── public stats for the frontend badge ─────────────────────────────────────
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


# ── digest ──────────────────────────────────────────────────────────────────
def _scalar(c, sql, *params):
    row = c.execute(sql, params or None).fetchone()
    return int(row["n"]) if row else 0


def _window_count(c, table, where):
    return _scalar(c, f"SELECT count(*) AS n FROM {table} WHERE {where}")


def _weighted_count(c, where):
    row = c.execute(f"""
        SELECT coalesce(sum(CASE WHEN kind='export' THEN 1 ELSE 0 END), 0)
             + coalesce(sum(CASE WHEN kind='preview' THEN 1 ELSE 0 END), 0) * %s
             AS n FROM events WHERE {where}
    """, (PREVIEW_WEIGHT,)).fetchone()
    return round(float(row["n"])) if row else 0


def collect_digest(since):
    with _connect() as c:
        gens_since_raw = c.execute(
            "SELECT kind, count(*) AS n FROM events "
            "WHERE ts > %s GROUP BY kind", (since,)).fetchall()
        by_kind = {r["kind"]: int(r["n"]) for r in gens_since_raw}
        gens_since_w = round(by_kind.get("export", 0) + by_kind.get("preview", 0) * PREVIEW_WEIGHT)

        gens = {
            "day":   _weighted_count(c, "ts >= date_trunc('day', now())"),
            "week":  _weighted_count(c, "ts >= now() - interval '7 days'"),
            "month": _weighted_count(c, "ts >= date_trunc('month', now())"),
            "all":   _weighted_count(c, "TRUE"),
        }
        uniq = {
            "day":   _scalar(c, "SELECT count(DISTINCT vid) AS n FROM daily_visits WHERE day = CURRENT_DATE"),
            "week":  _scalar(c, "SELECT count(DISTINCT vid) AS n FROM daily_visits WHERE day >= CURRENT_DATE - 6"),
            "month": _scalar(c, "SELECT count(DISTINCT vid) AS n FROM daily_visits WHERE day >= date_trunc('month', now())"),
            "all":   _scalar(c, "SELECT count(*) AS n FROM visitors"),
        }
        nr = c.execute(
            "SELECT is_returning, count(*) AS n FROM daily_visits "
            "WHERE day = CURRENT_DATE GROUP BY is_returning").fetchall()
        new_ret = {str(r["is_returning"]).lower(): int(r["n"]) for r in nr}

        visits = {
            "day":   _window_count(c, "daily_visits", "day = CURRENT_DATE"),
            "week":  _window_count(c, "daily_visits", "day >= CURRENT_DATE - 6"),
            "month": _window_count(c, "daily_visits", "day >= date_trunc('month', now())"),
            "all":   _window_count(c, "daily_visits", "TRUE"),
        }
        top_agents = c.execute("""
            SELECT killer_agent AS a, count(*) AS n FROM events
            WHERE coalesce(killer_agent,'') <> '' AND ts >= now() - interval '7 days'
            GROUP BY 1 ORDER BY 2 DESC LIMIT 5""").fetchall()
        top_weapons = c.execute("""
            SELECT coalesce(weapon,'other') AS w, count(*) AS n FROM events
            WHERE ts >= now() - interval '7 days' AND kind = 'export'
            GROUP BY 1 ORDER BY 2 DESC LIMIT 5""").fetchall()
        modes = c.execute(
            "SELECT mode, count(*) AS n FROM events GROUP BY mode").fetchall()
        refs = c.execute("""
            SELECT host, sum(count) AS total FROM referrers
            WHERE day >= CURRENT_DATE - 6
            GROUP BY host ORDER BY total DESC LIMIT 5""").fetchall()

    modes_map = {(r["mode"] or "normal"): int(r["n"]) for r in modes}
    mode_total = sum(modes_map.values()) or 1

    return {
        "gens_since": gens_since_w,
        "since_split": {"previews": by_kind.get("preview", 0), "exports": by_kind.get("export", 0)},
        "gens": gens,
        "uniq": uniq,
        "today_new": new_ret.get("false", 0),
        "today_returning": new_ret.get("true", 0),
        "visits": visits,
        "top_agents": [(r["a"], int(r["n"])) for r in top_agents],
        "top_weapons": [(r["w"].split("/")[-1], int(r["n"])) for r in top_weapons],
        "mode_mix": [(m, round(100 * n / mode_total))
                     for m, n in sorted(modes_map.items(), key=lambda kv: -kv[1])],
        "top_refs": [(r["host"], int(r["total"])) for r in refs],
        "online": online_now(),
        "peak": _peak_online,
    }


def build_embed(d):
    def chain(vals):
        return " · ".join(f"**{v}**" for v in vals)

    gens_line = (
        f"Since last: **{d['gens_since']}** ({d['since_split']['previews']} prev / "
        f"{d['since_split']['exports']} exp)\n"
        f"Day {d['gens']['day']} · Week {d['gens']['week']} · "
        f"Month {d['gens']['month']} · All-time **{d['gens']['all']}**")

    uniq_line = (
        f"Today: **{d['uniq']['day']}** ({d['today_new']} new / "
        f"{d['today_returning']} ret)\n"
        f"Week {d['uniq']['week']} · Month {d['uniq']['month']} · "
        f"All-time **{d['uniq']['all']}**")

    visits_line = (
        f"D {d['visits']['day']} · W {d['visits']['week']} · "
        f"M {d['visits']['month']} · All **{d['visits']['all']}**")

    live_line = f"Online now: **{d['online']}** · peak since last: **{d['peak']}**"

    fields = [
        {"name": "⚡ Generations", "value": gens_line},
        {"name": "👥 Unique visitors", "value": uniq_line, "inline": False},
        {"name": "🚪 Page visits", "value": visits_line, "inline": True},
        {"name": "🟢 Live", "value": live_line, "inline": True},
    ]
    if d["top_agents"]:
        fields.append({"name": "🔫 Top agents (7d)", "value": chain([f"{a} ({n})" for a, n in d["top_agents"]]), "inline": True})
    if d["top_weapons"]:
        fields.append({"name": "⚔️ Top weapons (7d)", "value": chain([f"{w} ({n})" for w, n in d["top_weapons"]]), "inline": True})
    if d["mode_mix"]:
        fields.append({"name": "🎛 Mode mix (all-time)", "value": chain([f"{m} {p}%" for m, p in d["mode_mix"]]), "inline": True})
    if d["top_refs"]:
        fields.append({"name": "🔗 Top referrers (7d)", "value": chain([f"{h} ({n})" for h, n in d["top_refs"]]), "inline": False})

    return {
        "username": "Killfeed Stats",
        "embeds": [{
            "title": "📊 Killfeed Generator — Stats Digest",
            "color": 0xFF4655,
            "fields": fields,
            "footer": {"text": f"every {DIGEST_SECONDS / 3600:.0f}h · day boundaries UTC"},
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }]
    }


def post_digest():
    global _last_digest_at
    from discord_webhook import DiscordWebhook, DiscordEmbed
    since = _last_digest_at or datetime.now(timezone.utc).replace(microsecond=0)
    d = collect_digest(since)
    webhook = DiscordWebhook(url=WEBHOOK_URL, username="Killfeed Stats")
    embed = DiscordEmbed(title="📊 Killfeed Generator — Stats Digest", color="ff4655",
                         timestamp=datetime.now(timezone.utc).isoformat())
    embed.set_footer(text=f"every {DIGEST_SECONDS / 3600:.0f}h · day boundaries UTC")

    def chain(vals):
        return " · ".join(f"**{v}**" for v in vals)

    embed.add_embed_field(name="⚡ Generations",
        value=f"Since last: **{d['gens_since']}** ({d['since_split']['previews']} prev / {d['since_split']['exports']} exp)\n"
              f"Day {d['gens']['day']} · Week {d['gens']['week']} · Month {d['gens']['month']} · All-time **{d['gens']['all']}**")
    embed.add_embed_field(name="👥 Unique visitors",
        value=f"Today: **{d['uniq']['day']}** ({d['today_new']} new / {d['today_returning']} ret)\n"
              f"Week {d['uniq']['week']} · Month {d['uniq']['month']} · All-time **{d['uniq']['all']}**")
    embed.add_embed_field(name="🚪 Page visits",
        value=f"D {d['visits']['day']} · W {d['visits']['week']} · M {d['visits']['month']} · All **{d['visits']['all']}**", inline=True)
    embed.add_embed_field(name="🟢 Live",
        value=f"Online now: **{d['online']}** · peak since last: **{d['peak']}**", inline=True)
    if d["top_agents"]:
        embed.add_embed_field(name="🔫 Top agents (7d)",
            value=chain([f"{a} ({n})" for a, n in d["top_agents"]]), inline=True)
    if d["top_weapons"]:
        embed.add_embed_field(name="⚔️ Top weapons (7d)",
            value=chain([f"{w} ({n})" for w, n in d["top_weapons"]]), inline=True)
    if d["mode_mix"]:
        embed.add_embed_field(name="🎛 Mode mix (all-time)",
            value=chain([f"{m} {p}%" for m, p in d["mode_mix"]]), inline=True)
    if d["top_refs"]:
        embed.add_embed_field(name="🔗 Top referrers (7d)",
            value=chain([f"{h} ({n})" for h, n in d["top_refs"]]), inline=False)

    webhook.add_embed(embed)
    resp = webhook.execute()
    if resp.status_code not in (200, 204):
        raise RuntimeError(f"Discord {resp.status_code}: {resp.text[:200]}")
    _last_digest_at = datetime.now(timezone.utc)
    log.info("stats: digest posted")


# ── background loops ────────────────────────────────────────────────────────
async def _event_flush_loop():
    while True:
        await asyncio.sleep(EVENT_FLUSH_INTERVAL)
        await asyncio.to_thread(_flush_events)


async def digest_loop():
    global _last_digest_at
    _last_digest_at = datetime.now(timezone.utc)
    while True:
        await asyncio.sleep(DIGEST_SECONDS)
        try:
            await asyncio.to_thread(_flush_events)
            await asyncio.to_thread(post_digest)
        except Exception as e:
            log.warning("stats: digest failed: %s", e)


async def startup():
    if not enabled:
        log.info("stats: disabled (no DATABASE_URL)")
        return
    await asyncio.to_thread(ensure_schema)
    asyncio.create_task(_event_flush_loop())
    if POST_WEBHOOK and WEBHOOK_URL:
        global _stats_task
        _stats_task = asyncio.create_task(digest_loop())
        log.info("stats: digest loop started (%.0fh)", DIGEST_SECONDS / 3600)
    else:
        log.info("stats: schema ready, digest posting disabled")


async def shutdown():
    if _stats_task:
        _stats_task.cancel()
    await asyncio.to_thread(_flush_events)
