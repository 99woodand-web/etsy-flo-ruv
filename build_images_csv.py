"""
Reads Batch output/ folder structure and writes images.csv
for listing_generator.py to consume.
"""
import csv
from pathlib import Path

BATCH = "Batch output"
OUTPUT = "images.csv"

# Defaults for fields that can't be derived from filenames.
# Edit these to match your typical listing.
DEFAULTS = {
    "style": "line_art",
    "mood": "calm",
    "use_case": "gift",
}


def extract_room(filename: str) -> str:
    """Pull the room name from a mockup filename like
    'Cornish3_A3_..._on_living_room_landscape_ar_preserved.png'
    """
    if "_on_" in filename:
        after = filename.split("_on_", 1)[1]
        # Grab words until we hit a technical token
        for token in ("_landscape", "_portrait", "_ar_preserved"):
            after = after.replace(token, "")
        room = after.split("_pin_")[0].strip("_")
        return room
    return "living_room"


def main():
    batch_dir = Path(BATCH)
    if not batch_dir.exists():
        print(f"[CSV] Folder not found: {batch_dir.resolve()}")
        return

    rows = []
    for artwork in sorted(batch_dir.iterdir()):
        if not artwork.is_dir():
            continue
        for size_dir in sorted(artwork.iterdir()):
            if not size_dir.is_dir() or size_dir.name == "pin":
                continue
            # Find a mockup file in this size folder to extract the room
            room = DEFAULTS["mood"]  # fallback
            for f in size_dir.iterdir():
                if f.is_file() and "_on_" in f.name:
                    room = extract_room(f.name)
                    break

            rows.append({
                "title": artwork.name,
                "style": DEFAULTS["style"],
                "room": room,
                "mood": DEFAULTS["mood"],
                "use_case": DEFAULTS["use_case"],
                "size": size_dir.name,
            })

    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["title", "style", "room", "mood", "use_case", "size"])
        w.writeheader()
        w.writerows(rows)

    print(f"[CSV] Wrote {len(rows)} rows to {OUTPUT}")
    for r in rows:
        print(f"  {r['title']} | {r['size']} | {r['room']}")


if __name__ == "__main__":
    main()
