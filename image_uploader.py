# image_uploader_manager.py

import os
from PIL import Image

def is_image_file(filepath):
    """
    Checks if a given file is a valid image file.
    
    Args:
        filepath (str): The path to the file to check.
        
    Returns:
        bool: True if the file is a recognized image, False otherwise.
    """
    try:
        # Attempt to open and verify the image.
        # This will raise an exception for non-image files or corrupted ones.
        with Image.open(filepath) as img:
            img.verify()
        return True
    except (IOError, SyntaxError):
        # IOError for file not found or cannot be opened.
        # SyntaxError for certain malformed image files.
        return False
    except Exception:
        # Catch any other unexpected exceptions during image opening/verification
        return False

# This file is primarily for its utility function. 
# It is designed to be imported by other modules (like main_etsy_print_shop_gui.py),
# and does not have a main execution block for standalone use in the final integrated app.