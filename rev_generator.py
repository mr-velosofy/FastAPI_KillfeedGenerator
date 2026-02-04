from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageChops, ImageFilter
import os
from datetime import datetime
import time

# --- Configuration ---
# Define paths to your asset and output folders
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ASSETS_PATH = os.path.join(BASE_DIR, "assets")
OUTPUT_PATH = os.path.join(BASE_DIR, "generated_killfeeds_v1")
FONT_PATH = os.path.join(ASSETS_PATH, "fonts", "dinnextw1g_medium.otf")


# Create the output directory if it doesn't exist
if not os.path.exists(OUTPUT_PATH):
    os.makedirs(OUTPUT_PATH)

def create_horizontal_gradient(color, width, height, reverse=False):
    """
    Creates a horizontal linear gradient from a color to transparent.

    Args:
        color (tuple): The RGBA color to start with (e.g., (70, 156, 147, 255)).
        width (int): The width of the gradient image.
        height (int): The height of the gradient image.
        reverse (bool): If True, the gradient will be from transparent to color.

    Returns:
        Image: A PIL Image object with the generated gradient.
    """
    gradient = Image.new('RGBA', (width, height), color=0)
    draw = ImageDraw.Draw(gradient)
    start_alpha = color[3]

    for x in range(width):
        if reverse:
            # Gradient from transparent (left) to color (right)
            alpha = int(start_alpha * (x / width))
        else:
            # Gradient from color (left) to transparent (right)
            alpha = int(start_alpha * (1 - x / width))
        
        # Draw a vertical line with the calculated alpha
        draw.line([(x, 0), (x, height)], fill=(color[0], color[1], color[2], alpha))
        
    return gradient


# --- Main Generator Function ---
def create_rev_killfeed(killer_name, victim_name, killer_agent, victim_agent, weapon, is_headshot=False, is_player_kill=False, is_wallbang=False, numeral=None):
    """
    Generates a Valorant killfeed image.

    Args:
        killer_name (str): The name of the killer.
        victim_name (str): The name of the victim.
        killer_agent (str): The filename of the killer's agent icon (e.g., 'Phoenix.png').
        victim_agent (str): The filename of the victim's agent icon (e.g., 'Sage.png').
        weapon (str): The filename of the weapon icon (e.g., 'Classic.png').
        is_wallbang (bool): If True, adds a wallbang icon before headshot icon.
        is_headshot (bool): If True, adds the headshot icon.
        is_player_kill (bool): If True, adds the yellow 'me' highlight.
    """
    # --- 1. Load Assets and Set Up Canvas ---
    
    # Load font and set sizes
    try:
        font = ImageFont.truetype(FONT_PATH, 60)
    except IOError:
        print(f"Error: Font file not found at {FONT_PATH}")
        print("Please make sure your font file is in 'assets/fonts/' and the FONT_PATH variable is correct.")
        return

    # Define colors
    #BG Colors are fading gradients to transparent
    VICTIM_BG_COLOR = (75, 190, 158, 255) # Teal color
    KILLER_BG_COLOR = (214, 98, 98, 255)   # Red color
    TEXT_COLOR = (255, 255, 255, 255)     # White

    # Define fixed heights and paddings
    IMG_HEIGHT = 128
    AGENT_ICON_SIZE = (256, 128)
    WEAPON_ICON_HEIGHT = 90
    HEADSHOT_ICON_SIZE = (72, 72)
    PADDING = 40
    ME_SIZE = 128
    
    # Load images
    try:
        killer_agent_img = Image.open(os.path.join(ASSETS_PATH, 'agents', killer_agent)).resize(AGENT_ICON_SIZE)
        victim_agent_img = Image.open(os.path.join(ASSETS_PATH, 'agents', victim_agent)).resize(AGENT_ICON_SIZE)
        weapon_img = Image.open(os.path.join(ASSETS_PATH, 'weapons', weapon))
        # Resize weapon icon while maintaining aspect ratio
        ratio = WEAPON_ICON_HEIGHT / weapon_img.height
        weapon_img = weapon_img.resize((int(weapon_img.width * ratio), WEAPON_ICON_HEIGHT))

    except FileNotFoundError as e:
        print(f"Error: Asset file not found. {e}")
        return

    # --- 2. Calculate Dynamic Width ---
    
    # Create a temporary drawing context to measure text width
    temp_draw = ImageDraw.Draw(Image.new('RGB', (0, 0)))
    killer_name_width = temp_draw.textlength(killer_name, font=font)
    victim_name_width = temp_draw.textlength(victim_name, font=font)
    
    # Define widths for central icons
    # weapon_img = weapon_img.resize((int(weapon_img.width * 90 / weapon_img.height), 90))
    weapon_width = weapon_img.width
    headshot_width = 0
    wallbang_width = 0
    if is_headshot:
        try:
            headshot_img = Image.open(os.path.join(ASSETS_PATH, 'icons', 'headshot.png')).resize(HEADSHOT_ICON_SIZE)
            headshot_width = headshot_img.width + 10 # Add padding
        except FileNotFoundError:
            print("Warning: headshot.png not found, skipping.")
            is_headshot = False # Disable if file is missing
            
    if is_wallbang:
        try:
            wallbang_img = Image.open(os.path.join(ASSETS_PATH, 'icons', 'wallbang.png')).resize((72,72))
            wallbang_width = wallbang_img.width + 10 # Add padding
        except FileNotFoundError:
            print("Warning: wallbang.png not found, skipping.")
            is_wallbang = False
            
    # Total width is the sum of all elements and padding
    total_width = (AGENT_ICON_SIZE[0] + PADDING + killer_name_width + PADDING +
                   weapon_width + headshot_width + PADDING  + wallbang_width  +PADDING+
                   victim_name_width + PADDING + AGENT_ICON_SIZE[0])
    
    # --- 3. Create Image and Draw Backgrounds ---

    # Create the main transparent canvas
    final_image = Image.new('RGBA', (int(total_width), IMG_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(final_image)

    # Calculate the midpoint where the two colors will meet
    mid_point_x = AGENT_ICON_SIZE[0] + PADDING + killer_name_width + PADDING + weapon_width + headshot_width + PADDING + PADDING+ wallbang_width 
    mid_point_x_weapon = AGENT_ICON_SIZE[0] + PADDING + killer_name_width + PADDING + (weapon_width / 2)

    # Draw the killer's background (Teal) with a pointed edge
    killer_bg_shape = [
        (0, 0), 
        (mid_point_x - 20, 0), 
        (mid_point_x, IMG_HEIGHT / 2),
        (mid_point_x + -20, IMG_HEIGHT),
        (0, IMG_HEIGHT)
    ]
    draw.polygon(killer_bg_shape, fill=KILLER_BG_COLOR)

    # Draw the victim's background (Red)
    victim_bg_shape = [
        (mid_point_x + -35, 0),
        (total_width, 0),
        (total_width, IMG_HEIGHT),
        (mid_point_x + -35, IMG_HEIGHT),
        (mid_point_x, IMG_HEIGHT / 2)
    ]
    draw.polygon(victim_bg_shape, fill=VICTIM_BG_COLOR)
    
    # --- 4. Paste All Image Layers ---

    # Paste killer agent icon over a slightly right moved image filled with white color
    killer_agent_hightlight = Image.new('RGBA', killer_agent_img.size, (240, 146, 146, 255))
    
    if is_player_kill:
        rect_width, rect_height = 120, 130
        yellow_rect = Image.new('RGBA', (rect_width, rect_height), (231, 237, 131, 255))
        final_image.paste(yellow_rect, (int(total_width - rect_width ), 0))


    final_image.paste(killer_agent_hightlight, (10,0), killer_agent_img)
    final_image.paste(killer_agent_img, (0, 0), killer_agent_img)

    # Paste victim agent icon (horizontally flipped)
    victim_agent_flipped = ImageOps.mirror(victim_agent_img)
    victim_agent_hightlight = Image.new('RGBA', victim_agent_flipped.size, (119, 233, 199, 255))
    final_image.paste(victim_agent_hightlight,(int(total_width - AGENT_ICON_SIZE[0] - 10), 0), victim_agent_flipped)
    final_image.paste(victim_agent_flipped, (int(total_width - AGENT_ICON_SIZE[0]), 0), victim_agent_flipped)

    # Paste weapon icon
    weapon_y = int((IMG_HEIGHT - weapon_img.height) / 2)
    weapon_x = int(mid_point_x_weapon - (weapon_width / 2))
    if "_weapon" in weapon.lower():
        weapon_img = ImageOps.mirror(weapon_img)
    #scale and place weapon so the height of weapon is 120 and width is in same aspect ratio as height
    final_image.paste(weapon_img, (weapon_x, weapon_y), weapon_img)
    
    # Paste wallbang icon if applicable
    if is_wallbang:
        wallbang_y = int((IMG_HEIGHT - wallbang_img.height) / 2)
        wallbang_x = weapon_x + weapon_width + 40
        final_image.paste(wallbang_img, (wallbang_x, wallbang_y), wallbang_img)
        
    # Paste headshot icon if applicable
    if is_headshot:
        headshot_y = int((IMG_HEIGHT - headshot_img.height) / 2)
        headshot_x = weapon_x + weapon_width + wallbang_width + 40
        final_image.paste(headshot_img, (headshot_x, headshot_y), headshot_img)

        

    # Paste "me highlight" if it's a player kill
    # if is_player_kill:
    #     try:
    #         highlight_img = Image.open(os.path.join(ASSETS_PATH, 'ui', 'MeBorder.png'))
    #         highlight_img = highlight_img.resize((600, ME_SIZE))
            
    #         me_highlight = Image.new('RGBA', highlight_img.size, (231,237,131,255))
            
    #         final_image.paste(me_highlight, (-30, 0), highlight_img)
    #     except FileNotFoundError:
    #         print("Warning: me_highlight.png not found, skipping highlight.")

    # --- 5. Draw Text ---
    SHADOW_OFFSET = (1, 1)
    SHADOW_COLOR = (0, 0, 0, 100)  # Black with 50% opacity
    
    # Draw Killer's Name
    killer_text_y = int((IMG_HEIGHT - font.getbbox(killer_name)[3]) / 2)
    killer_text_x = AGENT_ICON_SIZE[0] + PADDING
    
    
    #TEXT SHADOW
    draw.text((killer_text_x + SHADOW_OFFSET[0], killer_text_y + SHADOW_OFFSET[1]),
          killer_name, font=font, fill=SHADOW_COLOR)
    
    #MAIN TEXT
    draw.text((killer_text_x, killer_text_y), killer_name, font=font, fill=TEXT_COLOR)
    
    # Draw Victim's Name
    victim_text_y = int((IMG_HEIGHT - font.getbbox(victim_name)[3]) / 2)
    victim_text_x = int(total_width - AGENT_ICON_SIZE[0] - victim_name_width)
    
    #TEXT SHADOW
    draw.text((victim_text_x + SHADOW_OFFSET[0], victim_text_y + SHADOW_OFFSET[1]),
          victim_name, font=font, fill=SHADOW_COLOR)
    #MAIN TEXT
    draw.text((victim_text_x, victim_text_y), victim_name, font=font, fill=TEXT_COLOR)


    # --- 6. Save the Final Image ---
    output_filename = f"{killer_name}_vs_{victim_name}_{numeral}K_{int(datetime.now().timestamp())}_{'Me' if is_player_kill else ''}.png"
    # output_filename = f"{killer_name}_vs_{victim_name}.png"
    final_output_filename = output_filename
    # time.sleep(0.5)  # Sleep for 0.5 seconds
    final_image.save(os.path.join(OUTPUT_PATH, output_filename))
    print(f"Successfully created killfeed and saved to {os.path.join(OUTPUT_PATH, output_filename)}")
    
    
    """If Me is killer then open the output image we created above and 
    use pillow to merge it side by side with assets/ui/MeBorderTriangle.png"""
    
    
    if is_player_kill:
        try:
            # Load and resize highlight image
            highlight_img = Image.open(os.path.join(ASSETS_PATH, 'ui', 'MeBorder.png'))
            highlight_img = highlight_img.resize((600, ME_SIZE))
            
            # Flip the highlight horizontally
            highlight_img = highlight_img.transpose(Image.FLIP_LEFT_RIGHT)
            
            me_highlight = Image.new('RGBA', highlight_img.size, (231, 237, 131, 255))
            
            # Paste the yellow highlight overlay (mirrored) onto the image (right-aligned)
            final_image.paste(me_highlight, (final_image.width - highlight_img.width + 30, 0), highlight_img)
        except FileNotFoundError:
            print("Warning: me_highlight.png not found, skipping highlight.")

        img = final_image
        img2 = Image.open(os.path.join(ASSETS_PATH, 'ui', 'MeBorderTriangle.png')).convert('RGBA')

        # Flip the triangle horizontally
        img2 = img2.transpose(Image.FLIP_LEFT_RIGHT)

        # Color it yellow using alpha mask
        yellow_overlay = Image.new('RGBA', img2.size, (231, 237, 131, 255))
        img2_colored = Image.new('RGBA', img2.size, (0, 0, 0, 0))
        img2_colored.paste(yellow_overlay, (0, 0), img2)

        # Combine sizes for final image
        new_width = img.width + img2.width
        new_height = max(img.height, img2.height)
        final_image = Image.new('RGBA', (new_width, new_height), (0, 0, 0, 0))

        img2_y = (new_height - img2.height) // 2

        # Paste main image first, then mirrored triangle on the RIGHT
        final_image.paste(img, (0, 0), img)
        final_image.paste(img2_colored, (img.width, img2_y), img2)

        final_output_filename = output_filename
        final_image.save(os.path.join(OUTPUT_PATH, final_output_filename), optimize=False)
        print(f"✅ Applied Me Highlight (mirrored) to {os.path.join(OUTPUT_PATH, final_output_filename)}")


    if numeral:
        image = final_image
        numeral_img = Image.open(os.path.join(ASSETS_PATH, 'ui', f'Rev_Numeral_{numeral}.png')).convert('RGBA')
        
        new_width = image.width + numeral_img.width
        new_height = max(image.height, numeral_img.height)
        
        if is_player_kill:
            final_image = Image.new('RGBA', (new_width, new_height), (0, 0, 0, 0))
            final_image.paste(image, (numeral_img.width, 0), image)
            final_image.paste(numeral_img, (12, 30), numeral_img)
        else:
            final_image = Image.new('RGBA', (new_width, new_height), (0, 0, 0, 0))
            final_image.paste(image, (numeral_img.width, 0), image)
            final_image.paste(numeral_img, (12, 30), numeral_img)

        # Save with new filename
        final_output_filename = output_filename
        final_image.save(os.path.join(OUTPUT_PATH, final_output_filename), optimize=False)
        print(f"✅ Applied Numeral to {os.path.join(OUTPUT_PATH, final_output_filename)}")
    
    # --- Add Solid Background Shapes Underneath to Fix Transparency ---

    # Create a solid background layer (same size as final_image)
    background_layer = Image.new("RGBA", final_image.size, (0, 0, 0, 0))
    bg_draw = ImageDraw.Draw(background_layer)

    # Calculate horizontal offset (final_image might be wider due to numeral or triangle)
    offset_x = background_layer.width - total_width

    # Shift background shapes to the right by offset_x
    killer_bg_shape_shifted = [(x + offset_x, y) for x, y in killer_bg_shape]
    
    # if numeral:
    #     # If numeral is present, shift the victim background shape too
    #     victim_bg_shape_shifted = [(x -10, y) for x, y in victim_bg_shape]
    # else:
    victim_bg_shape_shifted = [(x - 1 , y) for x, y in victim_bg_shape]

    # Redraw background polygons on background layer
    bg_draw.polygon(victim_bg_shape_shifted, fill=VICTIM_BG_COLOR)
    bg_draw.polygon(killer_bg_shape_shifted, fill=KILLER_BG_COLOR)

    # Composite the background under the final image
    final_image = Image.alpha_composite(background_layer, final_image)
    final_image.save(os.path.join(OUTPUT_PATH, final_output_filename), optimize=False)
    
    return os.path.join(OUTPUT_PATH, final_output_filename)