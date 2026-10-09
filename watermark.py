from pathlib import Path
from PIL import Image, ImageDraw


def apply_watermark(image_path, logo_path, opacity=180,
                    position="bottom_right", margin=20):
    """Overlay a logo image onto an image, save in place."""
    image_path = Path(image_path)
    logo_path = Path(logo_path)

    img = Image.open(image_path).convert("RGBA")
    logo = Image.open(logo_path).convert("RGBA")

    W, H = img.size
    original_dpi = img.info.get("dpi", (300, 300))

    # Scale logo to ~25% of image width (max 300px)
    logo_target_w = min(int(W * 0.40), 400)
    ratio = logo_target_w / logo.size[0]
    logo_resized = logo.resize((logo_target_w, int(logo.size[1] * ratio)), Image.LANCZOS)

    # Apply opacity to the logo
    if opacity < 255:
        r, g, b, a = logo_resized.split()
        a = a.point(lambda x: int(x * opacity / 255))
        logo_resized = Image.merge("RGBA", (r, g, b, a))

    # Position
    lw, lh = logo_resized.size
    if position == "bottom_right":
        x, y = W - lw - margin, H - lh - margin
    elif position == "bottom_center":
        x, y = (W - lw) // 2, H - lh - margin
    elif position == "top_right":
        x, y = W - lw - margin, margin
    else:  # bottom_left
        x, y = margin, H - lh - margin

    img.paste(logo_resized, (x, y), logo_resized)

    # Save
    if image_path.suffix.lower() in (".jpg", ".jpeg"):
        img.convert("RGB").save(image_path, quality=95, dpi=original_dpi)
    else:
        img.save(image_path, dpi=original_dpi)

def watermark_public_files(batch_folder="Batch output", logo_path="logo.png",
                           enabled=True, watermark_pins=True,
                           watermark_mockups=False, opacity=180,
                           position="bottom_right"):
    results = []
    if not enabled:
        print("[WATERMARK] Disabled — skipping.")
        return results
    if not Path(logo_path).exists():
        print(f"[WATERMARK] Logo not found: {logo_path}")
        return results

    batch_dir = Path(batch_folder)
    if not batch_dir.exists():
        print(f"[WATERMARK] Folder not found: {batch_dir.resolve()}")
        return results

    for f in sorted(batch_dir.rglob("*.png")):
        if not f.is_file():
            continue
        is_pin = "pin" in f.name.lower()
        is_mockup = "_on_" in f.name
        is_print_ready = ("300dpi" in f.name) and not is_mockup and not is_pin

        if is_print_ready:
            continue

        target = (is_pin and watermark_pins) or (is_mockup and watermark_mockups)
        if not target:
            continue
        try:
            apply_watermark(f, logo_path, opacity=opacity, position=position)
            results.append(str(f))
            print(f"  [WATERMARK] {f.name}")
        except Exception as e:
            print(f"  [WATERMARK ERROR] {f.name}: {e}")

    print(f"[WATERMARK] Done — {len(results)} file(s) watermarked.")
    return results

