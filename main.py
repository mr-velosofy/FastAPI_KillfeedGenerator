from fastapi import FastAPI, Form, Request, Query
from fastapi.responses import HTMLResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import gzip
import os
import time
import zlib
from generator import create_killfeed
from rev_generator import create_rev_killfeed
from self_kill_generator import create_self_killfeed


app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class CachedStaticFiles(StaticFiles):
    """Static files with 1-year browser caching (immutable-style)."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000"
        return response


app.mount("/static", CachedStaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
app.mount("/generated", StaticFiles(directory=os.path.join(BASE_DIR, "generated_killfeeds")), name="generated")

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


# Startup-cached file versions for cache-busting URLs (changes only when the
# file actually changes — unlike the old per-render timestamp busting)
_version_cache = {}


def file_version(relpath: str) -> int:
    if relpath not in _version_cache:
        fp = os.path.join(BASE_DIR, relpath)
        try:
            _version_cache[relpath] = int(os.stat(fp).st_mtime)
        except OSError:
            _version_cache[relpath] = 0
    return _version_cache[relpath]

AGENTS_DIR = os.path.join(BASE_DIR, "assets", "agents")
WEAPONS_DIR = os.path.join(BASE_DIR, "assets", "weapons")
ABILITIES_DIR = os.path.join(BASE_DIR, "assets", "abilities")
SPECIAL_DIR = os.path.join(BASE_DIR, "assets", "special")

AGENTS = sorted([f[:-4] for f in os.listdir(AGENTS_DIR) if f.endswith(".png")])
WEAPONS = sorted(["weapons/" + f for f in os.listdir(WEAPONS_DIR) if f.endswith(".png")])
ABILITIES = sorted(["abilities/" + f for f in os.listdir(ABILITIES_DIR) if f.endswith(".png")])
SPECIAL = sorted(["special/" + f for f in os.listdir(SPECIAL_DIR) if f.endswith(".png")])


# ── Text compression (HTML/CSS/JS/JSON) ──────────────────────────
# Images pass through untouched: they are already optimized formats.

TEXT_TYPES = {
    "text/html", "text/css", "text/plain",
    "application/json", "application/javascript", "image/svg+xml",
}


class TextCompressionMiddleware:
    MIN_SIZE = 1024

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        accept = ""
        for k, v in scope.get("headers", []):
            if k.lower() == b"accept-encoding":
                accept = v.decode("latin-1").lower()
                break
        state = {"status": 200, "headers": [], "accept": accept, "ctype": "",
                 "body": bytearray(), "done": False}

        async def flush():
            if state["done"]:
                return
            state["done"] = True
            headers = list(state["headers"])
            body = bytes(state["body"])
            ctype = state["ctype"].split(";")[0].strip()
            has_ce = any(k.lower() == b"content-encoding" for k, _ in headers)
            if (ctype in TEXT_TYPES and not has_ce
                    and len(body) >= self.MIN_SIZE):
                if "gzip" in state["accept"]:
                    body = gzip.compress(body, 6)
                    headers.append((b"content-encoding", b"gzip"))
                elif "deflate" in state["accept"]:
                    body = zlib.compress(body, 6)
                    headers.append((b"content-encoding", b"deflate"))
            if any(k.lower() == b"content-encoding" for k, _ in headers):
                headers = [(k, v) for k, v in headers
                           if k.lower() != b"content-length"]
                headers.append((b"content-length", str(len(body)).encode()))
                headers.append((b"vary", b"Accept-Encoding"))
            await send({"type": "http.response.start",
                        "status": state["status"], "headers": headers})
            await send({"type": "http.response.body", "body": body})

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                state["status"] = message["status"]
                state["headers"] = message.get("headers", [])
                for k, v in state["headers"]:
                    if k.lower() == b"content-type":
                        state["ctype"] = v.decode("latin-1").lower()
                return  # held until full body is buffered
            if message["type"] == "http.response.body":
                state["body"] += message.get("body", b"")
                if not message.get("more_body"):
                    await flush()
                return
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            await flush()


app.add_middleware(TextCompressionMiddleware)


def cleanup_old_images(folder: str, age_seconds: int = 180):
    now = time.time()
    for filename in os.listdir(folder):
        filepath = os.path.join(folder, filename)
        if os.path.isfile(filepath):
            file_age = now - os.path.getmtime(filepath)
            if file_age > age_seconds:
                try:
                    os.remove(filepath)
                except Exception:
                    pass


# Preview compression targets (preview only; downloads stay full-res PNG)
PREVIEW_MAX_W = 800          # preview panel never displays more than this
PREVIEW_TARGET_BYTES = 5120  # ~5 KB budget per preview response
AVIF_QUALITY_LADDER = (55, 45, 38, 32, 26)


def _encode_tiny_preview(png_bytes: bytes):
    """Downscale to display size and AVIF-encode, aiming for <= ~5 KB."""
    import io
    from PIL import Image
    img = Image.open(io.BytesIO(png_bytes))
    w, h = img.size
    if w > PREVIEW_MAX_W:
        nh = max(1, round(h * PREVIEW_MAX_W / w))
        img = img.resize((PREVIEW_MAX_W, nh), Image.LANCZOS)
    best = None
    for q in AVIF_QUALITY_LADDER:
        buf = io.BytesIO()
        img.save(buf, format="AVIF", quality=q, speed=8)
        payload = buf.getvalue()
        if best is None or len(payload) < len(best):
            best = payload
        if len(payload) <= PREVIEW_TARGET_BYTES:
            break
    return best


@app.get("/ping")
async def ping():
    return {"message": "pong"}

@app.get("/", response_class=HTMLResponse)
async def form_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="form.html",
        context={
            "form": {},
            "agents": AGENTS,
            "weapons": WEAPONS,
            "abilities": ABILITIES,
            "special": SPECIAL,
            "css_version": file_version(os.path.join("static", "style.css")),
            "image_url": None,
            "error": None,
        },
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )

@app.post("/", response_class=HTMLResponse)
async def generate_and_preview(
    request: Request,
    killer_name: str = Form(...),
    victim_name: str = Form(...),
    killer_agent: str = Form(...),
    victim_agent: str = Form(...),
    weapon: str = Form(...),
    is_headshot: bool = Form(False),
    is_wallbang: bool = Form(False),
    is_player_kill: bool = Form(False),
    is_enemy_kill: bool = Form(False),
    is_self_kill: bool = Form(False),
    numeral: str = Form(None)
):
    numeral_valid = ['3', '4', '5', '6', '7']
    error = None
    image_url = None
    image_filename = None

    if numeral and numeral not in numeral_valid:
        error = "Only values 3, 4, 5, 6, and 7 are allowed for Numeral."

    if not error:
        weapon_path = os.path.join(BASE_DIR, "assets", weapon)
        if not os.path.isfile(weapon_path):
            error = f"Weapon file not found: {os.path.basename(weapon_path)}."

    if not error:
        if is_self_kill:
            name = killer_name or victim_name or "PLAYER"
            agent = killer_agent if killer_agent != "" else (victim_agent if victim_agent != "" else "Jett")
            cleanup_old_images(os.path.join(BASE_DIR, "generated_killfeeds"))
            image_path = create_self_killfeed(
                name=name,
                agent=agent + ".png",
                weapon=weapon,
                is_headshot=is_headshot,
                is_wallbang=is_wallbang,
                is_player_kill=is_player_kill,
                numeral=numeral,
                is_enemy_kill=is_enemy_kill
            )
        elif is_enemy_kill:
            cleanup_old_images(os.path.join(BASE_DIR, "generated_killfeeds"))
            image_path = create_rev_killfeed(
                killer_name=killer_name,
                victim_name=victim_name,
                killer_agent=killer_agent + ".png",
                victim_agent=victim_agent + ".png",
                weapon=weapon,
                is_headshot=is_headshot,
                is_wallbang=is_wallbang,
                is_player_kill=is_player_kill,
                numeral=numeral
            )
        else:
            cleanup_old_images(os.path.join(BASE_DIR, "generated_killfeeds"))
            image_path = create_killfeed(
                killer_name=killer_name,
                victim_name=victim_name,
                killer_agent=killer_agent + ".png",
                victim_agent=victim_agent + ".png",
                weapon=weapon,
                is_headshot=is_headshot,
                is_wallbang=is_wallbang,
                is_player_kill=is_player_kill,
                numeral=numeral
            )

        if not image_path:
            error = "Failed to generate image."
        else:
            image_filename = os.path.basename(image_path)
            image_url = f"/generated/{image_filename}"

    return templates.TemplateResponse(
        request=request,
        name="form.html",
        context={
            "agents": AGENTS,
            "weapons": WEAPONS,
            "abilities": ABILITIES,
            "special": SPECIAL,
            "css_version": file_version(os.path.join("static", "style.css")),
            "image_url": image_url,
            "image_filename": image_filename,
            "error": error,
            "form": {
                "killer_name": killer_name,
                "victim_name": victim_name,
                "killer_agent": killer_agent,
                "victim_agent": victim_agent,
                "weapon": weapon,
                "numeral": numeral,
                "is_headshot": is_headshot,
                "is_wallbang": is_wallbang,
                "is_player_kill": is_player_kill,
                "is_enemy_kill": is_enemy_kill,
                "is_self_kill": is_self_kill,
            }
        },
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )

@app.get("/api/preview")
async def api_preview(
    request: Request,
    killer_name: str = Query("PLAYER"),
    victim_name: str = Query("PLAYER"),
    killer_agent: str = Query("Jett"),
    victim_agent: str = Query("Jett"),
    weapon: str = Query("weapons/Phantom.png"),
    is_headshot: bool = Query(False),
    is_wallbang: bool = Query(False),
    is_player_kill: bool = Query(False),
    is_enemy_kill: bool = Query(False),
    is_self_kill: bool = Query(False),
    numeral: str = Query(None),
    download: bool = Query(False)
):
    numeral_valid = ['3', '4', '5', '6', '7']
    if numeral and numeral not in numeral_valid:
        numeral = None

    weapon_path = os.path.join(BASE_DIR, "assets", weapon)
    if not os.path.isfile(weapon_path):
        return Response(status_code=404, content="Weapon not found")

    try:
        if is_self_kill:
            name = killer_name or victim_name or "PLAYER"
            agent = killer_agent if killer_agent else (victim_agent if victim_agent else "Jett")
            image_path = create_self_killfeed(
                name=name, agent=agent + ".png", weapon=weapon,
                is_headshot=False, is_wallbang=False,
                is_player_kill=is_player_kill, numeral=None,
                is_enemy_kill=is_enemy_kill
            )
        elif is_enemy_kill:
            image_path = create_rev_killfeed(
                killer_name=killer_name, victim_name=victim_name,
                killer_agent=killer_agent + ".png", victim_agent=victim_agent + ".png",
                weapon=weapon, is_headshot=is_headshot, is_wallbang=is_wallbang,
                is_player_kill=is_player_kill, numeral=numeral
            )
        else:
            image_path = create_killfeed(
                killer_name=killer_name, victim_name=victim_name,
                killer_agent=killer_agent + ".png", victim_agent=victim_agent + ".png",
                weapon=weapon, is_headshot=is_headshot, is_wallbang=is_wallbang,
                is_player_kill=is_player_kill, numeral=numeral
            )

        if not image_path or not os.path.isfile(image_path):
            return Response(status_code=500, content="Generation failed")

        with open(image_path, "rb") as f:
            data = f.read()
        headers = {}
        if download:
            headers["Content-Disposition"] = 'attachment; filename="killfeed.png"'
            return Response(content=data, media_type="image/png", headers=headers)

        # Preview path: serve the smallest format the client accepts
        # (measured on real renders: png ~88 KB, webp-q84 ~28 KB, tiny avif ~4-5 KB)
        accept = request.headers.get("accept", "")
        try:
            if "image/avif" in accept:
                tiny = _encode_tiny_preview(data)
                if tiny and len(tiny) < len(data):
                    return Response(content=tiny, media_type="image/avif", headers=headers)
            if "image/webp" in accept:
                import io
                from PIL import Image
                img = Image.open(io.BytesIO(data))
                buf = io.BytesIO()
                img.save(buf, format="WEBP", quality=84, method=5)
                webp = buf.getvalue()
                if len(webp) < len(data):
                    return Response(content=webp, media_type="image/webp", headers=headers)
        except Exception:
            pass
        return Response(content=data, media_type="image/png", headers=headers)

    except Exception as e:
        return Response(status_code=500, content=str(e))

@app.get("/download/{filename}")
async def download_image(filename: str):
    filepath = os.path.join(BASE_DIR, "generated_killfeeds", filename)
    if not os.path.exists(filepath):
        return HTMLResponse("File not found", status_code=404)
    return FileResponse(filepath, media_type="image/png", filename=filename)
