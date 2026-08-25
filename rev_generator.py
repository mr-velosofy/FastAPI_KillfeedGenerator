from PIL import Image, ImageDraw, ImageFont, ImageOps
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_PATH = os.path.join(BASE_DIR, "assets")
OUTPUT_PATH = os.path.join(BASE_DIR, "generated_killfeeds")
FONT_PATH = os.path.join(ASSETS_PATH, "fonts", "dinnextw1g_medium.otf")
os.makedirs(OUTPUT_PATH, exist_ok=True)

FONT_SIZE = 66
IMG_HEIGHT = 128
AGENT_ICON_SIZE = (256, 128)
WEAPON_ICON_HEIGHT = 90
HEADSHOT_ICON_SIZE = (72, 72)
PADDING = 40
TEXT_PADDING = 70
EDGE_GAP = int(TEXT_PADDING / 4)
ME_SIZE = 128
KILLER_BG_COLOR = (240, 91, 88)
VICTIM_BG_COLOR = (87, 222, 196)
TEXT_COLOR = (255, 255, 255, 255)
YELLOW = (231, 237, 131)
TEAL_HIGHLIGHT = (87, 222, 196)
RED_HIGHLIGHT = (240, 91, 88)
BORDER_W = 6
BORDER_H = 6
MASK_OFFSET = 30
EARLY = 128


def unpremultiply(img):
    if img.mode != 'RGBA': return img
    arr = img.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = arr[x, y]
            if 0 < a < 255:
                arr[x, y] = (min(255, int(r * 255 / a)),
                             min(255, int(g * 255 / a)),
                             min(255, int(b * 255 / a)), a)
    return img


def create_custom_me_mask(mx):
    off = MASK_OFFSET
    gt = max(1, mx - BORDER_W - EARLY)
    width = max(600, off + BORDER_W + gt + 10)
    mask = Image.new("L", (width, ME_SIZE), 0)
    draw = ImageDraw.Draw(mask)

    draw.rectangle([off, 0, off + BORDER_W - 1, ME_SIZE - 1], fill=255)

    half = gt // 2
    for x in range(gt):
        if x < half:
            a = 255
        else:
            step = gt - half
            a = int(255 * (gt - 1 - x) / (step - 1)) if step > 1 else 0
        draw.line([(off + BORDER_W + x, 0), (off + BORDER_W + x, BORDER_H - 1)], fill=a)
        draw.line([(off + BORDER_W + x, ME_SIZE - BORDER_H), (off + BORDER_W + x, ME_SIZE - 1)], fill=a)

    return mask


def create_rev_killfeed(killer_name, victim_name, killer_agent, victim_agent, weapon,
                        is_headshot=False, is_player_kill=False, is_wallbang=False, numeral=None):
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)

    killer_agent_img = unpremultiply(Image.open(os.path.join(ASSETS_PATH, "agents", killer_agent)).resize(AGENT_ICON_SIZE))
    victim_agent_img = unpremultiply(Image.open(os.path.join(ASSETS_PATH, "agents", victim_agent)).resize(AGENT_ICON_SIZE))

    weapon_img = Image.open(os.path.join(ASSETS_PATH, weapon))
    ratio = WEAPON_ICON_HEIGHT / weapon_img.height
    weapon_img = weapon_img.resize((int(weapon_img.width * ratio), WEAPON_ICON_HEIGHT))
    weapon_img = unpremultiply(weapon_img)

    temp = ImageDraw.Draw(Image.new("RGB", (0, 0)))
    kw = temp.textlength(killer_name, font=font)
    vw = temp.textlength(victim_name, font=font)
    ww = weapon_img.width

    hs_img = None
    wb_img = None
    if is_headshot:
        hs_img = unpremultiply(Image.open(os.path.join(ASSETS_PATH, "icons", "headshot.png")).resize(HEADSHOT_ICON_SIZE))
    if is_wallbang:
        wb_img = unpremultiply(Image.open(os.path.join(ASSETS_PATH, "icons", "wallbang.png")).resize((72, 72)))

    left_text_x = int(AGENT_ICON_SIZE[0] + EDGE_GAP)
    weapon_left = int(left_text_x + kw + TEXT_PADDING)
    weapon_end = weapon_left + ww
    if wb_img or hs_img:
        weapon_end += PADDING
    if wb_img:
        weapon_end += int(wb_img.width + 10)
    if hs_img:
        weapon_end += int(hs_img.width + 10)
    mx = int(weapon_end + PADDING)
    right_text_x = int(mx + TEXT_PADDING)
    tw = int(right_text_x + vw + EDGE_GAP + AGENT_ICON_SIZE[0])

    k_shape = [(0, 0), (mx - 20, 0), (mx, IMG_HEIGHT // 2), (mx - 20, IMG_HEIGHT), (0, IMG_HEIGHT)]
    v_shape = [(mx - 35, 0), (tw, 0), (tw, IMG_HEIGHT), (mx - 35, IMG_HEIGHT), (mx, IMG_HEIGHT // 2)]

    canvas = Image.new("RGBA", (tw, IMG_HEIGHT), (0, 0, 0, 0))

    # Gradient backgrounds
    teal = Image.new("RGBA", (tw, IMG_HEIGHT), (0, 0, 0, 0))
    for x in range(mx + 1):
        a = int(255 * (x / mx))
        ImageDraw.Draw(teal).line([(x, 0), (x, IMG_HEIGHT)], fill=(*KILLER_BG_COLOR, a))
    m = Image.new("L", (tw, IMG_HEIGHT), 0)
    ImageDraw.Draw(m).polygon(k_shape, fill=255)
    canvas.paste(teal, (0, 0), m)

    red = Image.new("RGBA", (tw, IMG_HEIGHT), (0, 0, 0, 0))
    rl = mx - 35
    md = tw - mx
    for x in range(rl, tw):
        d = abs(x - mx)
        a = max(0, int(255 * (1 - d / md)))
        ImageDraw.Draw(red).line([(x, 0), (x, IMG_HEIGHT)], fill=(*VICTIM_BG_COLOR, a))
    m = Image.new("L", (tw, IMG_HEIGHT), 0)
    ImageDraw.Draw(m).polygon(v_shape, fill=255)
    canvas.paste(red, (0, 0), m)

    # Edge rects (rev: left=red, right=teal)
    canvas.paste(Image.new("RGBA", (120, 130), (*RED_HIGHLIGHT, 255)), (0, 0))
    canvas.paste(Image.new("RGBA", (120, 130), (*TEAL_HIGHLIGHT, 255)), (tw - 120, 0))

    # Me highlight — on RIGHT side for rev
    if is_player_kill:
        canvas.paste(Image.new("RGBA", (120, 130), (*YELLOW, 255)), (tw - 120, 0))

    # Agent icons (rev: left hl=red, right hl=teal / yellow on me)
    kill_hl_color = RED_HIGHLIGHT
    victim_hl_color = YELLOW if is_player_kill else TEAL_HIGHLIGHT

    killer_hl = Image.new("RGBA", killer_agent_img.size, (*kill_hl_color, 255))
    canvas.paste(killer_hl, (10, 0), killer_agent_img)
    canvas.paste(killer_agent_img, (0, 0), killer_agent_img)

    victim_flipped = ImageOps.mirror(victim_agent_img)
    victim_hl = Image.new("RGBA", victim_flipped.size, (*victim_hl_color, 255))
    canvas.paste(victim_hl, (tw - AGENT_ICON_SIZE[0] - 10, 0), victim_flipped)
    canvas.paste(victim_flipped, (tw - AGENT_ICON_SIZE[0], 0), victim_flipped)

    # Weapon
    weapon_y = (IMG_HEIGHT - weapon_img.height) // 2
    if weapon.replace("\\", "/").startswith("weapons/"):
        weapon_img = ImageOps.mirror(weapon_img)
    canvas.paste(weapon_img, (weapon_left, weapon_y), weapon_img)

    # Headshot / wallbang
    next_x = weapon_left + ww
    if wb_img or hs_img:
        next_x += PADDING
    if wb_img:
        wby = (IMG_HEIGHT - wb_img.height) // 2
        canvas.paste(wb_img, (next_x, wby), wb_img)
        next_x += wb_img.width + 10
    if hs_img:
        hsy = (IMG_HEIGHT - hs_img.height) // 2
        canvas.paste(hs_img, (next_x, hsy), hs_img)

    # Text
    draw = ImageDraw.Draw(canvas)
    ref = font.getbbox("Xy")
    text_center_y = int(IMG_HEIGHT / 2 - (ref[1] + ref[3]) / 2)
    draw.text((left_text_x, text_center_y), killer_name, font=font, fill=TEXT_COLOR)
    draw.text((right_text_x, text_center_y), victim_name, font=font, fill=TEXT_COLOR)

    # Me border on top — on RIGHT side for rev
    if is_player_kill:
        mask = create_custom_me_mask(mx).transpose(Image.FLIP_LEFT_RIGHT)
        me_hl = Image.new("RGBA", mask.size, (*YELLOW, 255))
        canvas.paste(me_hl, (canvas.width - 600 + 30, 0), mask)

    # Me triangle — on RIGHT side for rev
    if is_player_kill:
        tri = Image.open(os.path.join(ASSETS_PATH, "ui", "MeBorderTriangle.png")).convert("RGBA")
        tri = tri.transpose(Image.FLIP_LEFT_RIGHT)
        tri = unpremultiply(tri)
        tri_yellow = Image.new("RGBA", tri.size, (*YELLOW, 255))
        tri_c = Image.new("RGBA", tri.size, (0, 0, 0, 0))
        tri_c.paste(tri_yellow, (0, 0), tri)
        f = Image.new("RGBA", (canvas.width + tri.width, max(canvas.height, tri.height)), (0, 0, 0, 0))
        f.paste(canvas, (0, 0))
        f.paste(tri_c, (canvas.width, (f.height - tri.height) // 2))
        canvas = f

    # Numeral — use Rev_ variant
    if numeral:
        numeral_img = Image.open(os.path.join(ASSETS_PATH, "ui", f"Rev_Numeral_{numeral}.png")).convert("RGBA")
        numeral_img = unpremultiply(numeral_img)
        new_width = canvas.width + numeral_img.width
        new_height = max(canvas.height, numeral_img.height)
        offset_x = 12
        f = Image.new("RGBA", (new_width, new_height), (0, 0, 0, 0))
        f.paste(canvas, (numeral_img.width, 0))
        f.paste(numeral_img, (offset_x, 30), numeral_img)
        canvas = f

    numeral_str = f"{numeral}K" if numeral else ""
    me_str = "Me" if is_player_kill else ""
    tags = "_".join(filter(None, [numeral_str, me_str]))
    tag_part = f"_{tags}" if tags else ""
    output_filename = f"{killer_name}_vs_{victim_name}{tag_part}_{int(datetime.now().timestamp())}.png"
    canvas.save(os.path.join(OUTPUT_PATH, output_filename))

    return os.path.join(OUTPUT_PATH, output_filename)
