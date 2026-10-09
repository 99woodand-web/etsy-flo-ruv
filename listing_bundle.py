import shutil
import zipfile
from pathlib import Path
from PIL import Image


def create_listing_bundle(artwork_folder: str, etsy_dir: str = "Etsy") -> list[str]:
    """
    For one artwork folder (e.g. Batch output/Cornish3/),
    creates a clean Etsy-ready folder per size + a ZIP + listing template.
    """
    artwork_folder = Path(artwork_folder)
    artwork_name = artwork_folder.name
    etsy_dir = Path(etsy_dir)
    etsy_dir.mkdir(parents=True, exist_ok=True)

    created = []

    for size_folder in sorted(artwork_folder.iterdir()):
        if not size_folder.is_dir():
            continue

        size_name = size_folder.name
        bundle_name = f"{artwork_name}_{size_name}"
        bundle_path = etsy_dir / bundle_name
        bundle_path.mkdir(parents=True, exist_ok=True)

        for src_file in sorted(size_folder.iterdir()):
            if not src_file.is_file():
                continue
            dest_name = _clean_filename(src_file, size_name)
            shutil.copy2(src_file, bundle_path / dest_name)

        # --- Listing template ---
        _write_listing_template(bundle_path, artwork_name, size_name)

        # --- ZIP ---
        _zip_bundle(bundle_path)

        created.append(str(bundle_path))

    return created


def _clean_filename(src: Path, size_name: str) -> str:
    stem = src.stem
    suffix = src.suffix

    if "pin" in stem:
        return f"pin_{size_name}{suffix}" if size_name != "pin" else src.name

    if "_on_" in stem:
        scene = stem.split("_on_", 1)[1]
        for token in ("_ar_preserved", "_landscape", "_portrait"):
            scene = scene.replace(token, "")
        scene = scene.strip("_")
        return f"mockup_{scene}{suffix}"

    if "300dpi" in stem:
        return f"print_ready_300dpi{suffix}"

    return stem + suffix


def _write_listing_template(bundle_path: Path, artwork_name: str, size_name: str):
    template = f"""
═══════════════════════════════════════════
  ETSY LISTING — {artwork_name} ({size_name})
═══════════════════════════════════════════

TITLE:
  {artwork_name} — {size_name} Wall Art Print, [Style/Theme] Decor, [Room] Gift

TAGS (up to 13, comma separated):
  [tag1, tag2, tag3, ...]

DESCRIPTION:
  [2–3 sentences about the artwork]

  • Print-ready file at 300 DPI
  • Available in multiple sizes
  • Instant digital download
  • For personal use only

PRICE:
  £/€ $___

SHIPPING:
  [Digital download — no shipping]
═══════════════════════════════════════════
"""
    (bundle_path / "listing_template.txt").write_text(template, encoding="utf-8")


def _zip_bundle(bundle_path: Path):
    """ZIP the entire bundle folder for easy upload."""
    zip_path = bundle_path.parent / f"{bundle_path.name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(bundle_path.iterdir()):
            if f.is_file():
                zf.write(f, f.name)


def check_dpi(folder: str = "Batch output") -> list[str]:
    """
    Scan print-ready files only (exclude mockups and pins) and flag
    any that aren't effectively 300 DPI.
    """
    issues = []
    batch_dir = Path(folder)
    if not batch_dir.exists():
        print(f"[DPI CHECK] Folder not found: {batch_dir.resolve()}")
        return issues

    for artwork in sorted(batch_dir.iterdir()):
        if not artwork.is_dir():
            continue
        for f in sorted(artwork.rglob("*300dpi*")):
            if not (f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg")):
                continue
            # Skip mockups and pins — only check the actual print-ready file
            if "_on_" in f.name or "pin" in f.name:
                continue
            try:
                with Image.open(f) as img:
                    dpi = img.info.get("dpi", (0, 0))
                    dpi_val = dpi[0] if dpi else 0
                    # Allow 1 DPI tolerance for float rounding
                    if abs(dpi_val - 300) > 1:
                        issues.append(f"  \u26a0 {f} \u2192 {dpi_val:.1f} DPI (expected 300)")
            except Exception as e:
                issues.append(f"  \u2716 {f} \u2192 could not read ({e})")

    if issues:
        print("[DPI CHECK] Issues found:")
        for i in issues:
            print(i)
    else:
        print("[DPI CHECK] All print-ready files are 300 DPI \u2714")

    return issues
