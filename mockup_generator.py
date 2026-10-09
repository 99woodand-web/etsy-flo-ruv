# mockup_generator.py

import os
from PIL import Image
import numpy as np
import cv2
import json

# --- Configuration File Path ---
MOCKUP_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mockup_configs.json")

# --- Default Mockup Configuration Data ---
DEFAULT_MOCKUP_CONFIGS = {
    "living_room": {
        "template_path": "living_room_mockup.jpg",
        "position_data": {
            "landscape": [[450, 180], [750, 190], [760, 500], [440, 490]],
            "portrait":  [[580, 100], [680, 110], [690, 600], [570, 590]],
        }
    },
    "kitchen": {
        "template_path": "kitchen_mockup.jpg",
        "position_data": {
            "landscape": [[350, 100], [650, 110], [660, 450], [340, 440]],
            "portrait":  [[480, 80], [550, 90], [560, 500], [470, 490]],
        }
    },
    "bedroom": {
        "template_path": "bedroom_mockup.jpg",
        "position_data": {
            "landscape": [[400, 200], [800, 210], [810, 600], [390, 590]],
            "portrait":  [[550, 150], [650, 160], [660, 700], [540, 690]],
        }
    }
}

# Global variable to hold current mockup configurations
MOCKUP_CONFIGS = {}

def load_mockup_configs():
    """Loads mockup configurations from a JSON file."""
    global MOCKUP_CONFIGS
    if os.path.exists(MOCKUP_CONFIG_FILE):
        try:
            with open(MOCKUP_CONFIG_FILE, 'r') as f:
                MOCKUP_CONFIGS = json.load(f)
            print(f"Loaded mockup configurations from {MOCKUP_CONFIG_FILE}")
        except json.JSONDecodeError as e:
            print(f"Error reading {MOCKUP_CONFIG_FILE}: {e}. Loading default configurations.")
            MOCKUP_CONFIGS = DEFAULT_MOCKUP_CONFIGS.copy()
            save_mockup_configs()
    else:
        print(f"{MOCKUP_CONFIG_FILE} not found. Loading default configurations.")
        MOCKUP_CONFIGS = DEFAULT_MOCKUP_CONFIGS.copy()
        save_mockup_configs()

# Load configs immediately when the module is imported
load_mockup_configs()

def save_mockup_configs():
    """Saves the current mockup configurations to the JSON file."""
    global MOCKUP_CONFIGS
    with open(MOCKUP_CONFIG_FILE, 'w') as f:
        json.dump(MOCKUP_CONFIGS, f, indent=4)
    print(f"[TM-SAVE] wrote: {MOCKUP_CONFIG_FILE}")
    for name, cfg in MOCKUP_CONFIGS.items():
        print(f"[TM-SAVE]   {name} landscape = {cfg['position_data']['landscape']}")


def apply_perspective_transform(artwork_img_pil, target_quad):
    """
    Applies a perspective transformation to the artwork image.

    Args:
        artwork_img_pil (PIL.Image): The artwork image to transform.
        target_quad (list): A list of 4 (x, y) tuples representing the
                            target quadrilateral corners on the mockup.
                            Order: Top-Left, Top-Right, Bottom-Right, Bottom-Left.

    Returns:
        PIL.Image: The perspective-transformed artwork, or None if error.
    """
    try:
        artwork_cv = np.array(artwork_img_pil)
        if artwork_cv.shape[2] == 3:  # If RGB, convert to RGBA
            artwork_cv = cv2.cvtColor(artwork_cv, cv2.COLOR_RGB2RGBA)

        height, width, _ = artwork_cv.shape
        source_quad = np.float32([[0, 0], [width, 0], [width, height], [0, height]])
        target_quad_np = np.float32(target_quad)

        matrix = cv2.getPerspectiveTransform(source_quad, target_quad_np)

        max_x_coord = int(max(p[0] for p in target_quad))
        max_y_coord = int(max(p[1] for p in target_quad))

        warped_image_data = cv2.warpPerspective(
            artwork_cv, matrix, (max_x_coord + 1, max_y_coord + 1),
            flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_TRANSPARENT
        )

        return Image.fromarray(warped_image_data)

    except Exception as e:
        print(f"Error during perspective transform: {e}")
        return None


def generate_mockup(
    artwork_path: str,
    mockup_type: str,
    artwork_orientation: str,
    output_dir: str = "mockup_images",
    preserve_aspect_ratio: bool = True,
    apply_perspective: bool = False
) -> str | None:
    """
    Superimposes artwork onto a specified mockup template with correct orientation,
    optionally preserving artwork aspect ratio and applying perspective transformation.
    """
    if mockup_type not in MOCKUP_CONFIGS:
        print(f"Error: Unknown mockup type '{mockup_type}'. Available types: {list(MOCKUP_CONFIGS.keys())}")
        return None

    if artwork_orientation not in MOCKUP_CONFIGS[mockup_type]["position_data"]:
        print(f"Error: Orientation '{artwork_orientation}' not configured for mockup type '{mockup_type}'.")
        return None

    config = MOCKUP_CONFIGS[mockup_type]
    mockup_template_path = config["template_path"]

    target_quad = config["position_data"][artwork_orientation]

    # ── KEY FIX: check both the function parameter AND the JSON config ──
    use_perspective = apply_perspective or config.get("perspective", False)

    # Calculate bounding box from target_quad for traditional resize fallback
    min_x = int(min(p[0] for p in target_quad))
    max_x = int(max(p[0] for p in target_quad))
    min_y = int(min(p[1] for p in target_quad))
    max_y = int(max(p[1] for p in target_quad))

    target_width_bb = max_x - min_x
    target_height_bb = max_y - min_y
    target_x_bb = min_x
    target_y_bb = min_y

    if not os.path.exists(artwork_path):
        print(f"Error: Artwork file not found at '{artwork_path}'")
        return None
    if not os.path.exists(mockup_template_path):
        print(f"Error: Mockup template file not found at '{mockup_template_path}'")
        return None

    try:
        with Image.open(mockup_template_path) as mockup_img:
            with Image.open(artwork_path) as artwork_img:
                print(f"Loading mockup: {os.path.basename(mockup_template_path)} ({mockup_img.size[0]}x{mockup_img.size[1]})")
                print(f"Loading artwork: {os.path.basename(artwork_path)} ({artwork_img.size[0]}x{artwork_img.size[1]})")

                processed_artwork = None
                paste_coords = (target_x_bb, target_y_bb)

                if use_perspective:
                    processed_artwork = apply_perspective_transform(artwork_img, target_quad)
                    if processed_artwork is None:
                        raise Exception("Perspective transformation failed.")
                    paste_coords = (0, 0)

                else:  # No perspective, use traditional resize
                    if preserve_aspect_ratio:
                        original_artwork_width, original_artwork_height = artwork_img.size
                        width_ratio = target_width_bb / original_artwork_width
                        height_ratio = target_height_bb / original_artwork_height
                        scale_factor = min(width_ratio, height_ratio)

                        new_artwork_width = int(original_artwork_width * scale_factor)
                        new_artwork_height = int(original_artwork_height * scale_factor)

                        paste_x = target_x_bb + (target_width_bb - new_artwork_width) // 2
                        paste_y = target_y_bb + (target_height_bb - new_artwork_height) // 2

                        processed_artwork = artwork_img.resize((new_artwork_width, new_artwork_height), Image.LANCZOS)
                        paste_coords = (paste_x, paste_y)
                    else:
                        paste_x = target_x_bb
                        paste_y = target_y_bb
                        processed_artwork = artwork_img.resize((target_width_bb, target_height_bb), Image.LANCZOS)
                        paste_coords = (paste_x, paste_y)

                if processed_artwork.mode != 'RGBA':
                    processed_artwork = processed_artwork.convert('RGBA')

                if mockup_img.mode != 'RGBA':
                    mockup_img = mockup_img.convert('RGBA')
                from PIL import ImageFilter
                processed_artwork = processed_artwork.filter(
                    ImageFilter.UnsharpMask(radius=1.5, percent=70, threshold=2)
                )

                mockup_img.paste(processed_artwork, paste_coords, processed_artwork)

                os.makedirs(output_dir, exist_ok=True)

                artwork_filename = os.path.splitext(os.path.basename(artwork_path))[0]
                mockup_filename_base = os.path.splitext(os.path.basename(mockup_template_path))[0]

                output_filename_suffix = ""
                if use_perspective:
                    output_filename_suffix += "_perspective"
                elif preserve_aspect_ratio:
                    output_filename_suffix += "_ar_preserved"
                else:
                    output_filename_suffix += "_stretched"

                output_filename = f"{artwork_filename}_on_{mockup_type}_{artwork_orientation}{output_filename_suffix}.png"
                output_path = os.path.join(output_dir, output_filename)
                mockup_img.save(output_path)
                print(f"Mockup generated and saved to: {output_path}")
                return output_path

    except Exception as e:
        print(f"Error during mockup generation: {e}")
        return None
