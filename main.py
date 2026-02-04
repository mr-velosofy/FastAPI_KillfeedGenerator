from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
from generator import create_killfeed
from rev_generator import create_rev_killfeed


app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
print("BASE_DIR:", BASE_DIR)
print("FILES:", os.listdir(BASE_DIR))

app.mount("/static",StaticFiles(directory=os.path.join(BASE_DIR, "static")),name="static")
app.mount("/generated",StaticFiles(directory=os.path.join(BASE_DIR, "generated_killfeeds_v1")),name="generated")

# Setup Jinja2 templates
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


# Load agent and weapon names once at startup
AGENTS_DIR = os.path.join(BASE_DIR, "assets", "agents")
WEAPONS_DIR = os.path.join(BASE_DIR, "assets", "weapons")

AGENTS = [f[:-4] for f in os.listdir(AGENTS_DIR) if f.endswith(".png")]
WEAPONS = [f[:-4] for f in os.listdir(WEAPONS_DIR) if f.endswith(".png")]


import time

def cleanup_old_images(folder: str, age_seconds: int = 180):
    now = time.time()
    for filename in os.listdir(folder):
        filepath = os.path.join(folder, filename)
        if os.path.isfile(filepath):
            file_age = now - os.path.getmtime(filepath)
            if file_age > age_seconds:
                try:
                    os.remove(filepath)
                except Exception as e:
                    print(f"Failed to delete {filename}: {e}")



@app.get("/ping")
async def ping():
    return {"message": "pong"}

@app.get("/", response_class=HTMLResponse)
async def form_page(request: Request):
    # ✅ Pass an empty form dict to avoid Jinja errors
    return templates.TemplateResponse("form.html", {
        "request": request,
        "form": {},  # <-- this is what fixes your crash
        "agents": AGENTS,
        "weapons": WEAPONS,
        "image_url": None,
        "error": None
    })

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
    numeral: str = Form(None)
):
    numeral_valid_values = ['3', '4', '5', '6', '7']
    error = None
    image_url = None

    if numeral and numeral not in numeral_valid_values:
        error = "Only values 3, 4, 5, 6, and 7 are allowed for Numeral."

    if not error:
        # 🧹 Clean up old images
        cleanup_old_images(os.path.join(BASE_DIR, "generated_killfeeds_v1"))
        if is_enemy_kill:
            # Use the reverse generator for enemy kills
            image_path = create_rev_killfeed(
                killer_name=killer_name,
                victim_name=victim_name,
                killer_agent=killer_agent + ".png",
                victim_agent=victim_agent + ".png",
                weapon=weapon + ".png",
                is_headshot=is_headshot,
                is_wallbang=is_wallbang,
                is_player_kill=is_player_kill,
                numeral=numeral
            )
        else:
            image_path = create_killfeed(
                killer_name=killer_name,
                victim_name=victim_name,
                killer_agent=killer_agent + ".png",
                victim_agent=victim_agent + ".png",
                weapon=weapon + ".png",
                is_headshot=is_headshot,
                is_wallbang=is_wallbang,
                is_player_kill=is_player_kill,
                numeral=numeral
            )
        
        image_filename = os.path.basename(image_path)
        image_url = f"/generated/{image_filename}"


    # ✅ Re-inject form data for repopulating fields after submit
    return templates.TemplateResponse("form.html", {
        "request": request,
        "agents": AGENTS,
        "weapons": WEAPONS,
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
            "is_enemy_kill": is_enemy_kill
        }
    })

@app.get("/download/{filename}")
async def download_image(filename: str):
    filepath = os.path.join(BASE_DIR, "generated_killfeeds_v1", filename)
    if not os.path.exists(filepath):
        return HTMLResponse("File not found", status_code=404)
    
    response = FileResponse(filepath, media_type="image/png", filename=filename)
    
    # Optionally delete after serving (not recommended unless it's one-time use)
    # os.remove(filepath)

    return response


