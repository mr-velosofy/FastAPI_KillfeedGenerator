from PIL import Image, ImageDraw, ImageFont, ImageOps
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_PATH = os.path.join(BASE_DIR, "assets")
OUTPUT_PATH = os.path.join(BASE_DIR, "generated_killfeeds")
FONT_PATH = os.path.join(ASSETS_PATH, "fonts", "dinnextw1g_medium.otf")
REVIVE_ICON_PATH = os.path.join(ASSETS_PATH, "special", "Revive.png")
os.makedirs(OUTPUT_PATH, exist_ok=True)

FONT_SIZE = 66
STRIP_H = 128            # everything of the normal feed stays this tall
CANVAS_H = 153           # only because of the big revive icon
STRIP_Y = (CANVAS_H - STRIP_H) // 2   # 12 — strip sits vertically centered
AGENT_ICON_SIZE = (256, 128)
REVIVE_ICON_SIZE = (153, 153)
TEXT_PADDING = 70
PADDING = 40
EDGE_GAP = int(TEXT_PADDING / 4)
TEXT_COLOR = (255, 255, 255, 255)
YELLOW = (231, 237, 131)
BORDER_W = 6
BORDER_H = 6
MASK_OFFSET = 30
EARLY = 128
ME_SIZE = 128

# Colors follow Suicide Mode: one family per theme.
# Red = enemy revive; ME highlight is not allowed there.
THEMES = {
    "teal": {"base": (87, 222, 196), "light": (178, 237, 219)},
    "red": {"base": (240, 91, 88), "light": (253, 147, 149)},
}


def unpremultiply(img):
    if img.mode != 'RGBA':
        return img
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

    gt = max(1, min(mx - BORDER_W - EARLY, width - off - BORDER_W))
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


def create_revive_killfeed(left_name, left_agent, right_name, right_agent,
                           theme="teal", me_side=""):
    """Revive feed: big 153x153 icon in the ability slot, strip stays 128 tall.

    me_side: "" | "left" (reviver is you) | "right" (revived is you).
    Silently dropped on the red/enemy theme — enemies cannot be you.
    No numerals for revive feeds, ever."""
    if theme == "red":
        me_side = ""
    if me_side not in ("left", "right"):
        me_side = ""
    colors = THEMES[theme]
    base = colors["base"]     # reviver side
    light = colors["light"]   # revived side
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)

    left_agent_img = unpremultiply(Image.open(os.path.join(ASSETS_PATH, "agents", left_agent)).resize(AGENT_ICON_SIZE))
    right_agent_img = unpremultiply(Image.open(os.path.join(ASSETS_PATH, "agents", right_agent)).resize(AGENT_ICON_SIZE))

    revive_icon = unpremultiply(Image.open(REVIVE_ICON_PATH).convert("RGBA"))
    if revive_icon.size != REVIVE_ICON_SIZE:
        revive_icon = revive_icon.resize(REVIVE_ICON_SIZE)

    temp = ImageDraw.Draw(Image.new("RGB", (0, 0)))
    lw = temp.textlength(left_name, font=font)
    rw = temp.textlength(right_name, font=font)
    iw = REVIVE_ICON_SIZE[0]

    # Geometry (strip coordinates, then offset by STRIP_Y when pasting).
    # Icon sits in the classic ability slot: after the left name,
    # LEFT of the junction — same as weapons did.
    left_text_x = int(AGENT_ICON_SIZE[0] + EDGE_GAP)
    icon_x = int(left_text_x + lw + TEXT_PADDING)
    mx = int(icon_x + iw + PADDING)        # arrow tips meet past the icon
    right_text_x = int(mx + TEXT_PADDING)
    tw = int(right_text_x + rw + EDGE_GAP + AGENT_ICON_SIZE[0])

    k_shape = [(0, STRIP_Y), (mx - 20, STRIP_Y),
               (mx, STRIP_Y + STRIP_H // 2), (mx - 20, STRIP_Y + STRIP_H), (0, STRIP_Y + STRIP_H)]
    v_shape = [(mx - 35, STRIP_Y), (tw, STRIP_Y), (tw, STRIP_Y + STRIP_H),
               (mx - 35, STRIP_Y + STRIP_H), (mx, STRIP_Y + STRIP_H // 2)]

    canvas = Image.new("RGBA", (tw, CANVAS_H), (0, 0, 0, 0))

    # Left gradient (reviver)
    left_bg = Image.new("RGBA", (tw, CANVAS_H), (0, 0, 0, 0))
    for x in range(mx + 1):
        a = int(255 * (x / mx))
        ImageDraw.Draw(left_bg).line([(x, STRIP_Y), (x, STRIP_Y + STRIP_H)], fill=(*base, a))
    m = Image.new("L", (tw, CANVAS_H), 0)
    ImageDraw.Draw(m).polygon(k_shape, fill=255)
    canvas.paste(left_bg, (0, 0), m)

    # Right gradient (revived) — fades out from the junction
    right_bg = Image.new("RGBA", (tw, CANVAS_H), (0, 0, 0, 0))
    rl = mx - 35
    md = tw - mx
    for x in range(rl, tw):
        d = abs(x - mx)
        a = max(0, int(255 * (1 - d / md)))
        ImageDraw.Draw(right_bg).line([(x, STRIP_Y), (x, STRIP_Y + STRIP_H)], fill=(*light, a))
    m = Image.new("L", (tw, CANVAS_H), 0)
    ImageDraw.Draw(m).polygon(v_shape, fill=255)
    canvas.paste(right_bg, (0, 0), m)

    # Edge bars (clipped to strip height); yellow only on the "me" side
    me_l = me_side == "left"
    me_r = me_side == "right"
    edge_l = YELLOW if me_l else base
    edge_r = YELLOW if me_r else light
    canvas.paste(Image.new("RGBA", (120, STRIP_H), (*edge_l, 255)), (0, STRIP_Y))
    canvas.paste(Image.new("RGBA", (120, STRIP_H), (*edge_r, 255)), (tw - 120, STRIP_Y))

    # Agent icons
    left_hl_color = YELLOW if me_l else base
    left_hl = Image.new("RGBA", left_agent_img.size, (*left_hl_color, 255))
    canvas.paste(left_hl, (10, STRIP_Y), left_agent_img)
    canvas.paste(left_agent_img, (0, STRIP_Y), left_agent_img)

    right_flipped = ImageOps.mirror(right_agent_img)
    right_hl_color = YELLOW if me_r else light
    right_hl = Image.new("RGBA", right_flipped.size, (*right_hl_color, 255))
    canvas.paste(right_hl, (tw - AGENT_ICON_SIZE[0] - 10, STRIP_Y), right_flipped)
    canvas.paste(right_flipped, (tw - AGENT_ICON_SIZE[0], STRIP_Y), right_flipped)

    # Big revive icon — full 153x153 in the ability slot
    canvas.alpha_composite(revive_icon, (icon_x, 0))

    # Text
    draw = ImageDraw.Draw(canvas)
    ref = font.getbbox("Xy")
    text_center_y = int(STRIP_Y + STRIP_H / 2 - (ref[1] + ref[3]) / 2)
    draw.text((left_text_x, text_center_y), left_name, font=font, fill=TEXT_COLOR)
    draw.text((right_text_x, text_center_y), right_name, font=font, fill=TEXT_COLOR)

    # Custom Me border + corner triangle on the chosen side only
    if me_side == "left":
        mask_left = create_custom_me_mask(mx)
        me_hl = Image.new("RGBA", mask_left.size, (*YELLOW, 255))
        canvas.paste(me_hl, (-30, STRIP_Y), mask_left)

        tri = Image.open(os.path.join(ASSETS_PATH, "ui", "MeBorderTriangle.png")).convert("RGBA")
        tri = unpremultiply(tri)
        tri_y = Image.new("RGBA", tri.size, (*YELLOW, 255))
        tri_c = Image.new("RGBA", tri.size, (0, 0, 0, 0))
        tri_c.paste(tri_y, (0, 0), tri)
        f = Image.new("RGBA", (canvas.width + tri.width, max(canvas.height, tri.height)), (0, 0, 0, 0))
        f.paste(tri_c, (0, (f.height - tri.height) // 2))
        f.paste(canvas, (tri.width, 0))
        canvas = f

    if me_side == "right":
        mask_right = create_custom_me_mask(mx).transpose(Image.FLIP_LEFT_RIGHT)
        me_hl_r = Image.new("RGBA", mask_right.size, (*YELLOW, 255))
        canvas.paste(me_hl_r, (canvas.width - 600 + 30, STRIP_Y), mask_right)

        tri_r = Image.open(os.path.join(ASSETS_PATH, "ui", "MeBorderTriangle.png")).convert("RGBA")
        tri_r = tri_r.transpose(Image.FLIP_LEFT_RIGHT)
        tri_r = unpremultiply(tri_r)
        tri_ry = Image.new("RGBA", tri_r.size, (*YELLOW, 255))
        tri_rc = Image.new("RGBA", tri_r.size, (0, 0, 0, 0))
        tri_rc.paste(tri_ry, (0, 0), tri_r)
        f = Image.new("RGBA", (canvas.width + tri_r.width, max(canvas.height, tri_r.height)), (0, 0, 0, 0))
        f.paste(canvas, (0, 0))
        f.paste(tri_rc, (canvas.width, (f.height - tri_r.height) // 2))
        canvas = f

    me_str = {"left": "MeLeft", "right": "MeRight", "": ""}[me_side]
    tag_part = f"_{me_str}" if me_str else ""
    output_filename = f"revive_{left_name}_and_{right_name}{tag_part}_{int(datetime.now().timestamp())}.png"
    canvas.save(os.path.join(OUTPUT_PATH, output_filename))

    return os.path.join(OUTPUT_PATH, output_filename)
