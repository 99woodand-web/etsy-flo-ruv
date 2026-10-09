# upscaling_resolution_tool.py (orientation + quality + fill-crop + crop position)

import os
import shutil
import subprocess
import tempfile
from PIL import Image

PRINT_SIZES_MM = {
    "A4": (210, 297),
    "A3": (297, 420),
    "A2": (420, 594),
    "A1": (594, 841),
}

ESRGAN_EXE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "esrgan", "realesrgan-ncnn-vulkan.exe")


def get_pixel_dimensions(size_name, dpi=300, orientation="portrait"):
    if size_name not in PRINT_SIZES_MM:
        print(f"Error: Unknown print size '{size_name}'. Available sizes: {list(PRINT_SIZES_MM.keys())}")
        return None
    width_mm, height_mm = PRINT_SIZES_MM[size_name]
    if orientation == "landscape":
        width_mm, height_mm = height_mm, width_mm
    return (int((width_mm / 25.4) * dpi), int((height_mm / 25.4) * dpi))


def _crop_to_fit(img, target_w, target_h, position="center"):
    """Crop img to match the aspect ratio of target_w x target_h (no distortion)."""
    sw, sh = img.size
    target_ratio = target_w / target_h
    source_ratio = sw / sh
    if source_ratio > target_ratio:
        new_w = int(sh * target_ratio); new_h = sh
        if position == "left":
            left = 0
        elif position == "right":
            left = sw - new_w
        else:
            left = (sw - new_w) // 2
        top = 0
    else:
        new_w = sw; new_h = int(sw / target_ratio)
        left = 0
        if position == "top":
            top = 0
        elif position == "bottom":
            top = sh - new_h
        else:
            top = (sh - new_h) // 2
    return img.crop((left, top, left + new_w, top + new_h))


def _esrgan_resize(img, target_w, target_h):
    """Upscale with Real-ESRGAN 4x, then Lanczos-resize to exact target size."""
    if not os.path.exists(ESRGAN_EXE):
        print(f"ESRGAN exe not found at '{ESRGAN_EXE}' — falling back to Lanczos.")
        return img.resize((target_w, target_h), Image.LANCZOS)

    tmp_dir = tempfile.mkdtemp(prefix="esrgan_")
    try:
        tmp_input = os.path.join(tmp_dir, "input.png")
        tmp_output = os.path.join(tmp_dir, "esrgan_out.png")
        img.save(tmp_input)

        print(f"Running ESRGAN 4x on {img.size[0]}x{img.size[1]}...")
        result = subprocess.run(
            [ESRGAN_EXE, "-i", tmp_input, "-o", tmp_output, "-s", "4"],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            print(f"ESRGAN error: {result.stderr.strip()}")
            print("Falling back to Lanczos.")
            return img.resize((target_w, target_h), Image.LANCZOS)

        with Image.open(tmp_output) as esrgan_img:
            print(f"ESRGAN 4x output: {esrgan_img.size[0]}x{esrgan_img.size[1]} "
                  f"-> resizing to {target_w}x{target_h}")
            return esrgan_img.resize((target_w, target_h), Image.LANCZOS)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def upscale_image(image_path, target_size_name, dpi=300, output_dir="upscaled_images",
                  orientation="auto", resample="bicubic", fit="fill_crop", crop_pos="center"):
    if not os.path.exists(image_path):
        print(f"Error: Input image file not found at '{image_path}'")
        return None
    try:
        with Image.open(image_path) as img:
            original_width, original_height = img.size
            original_is_portrait = original_width < original_height
            if orientation == "auto":
                target_orientation = "portrait" if original_is_portrait else "landscape"
            else:
                target_orientation = orientation
            target_dimensions = get_pixel_dimensions(target_size_name, dpi, target_orientation)
            if target_dimensions is None:
                return None
            target_width, target_height = target_dimensions
            print(f"Original: {original_width}x{original_height}")
            print(f"Target {target_size_name} ({target_orientation}) @ {dpi} DPI: {target_width}x{target_height}")
            print(f"Resample: {resample}   Fit: {fit}   CropPos: {crop_pos}")
            if original_is_portrait != (target_width < target_height):
                print("Orientation mismatch -> rotating 90 degrees.")
                img = img.transpose(Image.ROTATE_90)
            if fit == "fill_crop":
                img = _crop_to_fit(img, target_width, target_height, crop_pos)
                print(f"After crop: {img.size[0]}x{img.size[1]}")
            if resample == "realesrgan":
                upscaled_img = _esrgan_resize(img, target_width, target_height)
            else:
                resample_filter = Image.BICUBIC if resample == "bicubic" else Image.LANCZOS
                upscaled_img = img.resize((target_width, target_height), resample_filter)
            os.makedirs(output_dir, exist_ok=True)
            original_file_name = os.path.splitext(os.path.basename(image_path))[0]
            fit_tag = "fillcrop" if fit == "fill_crop" else "stretch"
            output_filename = f"{original_file_name}_{target_size_name}_{target_orientation}_{fit_tag}_{dpi}dpi.png"
            output_path = os.path.join(output_dir, output_filename)
            upscaled_img = upscaled_img.convert("RGB")
            upscaled_img.save(output_path, dpi=(dpi, dpi))

            print(f"Saved: {output_path}")
            return output_path
    except Exception as e:
        print(f"Error during image upscaling: {e}")
        return None
