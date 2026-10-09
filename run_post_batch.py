import json
from pathlib import Path
from listing_bundle import create_listing_bundle, check_dpi
from watermark import watermark_public_files

BATCH = "Batch output"
ETSY = "Etsy"
SETTINGS = Path("watermark_settings.json")


def load_watermark_settings():
    if SETTINGS.exists():
        try:
            return json.loads(SETTINGS.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"enabled": True, "shop_name": "", "watermark_mockups": False,
            "opacity": 110, "position": "bottom_right"}


def main():
    s = load_watermark_settings()
    print(f"[WATERMARK] enabled={s.get('enabled')}  name={s.get('shop_name')!r}  "
          f"mockups={s.get('watermark_mockups', False)}")

    watermark_public_files(
        BATCH,
        logo_path=s.get("logo_path", "logo.png"),
        enabled=s.get("enabled", True),
        watermark_pins=True,
        watermark_mockups=s.get("watermark_mockups", False),
        opacity=s.get("opacity", 180),
        position=s.get("position", "bottom_right"),
    )

    for artwork in sorted(Path(BATCH).iterdir()):
        if artwork.is_dir():
            for b in create_listing_bundle(artwork, etsy_dir=ETSY):
                print(f"  [BUNDLE] {b}")

    check_dpi(BATCH)


if __name__ == "__main__":
    main()
