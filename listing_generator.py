#!/usr/bin/env python3
"""
Etsy Listing Generator for Print Shop
======================================
Reads a CSV of your images and generates SEO-optimized titles,
13 tags, and short descriptions for each Etsy listing.

Usage:
  py listing_generator.py -i images.csv -o listings_output.csv
  py listing_generator.py -i images.csv --shop "WildShirePrints"
  py listing_generator.py -i images.csv --dry-run
"""

import argparse
import csv
import random
import sys
from pathlib import Path

# Windows UTF-8 fix
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')


# ─────────────────────────────────────────────
# KEYWORD BANKS
# Edit these to match your niche. The more
# specific they are, the better your SEO.
# ─────────────────────────────────────────────

TAG_BANKS = {
    "minimalist": [
        "minimalist wall art", "modern art print", "simple wall decor",
        "scandinavian art", "contemporary print", "clean aesthetic",
        "minimal home decor", "neutral wall art",
    ],
    "landscape": [
        "landscape poster", "nature print", "scenery wall art",
        "outdoor art print", "mountain poster", "forest wall art",
        "landscape art print", "countryside print",
    ],
    "abstract": [
        "abstract art print", "modern abstract", "colorful wall art",
        "abstract poster", "contemporary art", "abstract home decor",
        "bold art print", "geometric art",
    ],
    "botanical": [
        "botanical print", "flower wall art", "plant poster",
        "botanical art print", "floral decor", "greenery wall art",
        "herbal print", "garden wall art",
    ],
    "watercolor": [
        "watercolor print", "watercolor art", "soft pastel print",
        "watercolor poster", "delicate art print", "painterly wall art",
        "hand painted look", "watercolor landscape",
    ],
    "black_and_white": [
        "black and white art", "monochrome print", "b&w wall art",
        "black white poster", "dramatic art print", "high contrast print",
        "timeless wall art", "modern monochrome",
    ],
    "living_room": [
        "living room art", "sofa wall decor", "home interior print",
        "neutral decor", "calming wall art", "family room art",
        "above sofa print", "large wall art",
    ],
    "bedroom": [
        "bedroom wall art", "bedroom decor print", "calming bedroom art",
        "soft bedroom print", "sleep room decor", "restful wall art",
        "bedroom poster", "cozy bedroom art",
    ],
    "office": [
        "office wall art", "workspace decor", "study room print",
        "home office art", "motivating wall art", "professional decor",
        "desk wall print", "creative space art",
    ],
    "dining_room": [
        "dining room art", "kitchen wall decor", "dining room print",
        "food inspired art", "warm home decor", "family dining art",
        "wall art for dining", "cozy dining print",
    ],
    "gift": [
        "gift for her", "gift for him", "housewarming gift",
        "birthday gift art", "anniversary gift", "unique home gift",
        "gift for mom", "gift for dad",
    ],
}

# Generic filler tags (used to reach 13)
GENERIC_TAGS = [
    "wall art", "home decor", "art print", "poster", "interior design",
    "canvas alternative", "room decor", "decor print", "wall decoration",
    "art for home", "print on demand", "instant download", "giclee print",
    "framed art", "unframed print", "a3 poster", "a4 poster",
    "art for living room", "art for bedroom", "modern home",
]

# Title templates
TITLE_TEMPLATES = [
    "{title} | {style} {mood} Art Print | {size} Wall Art for {room} | {use_case} Poster",
    "{title} {style} Print | {mood} {room} Wall Art | {size} {use_case} Decor Poster",
    "{style} {title} | {mood} Art for {room} | {size} {use_case} Wall Print Poster",
    "{title} - {style} {mood} Print | {room} Decor | {size} {use_case} Wall Art",
]

# Description templates
DESCRIPTION_TEMPLATES = [
    (
        "Elevate your {room} with this {style} {mood} print.\n\n"
        "Created by {shop}, this {size} wall art brings a touch of "
        "{style} beauty to your home. Printed on premium 200gsm matte "
        "paper for rich, lasting colour.\n\n"
        "Perfect as a {use_case} gift or to refresh your {room} decor.\n\n"
        "Available in multiple sizes. Free shipping to UK, US, EU, and Canada."
    ),
    (
        "A {style} take on {title} - designed to complement your {room}.\n\n"
        "Each print is produced on heavy 200gsm enhanced matte paper, "
        "ensuring vibrant detail and a premium feel. Framed and unframed "
        "options available.\n\n"
        "Makes a thoughtful {use_case} gift. Shipped free to UK, US, EU "
        "and Canada from our regional print facility."
    ),
    (
        "Bring {mood} vibes to your {room} with this {style} print.\n\n"
        "From the {shop} collection. Printed to order on premium matte "
        "stock for deep, gallery-quality colour. Available in {size} "
        "(additional sizes in shop).\n\n"
        "Ideal for {use_case}. Free worldwide shipping to major markets."
    ),
]


# ─────────────────────────────────────────────
# LOGIC
# ─────────────────────────────────────────────

def generate_tags(style: str, room: str, mood: str, use_case: str,
                  count: int = 13) -> list:
    """Generate 13 tags from the keyword banks."""
    tags = []

    # Pull from relevant banks
    for key in [style, room, mood, use_case]:
        if key in TAG_BANKS:
            tags.extend(TAG_BANKS[key])

    # Add size-related tags
    tags.append("art print")
    tags.append("wall art")

    # Deduplicate while preserving order
    seen = set()
    unique_tags = []
    for t in tags:
        t_lower = t.lower().strip()
        if t_lower not in seen and len(t_lower) <= 20:
            unique_tags.append(t_lower)
            seen.add(t_lower)

    # Fill with generic tags if under count
    random.shuffle(GENERIC_TAGS)
    for t in GENERIC_TAGS:
        if len(unique_tags) >= count:
            break
        if t not in seen:
            unique_tags.append(t)
            seen.add(t)

    return unique_tags[:count]


def generate_title(title: str, style: str, mood: str, room: str,
                   size: str, use_case: str) -> str:
    """Generate an SEO-optimized Etsy title (max 140 chars)."""
    template = random.choice(TITLE_TEMPLATES)
    t = template.format(
        title=title.title(),
        style=style.title(),
        mood=mood.title(),
        room=room.title(),
        size=size.upper(),
        use_case=use_case.title(),
    )
    # Etsy limit is 140 characters
    if len(t) > 140:
        t = t[:137] + "..."
    return t


def generate_description(title: str, style: str, mood: str, room: str,
                         size: str, use_case: str, shop: str) -> str:
    """Generate a listing description."""
    template = random.choice(DESCRIPTION_TEMPLATES)
    return template.format(
        title=title.title(),
        style=style,
        mood=mood,
        room=room,
        size=size.upper(),
        use_case=use_case,
        shop=shop,
    )


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate Etsy listing titles, tags, and descriptions"
    )

    parser.add_argument('--input', '-i', required=True,
                        help="Input CSV file with image metadata")
    parser.add_argument('--output', '-o', default='listings_output.csv',
                        help="Output CSV file (default: listings_output.csv)")
    parser.add_argument('--shop', '-s', default='Midsummer Canvas',
                        help="Your shop name (default: Midsummer Canvas)")
    parser.add_argument('--dry-run', action='store_true',
                        help="Show results without writing file")

    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()

    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        print()
        print("Create a CSV with these columns:")
        print("  title,style,room,mood,use_case,size")
        print()
        print("Example (images.csv):")
        print('  "Sunset Over Mountains","watercolor","living_room","calming","gift","A3"')
        print('  "Forest Path in Mist","minimalist","bedroom","serene","decor","A4"')
        print('  "Ocean Waves Abstract","abstract","office","bold","motivational","A3"')
        sys.exit(1)

    # Read input CSV
    with open(input_path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print("ERROR: No rows found in input CSV.")
        sys.exit(1)

    # Validate columns
    required = {'title', 'style', 'room', 'mood', 'use_case', 'size'}
    actual = set(rows[0].keys())
    missing = required - actual
    if missing:
        print(f"ERROR: Missing required columns: {', '.join(missing)}")
        print(f"  Found columns: {', '.join(actual)}")
        print(f"  Required:      {', '.join(required)}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  ETSY LISTING GENERATOR")
    print(f"{'='*60}")
    print(f"  Input:      {input_path}")
    print(f"  Output:     {output_path}")
    print(f"  Shop:       {args.shop}")
    print(f"  Images:     {len(rows)}")
    print(f"{'='*60}\n")

    # Generate listings
    results = []
    for i, row in enumerate(rows, 1):
        title = row['title'].strip()
        style = row['style'].strip().lower()
        room = row['room'].strip().lower()
        mood = row['mood'].strip().lower()
        use_case = row['use_case'].strip().lower()
        size = row['size'].strip().upper()

        listing_title = generate_title(title, style, mood, room, size, use_case)
        tags = generate_tags(style, room, mood, use_case)
        description = generate_description(title, style, mood, room, size, use_case, args.shop)

        results.append({
            'title': listing_title,
            'tags': '; '.join(tags),
            'description': description,
            'tag_count': len(tags),
            'title_length': len(listing_title),
        })

        if args.dry_run:
            print(f"  [{i}/{len(rows)}] {title}")
            print(f"    Title: {listing_title}")
            print(f"    Tags:  {', '.join(tags)}")
            print(f"    Desc:  {description[:80]}...")
            print()

    if args.dry_run:
        print(f"  Dry run complete. {len(results)} listings generated.")
        return

    # Write output CSV
    fieldnames = ['title', 'tags', 'description', 'tag_count', 'title_length']
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"  Wrote {len(results)} listings to: {output_path}")
    print()
    print(f"  Next steps:")
    print(f"    1. Open the CSV in Excel/Sheets")
    print(f"    2. Copy 'title' column into Etsy listing titles")
    print(f"    3. Copy 'tags' into Etsy tag fields (semicolon-separated)")
    print(f"    4. Copy 'description' into listing descriptions")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
