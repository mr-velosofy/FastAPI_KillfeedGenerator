from fastapi import FastAPI, Form, Request, Query
from fastapi.responses import HTMLResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import time
from generator_v2 import create_killfeed
from rev_generator_v2 import create_rev_killfeed
from self_kill_generator import create_self_killfeed


app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app.mount("/assets", StaticFiles(directory=os.path.join(BASE_DIR, "assets")), name="assets")
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
app.mount("/static_v2", StaticFiles(directory=os.path.join(BASE_DIR, "static_v2")), name="static_v2")
app.mount("/generated", StaticFiles(directory=os.path.join(BASE_DIR, "generated_killfeeds_v1")), name="generated")

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates_v2"))

AGENTS_DIR = os.path.join(BASE_DIR, "assets", "agents")
WEAPONS_DIR = os.path.join(BASE_DIR, "assets", "weapons")
ABILITIES_DIR = os.path.join(BASE_DIR, "assets", "abilities")
SPECIAL_DIR = os.path.join(BASE_DIR, "assets", "special")

AGENTS = sorted([f[:-4] for f in os.listdir(AGENTS_DIR) if f.endswith(".png")])
WEAPONS = sorted([os.path.join("weapons", f) for f in os.listdir(WEAPONS_DIR) if f.endswith(".png")])
ABILITIES = sorted([os.path.join("abilities", f) for f in os.listdir(ABILITIES_DIR) if f.endswith(".png")])
SPECIAL = sorted([os.path.join("special", f) for f in os.listdir(SPECIAL_DIR) if f.endswith(".png")])

def get_css_version():
    return str(int(time.time()))

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


@app.get("/ping")
async def ping():
    return {"message": "pong"}

@app.get("/", response_class=HTMLResponse)
async def form_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="form_v2.html",
        context={
            "form": {},
            "agents": AGENTS,
            "weapons": WEAPONS,
            "abilities": ABILITIES,
            "special": SPECIAL,
            "css_version": get_css_version(),
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
            cleanup_old_images(os.path.join(BASE_DIR, "generated_killfeeds_v1"))
            image_path = create_self_killfeed(
                name=name,
                agent=agent + ".png",
                weapon=weapon,
                is_headshot=is_headshot,
                is_wallbang=is_wallbang,
                is_player_kill=is_player_kill,
                numeral=numeral
            )
        elif is_enemy_kill:
            cleanup_old_images(os.path.join(BASE_DIR, "generated_killfeeds_v1"))
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
            cleanup_old_images(os.path.join(BASE_DIR, "generated_killfeeds_v1"))
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
        name="form_v2.html",
        context={
            "agents": AGENTS,
            "weapons": WEAPONS,
            "abilities": ABILITIES,
            "special": SPECIAL,
            "css_version": get_css_version(),
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
                is_player_kill=is_player_kill, numeral=None
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

    except Exception as e:
        return Response(status_code=500, content=str(e))

@app.get("/download/{filename}")
async def download_image(filename: str):
    filepath = os.path.join(BASE_DIR, "generated_killfeeds_v1", filename)
    if not os.path.exists(filepath):
        return HTMLResponse("File not found", status_code=404)
    return FileResponse(filepath, media_type="image/png", filename=filename)
