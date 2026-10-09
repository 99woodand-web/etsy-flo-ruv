@echo off
cd /d "%~dp0"
py .\main_etsy_print_shop_gui.py
py .\run_post_batch.py
py .\build_images_csv.py
py .\listing_generator.py -i images.csv -o listings_output.csv --shop WildShirePrints
pause