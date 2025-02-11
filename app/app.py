"""
Main script for running web application
"""

import yaml
import cloudinary
import cloudinary.uploader
import cloudinary.api
from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify
import os
import glob
from werkzeug.utils import secure_filename
from util import generate_new_AI_images, download_images, save_image_grid
import shutil
import threading

with open("app/config.yaml", "r") as file:
    config = yaml.safe_load(file)

cloudinary.config(
    cloud_name=config["cloud_name"],
    api_key=config["api_key"],
    api_secret=config["api_secret"]
)

app = Flask(__name__)
app.secret_key = 'supersecretkey'
files = 0

# Configure the upload folder
UPLOAD_FOLDER = os.path.join('app/static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create the upload folder if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/')
def index():
    # Path to the uploads folder
    uploads_folder = os.path.join(app.root_path, 'static/uploads')

    # Clear all files in the uploads folder
    for file in glob.glob(os.path.join(uploads_folder, '*')):
        os.remove(file)

    # Reset the session variables
    session.clear()

    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    global files
    # Check if files are in the request
    if 'images' not in request.files:
        return redirect(request.url)

    files = 0
    uploaded_files = request.files.getlist('images')
    session['image_paths'] = []
    session['room_types'] = []  # Initialize room types for each image
    session['upscale_factors'] = []  # Initialize upscale factors for each image
    session['color_schemes'] = []  # Initialize color schemes for each image

    # Save each uploaded file
    for file in uploaded_files:
        if file.filename != '':
            # Secure the filename and save to the upload folder
            files += 1
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            # Store the relative path (relative to the 'static' folder)
            session['image_paths'].append(f"uploads/{filename}")
            session['room_types'].append("")  # Default room type as empty string
            session['upscale_factors'].append("")  # Default upscale factor as empty string
            session['color_schemes'].append("")  # Default color scheme as empty string

    session['current_index'] = 0  # Initialize current index
    session['selected_room_style'] = ''
    session['selected_specialty_decor'] = ''
    session.modified = True  # Ensure session changes are saved

    # Redirect to Room Design first
    return redirect(url_for('room_design'))


@app.route('/room_design', methods=['GET', 'POST'])
def room_design():
    if request.method == 'POST':
        # Save the selected room style
        selected_style = request.form.get('design_style')
        if selected_style:
            session['selected_room_style'] = selected_style
            session.modified = True
            return redirect(url_for('preview'))  # Navigate to Preview page

    # Render Room Design Page
    design_photos_dir = os.path.join(app.static_folder, 'design_photos')
    design_styles = [
        filename for filename in os.listdir(design_photos_dir) if filename.endswith(('.jpg', '.png'))
    ]
    default_image = 'generic.jpg'
    return render_template('room_design.html', design_styles=design_styles, default_image=default_image)


@app.route('/preview', methods=['GET', 'POST'])
def preview():
    if request.method == 'POST':
        selected_room_type = request.form.get('room_type')
        selected_upscale_factor = request.form.get('upscale_factor')
        selected_color_scheme = request.form.get('color_scheme')
        current_index = session.get('current_index', 0)

        # Update session data
        if selected_room_type:
            session['room_types'][current_index] = selected_room_type
        if selected_upscale_factor:
            session['upscale_factors'][current_index] = selected_upscale_factor
        if selected_color_scheme:
            session['color_schemes'][current_index] = selected_color_scheme

        session.modified = True

    # Initialize session variables if not already present
    if 'image_paths' not in session:
        session['image_paths'] = []
    if 'room_types' not in session:
        session['room_types'] = ["" for _ in session['image_paths']]
    if 'upscale_factors' not in session:
        session['upscale_factors'] = ["1" for _ in session['image_paths']]
    if 'color_schemes' not in session:
        session['color_schemes'] = ["Default" for _ in session['image_paths']]

    # Fetch the current image and index
    image_paths = session.get('image_paths', [])
    current_index = session.get('current_index', 0)

    # If no images, redirect to Room Design
    if not image_paths:
        return redirect(url_for('room_design'))

    # Render Preview Page
    return render_template(
        'preview.html',
        image_path=image_paths[current_index],
        index=current_index + 1,
        total=len(image_paths),
        room_type=session['room_types'][current_index],
        upscale_factor=session['upscale_factors'][current_index],
        color_scheme=session['color_schemes'][current_index],
        color_schemes=[
            "Default",
            "Moss Green, Tan, White",
            "Gray, Sand, Blue",
            "Hunter Green, Red",
            "White, Pops of Color",
            "Blue, Neon",
            "Light Blue, Emerald",
            "Blue, Grass Green",
            "Blue, Beige",
            "Gray, Brown",
            "Black, Red",
            "Gray-Green, White, Black",
            "Blue, Gray, Taupe",
            "Black, Navy",
            "Emerald, Tan",
            "Forest Green, Light Gray",
            "Yellow, Gray",
            "Pink, Green",
            "Blush Pink, Black",
            "Black, White",
            "Blue, White"
        ],
        enumerate=enumerate
    )

@app.route('/navigate', methods=['POST'])
def navigate():
    direction = request.form.get('direction')

    # Ensure current_index is initialized
    if 'current_index' not in session:
        session['current_index'] = 0

    current_index = session['current_index']

    if direction == 'back':
        if current_index == 0:
            return redirect(url_for('room_design'))  # Redirect to Room Design for the first image
        session['current_index'] -= 1
    elif direction == 'next':
        if current_index < len(session.get('image_paths', [])) - 1:
            session['current_index'] += 1
        else:
            return redirect(url_for('specialty_decor'))  # Redirect to Specialty Decor page

    session.modified = True
    return redirect(url_for('preview'))


@app.route('/specialty_decor', methods=['GET', 'POST'])
def specialty_decor():
    if request.method == 'POST':
        # Save the selected specialty decor style
        selected_decor = request.form.get('design_style')
        print(selected_decor)
        if selected_decor:
            session['selected_specialty_decor'] = selected_decor
            session.modified = True
            return redirect(url_for('download'))  # Navigate to Download page

    # Render Specialty Decor Page
    decor_buttons = [
        (1, "Halloween"),
        (2, "Christmas"),
        (3, "Thanksgiving"),
        (4, "Fall"),
        (5, "Spring"),
        (6, "Summer"),
        (7, "Winter")
    ]
    default_image = 'generic.jpg'
    return render_template('specialty_decor.html', buttons=decor_buttons, default_image=default_image)


# Global variable to track task status
task_status = {"status": "pending", "result": None}

@app.route('/download', methods=['GET'])
def download():
    def long_task():
        global task_status
        try:
            task_status["status"] = "processing"
            # Perform long-running tasks
            new_image_urls = generate_new_AI_images(session_data, config['url'], config['headers'])
            download_images(new_image_urls, "app/static/AI_uploads/")
            task_status["status"] = "completed"
        except Exception as e:
            task_status["status"] = "error"
            task_status["result"] = str(e)

    # Start the task in a new thread
    session_data = dict(session.items())
    task_thread = threading.Thread(target=long_task)
    task_thread.start()

    # Render the page with a loading screen
    return render_template('download.html')

@app.route('/check-task-status', methods=['GET'])
def check_task_status():
    return jsonify(task_status)

@app.route('/download-folder', methods=['GET'])
def download_folder():
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    FOLDER_PATH = os.path.join(BASE_DIR, "static/AI_uploads")
    ZIP_FILE_PATH = os.path.join(BASE_DIR, "static/AI_uploads.zip")
    try:
        # Compress the folder into a zip file
        if not os.path.exists(ZIP_FILE_PATH):
            shutil.make_archive(FOLDER_PATH, 'zip', FOLDER_PATH)

        # Serve the zip file
        response = send_file(
            ZIP_FILE_PATH,
            as_attachment=True,
            download_name="folder.zip",
            mimetype='application/zip'
        )

        # Delete the zip file after serving
        os.remove(ZIP_FILE_PATH)

        return response
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)