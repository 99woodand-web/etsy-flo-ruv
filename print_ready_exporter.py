# print_ready_exporter.py

import os
from PIL import Image

def export_print_ready_image(
    mockup_image_path: str,
    output_dir: str = "print_ready_files",
    format: str = "PNG",
    quality: int = 95
) -> str | None:
    """
    Prepares and exports the final mockup image as a print-ready file.
    """
    if not os.path.exists(mockup_image_path):
        print(f"Error: Mockup image file not found at '{mockup_image_path}'")
        return None

    format = format.upper()

    try:
        with Image.open(mockup_image_path) as img:
            print(f"Loading mockup image for export: {os.path.basename(mockup_image_path)}")
            print(f"Image dimensions: {img.size[0]}x{img.size[1]} pixels")
            
            os.makedirs(output_dir, exist_ok=True)
            
            original_file_name = os.path.splitext(os.path.basename(mockup_image_path))[0]
            output_filename = f"{original_file_name}_print_ready.{format.lower()}"
            output_path = os.path.join(output_dir, output_filename)
            
            save_params = {}
            if format == "JPEG":
                if img.mode == 'RGBA': # JPEG does not support alpha channel
                    img = img.convert('RGB')
                save_params['quality'] = quality
                save_params['optimize'] = True
            elif format == "PNG":
                save_params['optimize'] = True
                save_params['dpi'] = img.info.get('dpi', (300, 300))
            elif format == "TIFF":
                save_params['dpi'] = img.info.get('dpi', (300, 300))
            else:
                print(f"Warning: Output format '{format}' not explicitly handled for specific parameters. Saving with defaults.")

            img.save(output_path, format=format, **save_params)
            print(f"Print-ready image successfully exported to: {output_path}")
            print(f"Format: {format}, Quality (JPEG only): {quality}")
            return output_path
            
    except Exception as e:
        print(f"Error during print-ready image export: {e}")
        return None

# This file is primarily for its utility functions. 
# It doesn't have a main execution block for standalone use in the final integrated app.