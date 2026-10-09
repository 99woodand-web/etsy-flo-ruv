# pinterest_pin_maker.py
# Creates Pinterest-ready vertical pin images from mockup images.

import os
from PIL import Image, ImageDraw, ImageFont

# Common font paths (Windows)
FONT_PATHS = {
    "arial": "C:/Windows/Fonts/arial.ttf",
    "arial_bold": "C:/Windows/Fonts/arialbd.ttf",
    "calibri": "C:/Windows/Fonts/calibri.ttf",
    "calibri_bold": "C:/Windows/Fonts/calibrib.ttf",
    "verdana": "C:/Windows/Fonts/verdana.ttf",
    "verdana_bold": "C:/Windows/Fonts/verdanab.ttf",
    "georgia": "C:/Windows/Fonts/georgia.ttf",
    "georgia_bold": "C:/Windows/Fonts/georgiab.ttf",
}

def _get_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    """Load a system font, falling back to default if not found."""
    path = FONT_PATHS.get(name, FONT_PATHS["arial"])
    try:
        return ImageFont.truetype(path, size)
    except (IOError, OSError):
        # Fallback: try a relative name (works on some systems)
        try:
            return ImageFont.truetype(name, size)
        except (IOError, OSError):
            return ImageFont.load_default()


def create_pinterest_pin(
    mockup_path: str,
    output_dir: str = "pinterest_pins",
    pin_width: int = 1000,
    pin_height: int = 1500,
    bg_color: str = "#ffffff",
    title: str = "",
    subtitle: str = "",
    text_color: str = "#333333",
    font_name: str = "arial",
    font_size: int = 52,
    subtitle_font_size: int = 36,
    mockup_position: str = "top",
    mockup_margin: int = 40
) -> str | None:
    """
    Creates a Pinterest pin from a mockup image.

    Args:
        mockup_path: Path to the mockup image to use.
        output_dir: Directory to save the pin.
        pin_width: Pin width in px (default 1000).
        pin_height: Pin height in px (default 1500 for standard, 2100 for tall).
        bg_color: Background colour as hex (e.g. "#ffffff").
        title: Main title text (optional).
        subtitle: Subtitle / shop name text (optional).
        text_color: Text colour as hex.
        font_name: Font key (arial, arial_bold, calibri, calibri_bold,
                   verdana, verdana_bold, georgia, georgia_bold).
        font_size: Title font size in px.
        subtitle_font_size: Subtitle font size in px.
        mockup_position: Where to place the mockup: "top", "center", or "bottom".
        mockup_margin: Padding around the mockup in px.

    Returns:
        str: Path to the saved pin, or None on error.
    """
    if not os.path.exists(mockup_path):
        print(f"[PIN] Error: Mockup not found: {mockup_path}")
        return None

    try:
        # Create the pin canvas
        pin = Image.new("RGB", (pin_width, pin_height), bg_color)
        draw = ImageDraw.Draw(pin)

        # Load and resize the mockup to fit the pin width
        with Image.open(mockup_path) as mockup:
            if mockup.mode != "RGB":
                mockup = mockup.convert("RGB")
            orig_w, orig_h = mockup.size

            # Fit to pin width (with margins)
            available_w = pin_width - (mockup_margin * 2)
            available_h = pin_height - (mockup_margin * 2)
            scale = min(available_w / orig_w, available_h / orig_h)
            new_w = int(orig_w * scale)
            new_h = int(orig_h * scale)
            mockup = mockup.resize((new_w, new_h), Image.LANCZOS)

        # Calculate mockup position
        mockup_x = (pin_width - new_w) // 2
        if mockup_position == "top":
            mockup_y = mockup_margin
        elif mockup_position == "bottom":
            mockup_y = pin_height - new_h - mockup_margin
        else:  # center
            mockup_y = (pin_height - new_h) // 2

        # Paste the mockup
        pin.paste(mockup, (mockup_x, mockup_y))

        # Add text
        if title or subtitle:
            title_font = _get_font(font_name, font_size)
            sub_font = _get_font(font_name, subtitle_font_size)

            # Calculate text block height
            text_block_h = 0
            if title:
                text_block_h += font_size + 10
            if subtitle:
                text_block_h += subtitle_font_size + 10

            # Position the text block
            if mockup_position == "top" and text_block_h > 0:
                # Text goes below the mockup
                text_y = mockup_y + new_h + 20
            elif mockup_position == "bottom" and text_block_h > 0:
                # Text goes above the mockup
                text_y = mockup_y - text_block_h - 10
            else:
                # Center
                text_y = (pin_height + mockup_y + new_h) // 2 - text_block_h // 2

            # Draw title
            if title:
                bbox = draw.textbbox((0, 0), title, font=title_font)
                tw = bbox[2] - bbox[0]
                tx = (pin_width - tw) // 2
                draw.text((tx, text_y), title, fill=text_color, font=title_font)
                text_y += font_size + 10

            # Draw subtitle
            if subtitle:
                bbox = draw.textbbox((0, 0), subtitle, font=sub_font)
                sw = bbox[2] - bbox[0]
                sx = (pin_width - sw) // 2
                draw.text((sx, text_y), subtitle, fill=text_color, font=sub_font)

        # Save
        os.makedirs(output_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(mockup_path))[0]
        output_path = os.path.join(output_dir, f"{base}_pin_{pin_width}x{pin_height}.png")
        pin.save(output_path, "PNG", optimize=True)
        print(f"[PIN] Saved: {output_path} ({pin_width}x{pin_height})")
        return output_path

    except Exception as e:
        print(f"[PIN] Error: {e}")
        return None
