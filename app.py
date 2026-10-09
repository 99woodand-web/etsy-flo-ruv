# app.py (Updated with Mockup Generation Functionality)

import os
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session, flash
from werkzeug.utils import secure_filename
from PIL import Image
import json # Used for mockup_configs.json, though mockup_generator now handles its loading/saving

# Import backend functionality
from upscaling_resolution_tool import PRINT_SIZES_MM, upscale_image
from mockup_generator import MOCKUP_CONFIGS, generate_mockup, load_mockup_configs # Import MOCKUP_CONFIGS and load_mockup_configs

# --- Configuration Constants ---
UPLOAD_FOLDER = 'uploads'
UPSCALED_FOLDER = 'upscaled_images'
MOCKUP_FOLDER = 'mockup_images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff'}
DEFAULT_DPI = 300

# Create necessary folders if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(UPSCALED_FOLDER, exist_ok=True)
os.makedirs(MOCKUP_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['UPSCALED_FOLDER'] = UPSCALED_FOLDER
app.config['MOCKUP_FOLDER'] = MOCKUP_FOLDER
app.secret_key = 'supersecretkey'

# Load mockup configurations at app startup
load_mockup_configs()

# --- is_image_file function (copied for self-containment of Flask app) ---
def is_image_file(filepath):
    """
    Checks if a given file is a valid image file.
    """
    try:
        with Image.open(filepath) as img:
            img.verify()
        return True
    except (IOError, SyntaxError):
        return False
    except Exception:
        return False

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.before_request
def before_request_load_configs():
    # Ensure configs are always up-to-date before handling a request
    # This is important if mockup_configs.json is edited externally or by a config manager
    load_mockup_configs()

@app.route('/', methods=['GET', 'POST'])
def index():
    uploaded_image_url = session.get('original_image_url')
    upscaled_image_url = session.get('upscaled_image_url')
    generated_mockup_urls = session.get('generated_mockup_urls', [])
    uploaded_filename = session.get('original_image_filename')
    
    if request.method == 'POST':
        # Handle file upload
        if 'file' in request.files:
            file = request.files['file']
            if file.filename == '':
                flash("No file selected.", 'error')
                return redirect(request.url)
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                
                if is_image_file(filepath):
                    session['original_image_path'] = filepath
                    session['original_image_filename'] = filename
                    session['original_image_url'] = url_for('uploaded_file', folder='uploads', filename=filename)
                    session['upscaled_image_path'] = None # Clear previous
                    session['upscaled_image_url'] = None # Clear previous
                    session['generated_mockup_paths'] = [] # Clear previous mockups
                    session['generated_mockup_urls'] = []
                    flash(f"Image '{filename}' uploaded successfully.", 'success')
                    return redirect(url_for('index'))
                else:
                    os.remove(filepath)
                    flash(f"Uploaded file '{filename}' is not a valid image.", 'error')
                    session.pop('original_image_path', None)
                    session.pop('original_image_filename', None)
                    session.pop('original_image_url', None)
                    session.pop('upscaled_image_path', None)
                    session.pop('upscaled_image_url', None)
                    session.pop('generated_mockup_paths', None)
                    session.pop('generated_mockup_urls', None)
                    return redirect(url_for('index'))

        # Handle upscaling
        elif 'upscale_size' in request.form:
            original_image_path = session.get('original_image_path')
            if not original_image_path:
                flash("No image uploaded for upscaling.", 'error')
                return redirect(request.url)
            
            selected_size = request.form['upscale_size']
            if selected_size not in PRINT_SIZES_MM:
                flash("Invalid print size selected.", 'error')
                return redirect(request.url)

            print(f"Upscaling '{session.get('original_image_filename')}' to {selected_size}...")
            upscaled_filepath = upscale_image(
                image_path=original_image_path,
                target_size_name=selected_size,
                dpi=DEFAULT_DPI,
                output_dir=app.config['UPSCALED_FOLDER']
            )

            if upscaled_filepath:
                upscaled_filename = os.path.basename(upscaled_filepath)
                session['upscaled_image_path'] = upscaled_filepath
                session['upscaled_image_url'] = url_for('uploaded_file', folder='upscaled_images', filename=upscaled_filename)
                session['generated_mockup_paths'] = [] # Clear previous mockups
                session['generated_mockup_urls'] = []
                flash(f"Image upscaled to {selected_size} successfully.", 'success')
                return redirect(url_for('index'))
            else:
                session['upscaled_image_path'] = None
                session['upscaled_image_url'] = None
                flash("Upscaling failed. Check server console for details.", 'error')
                return redirect(url_for('index'))
        
        # Handle mockup generation
        elif 'generate_mockups' in request.form:
            upscaled_image_path = session.get('upscaled_image_path')
            if not upscaled_image_path:
                flash("Please upscale an image first before generating mockups.", 'error')
                return redirect(request.url)
            
            selected_mockup_types = request.form.getlist('mockup_type')
            selected_orientation = request.form.get('artwork_orientation')
            preserve_ar = request.form.get('preserve_aspect_ratio') == 'on'
            apply_perspective = request.form.get('apply_perspective') == 'on'

            if not selected_mockup_types:
                flash("Please select at least one Mockup Type.", 'error')
                return redirect(request.url)
            if not selected_orientation:
                flash("Please select an Artwork Orientation.", 'error')
                return redirect(request.url)

            generated_mockup_paths = []
            generated_mockup_urls = []
            
            flash_message = "Mockups generated: "
            error_during_mockup = False

            for m_type in selected_mockup_types:
                print(f"Generating mockup for '{m_type}' with orientation '{selected_orientation}'...")
                mockup_path = generate_mockup(
                    artwork_path=upscaled_image_path,
                    mockup_type=m_type,
                    artwork_orientation=selected_orientation,
                    output_dir=app.config['MOCKUP_FOLDER'],
                    preserve_aspect_ratio=preserve_ar,
                    apply_perspective=apply_perspective
                )
                if mockup_path:
                    generated_mockup_paths.append(mockup_path)
                    mockup_filename = os.path.basename(mockup_path)
                    generated_mockup_urls.append(url_for('uploaded_file', folder='mockup_images', filename=mockup_filename))
                    flash_message += f" {m_type.replace('_', ' ').title()}"
                else:
                    error_during_mockup = True
                    flash(f"Failed to generate mockup for '{m_type}'. Check server console.", 'error')
            
            session['generated_mockup_paths'] = generated_mockup_paths
            session['generated_mockup_urls'] = generated_mockup_urls

            if generated_mockup_paths:
                if error_during_mockup:
                    flash(flash_message + ". Some mockups failed.", 'warning')
                else:
                    flash(flash_message + " successfully.", 'success')
                return redirect(url_for('index'))
            else:
                flash("No mockups were generated successfully. Check server console and mockup configurations.", 'error')
                return redirect(url_for('index'))

    return render_template('index.html', 
                           uploaded_image_url=uploaded_image_url, 
                           upscaled_image_url=upscaled_image_url,
                           generated_mockup_urls=generated_mockup_urls,
                           uploaded_filename=uploaded_filename,
                           print_sizes=PRINT_SIZES_MM.keys(),
                           mockup_types=MOCKUP_CONFIGS.keys())

@app.route('/<folder>/<filename>')
def uploaded_file(folder, filename):
    # Ensure only allowed folders can be accessed
    if folder not in ['uploads', 'upscaled_images', 'mockup_images', 'print_ready_files']: # Add print_ready_files later
        return "Unauthorized folder", 403
    return send_from_directory(os.path.join(app.root_path, folder), filename)

# Placeholder routes for future integration
@app.route('/export_print_ready_action')
def export_print_ready_action():
    return "Print-ready export action would be performed here!"

@app.route('/clear_session')
def clear_session():
    # Clean up files from previous sessions if they exist
    # This is a basic cleanup; a more robust system might use temp files or a cron job
    for key in ['original_image_path', 'upscaled_image_path'] + session.get('generated_mockup_paths', []):
        if key and os.path.exists(key):
            try:
                os.remove(key)
                print(f"Cleaned up: {key}")
            except Exception as e:
                print(f"Error cleaning up {key}: {e}")

    session.clear()
    flash("Session cleared and temporary files removed.", 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    print("Starting Flask Image Uploader GUI...")
    print(f"Uploads will be saved to: {os.path.abspath(UPLOAD_FOLDER)}")
    print(f"Upscaled images will be saved to: {os.path.abspath(UPSCALED_FOLDER)}")
    print(f"Mockup images will be saved to: {os.path.abspath(MOCKUP_FOLDER)}")
    app.run(debug=True)
