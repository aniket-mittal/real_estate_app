"""
Main script for running web application
"""

import yaml
import cloudinary
import cloudinary.uploader
import cloudinary.api
from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify, g
import os
import glob
from werkzeug.utils import secure_filename
from util import generate_new_AI_images, download_images, save_image_grid
import shutil
import threading
import pandas as pd
import shutil
import stripe
import sqlite3

with open("app/config.yaml", "r") as file:
    config = yaml.safe_load(file)

cloudinary.config(
    cloud_name=config["cloud_name"],
    api_key=config["api_key"],
    api_secret=config["api_secret"]
)

stripe.api_key = config["stripe_api"]

app = Flask(__name__)
app.secret_key = 'rayansucksatmarketing'


DATABASE = "app/customers.db"

# Database connection
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE, check_same_thread=False)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# Initialize the database
def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            username TEXT UNIQUE,
            email TEXT,
            phone_number TEXT,
            password TEXT,
            upload_dir TEXT,
            ai_upload_dir TEXT,
            past_upload_dir TEXT,
            subscription TEXT DEFAULT 'No Plan',
            remaining_photos INTEGER DEFAULT 0
        )""")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            user_id INTEGER PRIMARY KEY,
            status TEXT DEFAULT 'pending',
            result TEXT,
            images TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )""")

        db.commit()

init_db()

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/authenticate', methods=['POST'])
def authenticate():
    db = get_db()
    username_value = request.form.get('username')
    password = request.form.get('password')
    
    user = db.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username_value, password)).fetchone()

    if user:
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['upload_folder'] = user['upload_dir']
        session['ai_upload_folder'] = user['ai_upload_dir']
        session['past_upload_folder'] = user['past_upload_dir']

        for file in glob.glob(os.path.join(session['upload_folder'], '*')):
            os.remove(file)
        for file in glob.glob(os.path.join(session['ai_upload_folder'], '*')):
            os.remove(file)

        return redirect(url_for('dashboard'))
    else:
        return render_template('login.html', error="Invalid credentials, please try again.")

@app.route('/create_account')
def create_account():
    return render_template('create_account.html')

@app.route('/register', methods=['POST'])
def register():
    db = get_db()
    name = request.form.get('name')
    username_value = request.form.get('username')
    email = request.form.get('email')
    phone = request.form.get('phone')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')

    if password != confirm_password:
        return render_template('create_account.html', error="Passwords do not match.")

    upload_folder = f'app/static/customers/{username_value}/uploads'
    ai_upload_folder = f'app/static/customers/{username_value}/AI_uploads'
    past_upload_folder = f'app/static/customers/{username_value}/past_uploads'

    try:
        # Insert new user into the database
        db.execute("""
        INSERT INTO users (name, username, email, phone_number, password, upload_dir, ai_upload_dir, past_upload_dir)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, username_value, email, phone, password, upload_folder, ai_upload_folder, past_upload_folder))
        db.commit()

        # Fetch the newly created user
        user = db.execute("SELECT id FROM users WHERE username = ?", (username_value,)).fetchone()

        if not user:
            return render_template('create_account.html', error="User creation failed. Please try again.")

        # Create directories for user
        os.makedirs(upload_folder, exist_ok=True)
        os.makedirs(ai_upload_folder, exist_ok=True)
        os.makedirs(past_upload_folder, exist_ok=True)

        # Automatically log the user in by setting session variables
        session['user_id'] = user['id']
        print(user['id'])
        session['username'] = username_value
        session['upload_folder'] = upload_folder
        session['ai_upload_folder'] = ai_upload_folder
        session['past_upload_folder'] = past_upload_folder

        return redirect(url_for('dashboard'))
    
    except sqlite3.IntegrityError:
        return render_template('create_account.html', error="Username already exists.")

@app.route('/account_settings')
def account_settings():
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 403
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    user_name = user['name']
    user_plan = user['subscription']
    if user_plan != "Subscription":
        user_plan = ''
    user_email = user['email']
    user_phone = user['phone_number']

    return render_template('account_settings.html', name=user_name, email=user_email, phone=user_phone, plan=user_plan)

@app.route('/delete-account', methods=['POST'])
def delete_account():
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 403

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()

    shutil.rmtree(user['upload_dir'], ignore_errors=True)
    shutil.rmtree(user['ai_upload_dir'], ignore_errors=True)
    shutil.rmtree(user['past_upload_dir'], ignore_errors=True)

    db.execute("DELETE FROM users WHERE id = ?", (session['user_id'],))
    db.execute("DELETE FROM images WHERE user_id = ?", (session['user_id'],))
    db.commit()

    session.clear()
    return jsonify({"message": "Account deleted successfully"}), 200

@app.route("/cancel_subscription", methods=['POST'])
def cancel_subscription():
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 403

    db = get_db()
    db.execute("UPDATE users SET subscription = 'No Plan' WHERE id = ?", (session['user_id'],))
    db.commit()

    return jsonify({"message": "Subscription canceled successfully"}), 200

@app.route('/dashboard')
def dashboard():
    # Fetch user details from the dataframe
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 403
    
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()

    if not user:
        return redirect(url_for('login'))
    
    user_name = user['name']
    subscription_plan = user['subscription']
    remaining_images = user['remaining_photos']
    
    past_upload_folder = user['past_upload_dir']
    if os.path.exists(past_upload_folder):
        processed_images = len([f for f in os.listdir(past_upload_folder) if os.path.isfile(os.path.join(past_upload_folder, f))])
    else:
        processed_images = 0
    
    # Get image file paths
    images = [f"{past_upload_folder}/{img}".replace("app/", "") for img in os.listdir(past_upload_folder)] if processed_images > 0 else []

    return render_template('dashboard.html', 
                           user_name=user_name, 
                           subscription_plan=subscription_plan, 
                           remaining_images=remaining_images, 
                           processed_images=processed_images, 
                           images=images)

@app.route('/payment_options')
def payment_options():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()

    if not user:
        return redirect(url_for('login'))
    
    user_current_subscription = user['subscription']
    print(user_current_subscription)

    return render_template('payment_options.html', current_subscription=user_current_subscription)

@app.route('/previous_images')
def previous_images():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()

    if not user:
        return redirect(url_for('login'))
    
    past_upload_folder = user['past_upload_dir']
    image_files = glob.glob(os.path.join(past_upload_folder, '*'))
    image_urls = [f"{past_upload_folder.replace('app/', '')}/{os.path.basename(img)}" for img in image_files]
    print(image_urls)
    return render_template('previous_images.html', image_files=image_urls)

@app.route('/download_past_uploads')
def download_past_uploads():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()

    if not user:
        return redirect(url_for('login'))
    
    past_upload_folder = user['past_upload_dir']
    ZIP_FILE_PATH = os.path.join(past_upload_folder.replace("app/", "").replace("past_uploads", ""), "past_uploads.zip")
    try:
        # Compress the folder into a zip file
        if not os.path.exists(ZIP_FILE_PATH):
            shutil.make_archive(past_upload_folder, 'zip', past_upload_folder)
        # Serve the zip file
        response = send_file(
            ZIP_FILE_PATH,
            as_attachment=True,
            download_name="images.zip",
            mimetype='application/zip'
        )

        # Delete the zip file after serving
        os.remove("app/" + ZIP_FILE_PATH)

        return response
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/update_payments', methods=['POST'])
def update_payments():
    if 'user_id' not in session:
        return jsonify({"message": "Unauthorized"}), 403
    
    data = request.json
    session['subscription_to_buy'] = data.get('plan')
    session['num_of_images_to_buy'] = data.get('images', 0)
    if session['subscription_to_buy'] == "subscription":
        session['cost_for_purchase'] = 15.00
    elif session['subscription_to_buy'] == "buy_more_images":
        session['cost_for_purchase'] = session['num_of_images_to_buy'] * 0.8
    else:
        session['cost_for_purchase'] = session['num_of_images_to_buy'] * 1.5
    
    return jsonify({"status": "success"})

@app.route('/index')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()

    if not user:
        return redirect(url_for('login'))
    remaining_images = user['remaining_photos']
    return render_template('index.html', remaining_images=remaining_images)

@app.route('/upload', methods=['POST'])
def upload():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()

    if not user:
        return redirect(url_for('login'))

    upload_folder = user['upload_dir']

    # Check if files are in the request
    if 'images' not in request.files:
        return redirect(request.url)

    uploaded_files = request.files.getlist('images')
    session['image_paths'] = []
    session['room_types'] = []  # Initialize room types for each image
    session['upscale_factors'] = []  # Initialize upscale factors for each image
    session['color_schemes'] = []  # Initialize color schemes for each image

    # Save each uploaded file
    for file in uploaded_files:
        if file.filename != '':
            # Secure the filename and save to the upload folder
            filename = secure_filename(file.filename)
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)

            # Store the relative path (relative to the 'static' folder)
            session['image_paths'].append(f"{upload_folder}/{filename}")
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

    # Fetch the current image and index
    image_paths = [path.replace("app/", "") for path in session.get('image_paths', [])]
    print(image_paths)
    current_index = session.get('current_index', 0)

    # If no images, redirect to Room Design
    if not image_paths:
        return redirect(url_for('upload'))

    # Render Preview Page
    return render_template(
        'preview.html',
        image_path=image_paths[current_index],
        index=current_index + 1,
        total=len(image_paths),
        room_type=session['room_types'][current_index],
        upscale_factor=session['upscale_factors'][current_index],
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
            return redirect(url_for('confirm_image'))

    session.modified = True
    return redirect(url_for('preview'))


@app.route('/checkout')
def checkout():
    # Simulate values coming from the backend
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session['subscription_to_buy'] == "buy_more_images":
        plan = "Buy More Images"
    elif session['subscription_to_buy'] == "pay_as_you_go":
        plan = "Pay As You Go"
    else:
        plan = "Subscription"
    return render_template("checkout.html", num_of_images=session['num_of_images_to_buy'], plan=plan, cost=session['cost_for_purchase'])

@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    try:
        # Assume values are coming from the backend
        if session['subscription_to_buy'] == "subscription":
            # Create a Stripe Product
            product = stripe.Product.create(name=f"Subscription Plan - {session['num_of_images_to_buy']} Images")
            
            # Create a Price Object for Subscription
            price = stripe.Price.create(
                unit_amount=int(session['cost_for_purchase'] * 100),  # Convert dollars to cents
                currency="usd",
                recurring={"interval": "month"},
                product=product.id,
            )
        else:
            # Create a Stripe Product
            product = stripe.Product.create(name=f"One-Time Purchase - {session['num_of_images_to_buy']} Images")
            
            # Create a Price Object for One-Time Payment
            price = stripe.Price.create(
                unit_amount=int(session['cost_for_purchase'] * 100),  # Convert dollars to cents
                currency="usd",
                product=product.id,
            )
        print("Price Object Created:", price.id)  # Debugging
        # Create Stripe Checkout Session
        stripe_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price": price.id,
                    "quantity": 1,
                }
            ],
            mode="subscription" if session['subscription_to_buy'] == "subscription" else "payment",
            success_url=url_for('success', _external=True),
            cancel_url=url_for('cancel', _external=True),
        )        
        return jsonify({"id": stripe_session.id})
    except Exception as e:
        return jsonify(error=str(e)), 400

@app.route('/success')
def success():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()

    if not user:
        return redirect(url_for('login'))
    
    num_of_images_to_add = session['num_of_images_to_buy']
    subscription_to_buy = session['subscription_to_buy']

    if subscription_to_buy == "subscription":
        subscription_to_buy = "Subscription"
    if subscription_to_buy == "pay_as_you_go":
        subscription_to_buy = "Pay As You Go"
    
    new_remaining_photos = user['remaining_photos'] + num_of_images_to_add

    db.execute("""
        UPDATE users
        SET remaining_photos = ?, subscription = ?
        WHERE id = ?
    """, (new_remaining_photos, subscription_to_buy, session['user_id']))
    db.commit()

    return redirect(url_for('dashboard',  message="success"))

@app.route('/cancel')
def cancel():
    return redirect(url_for('dashboard',  message="failed"))

@app.route('/confirm_image', methods=['GET', 'POST'])
def confirm_image():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()

    if not user:
        return redirect(url_for('login'))
    
    upload_folder = user['upload_dir']
    image_files = glob.glob(os.path.join(upload_folder, '*'))  # Find all PNG images
    total_images = len(image_files)
    image_urls = [f"{upload_folder}/{os.path.basename(img)}".replace("app/", "") for img in image_files]

    return render_template('confirm_image.html', total_images=total_images, image_urls=image_urls)

@app.route('/download', methods=['GET'])
def download():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    db = get_db()

    # Retrieve user details from the database
    user = db.execute("SELECT upload_dir, ai_upload_dir, past_upload_dir, remaining_photos FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    if not user:
        return redirect(url_for('dashboard', message="error"))

    upload_folder = user['upload_dir']
    ai_upload_folder = user['ai_upload_dir']
    past_upload_folder = user['past_upload_dir']

    # Get list of uploaded images
    image_files = glob.glob(os.path.join(upload_folder, '*'))
    total_images = len(image_files)
    estimated_time = round(total_images * 0.5, 2)

    # Update remaining photo count in the database
    new_remaining_photos = max(user['remaining_photos'] - total_images, 0)
    db.execute("UPDATE users SET remaining_photos = ? WHERE id = ?", (new_remaining_photos, session['user_id']))
    db.commit()

    # Initialize task in the database
    db.execute("""
        INSERT INTO tasks (user_id, status, result, images) 
        VALUES (?, 'processing', NULL, NULL)
        ON CONFLICT(user_id) DO UPDATE SET status='processing', result=NULL, images=NULL
    """, (session['user_id'],))
    db.commit()

    session_data = dict(session.items())

    # Start AI processing in a separate thread
    task_thread = threading.Thread(target=long_task, args=(session_data, session['user_id'], upload_folder, ai_upload_folder, past_upload_folder))
    task_thread.start()

    return render_template('download.html', total_time=estimated_time)


def long_task(session_data, user_id, upload_folder, ai_upload_folder, past_upload_folder):
    """Handles AI image processing in a separate thread and updates the database."""
    
    # Create a new SQLite connection since threads don't have access to Flask's `g` object
    db = sqlite3.connect(DATABASE, check_same_thread=False)
    cursor = db.cursor()

    try:
        cursor.execute("UPDATE tasks SET status='processing' WHERE user_id = ?", (user_id,))
        db.commit()

        # Generate AI images (replace with actual AI processing logic)
        print("AI Generating process started")
        new_image_urls = generate_new_AI_images(session_data, config['url'], config['headers'])
        download_images(new_image_urls, ai_upload_folder)

        # Get AI-generated image files
        image_files_AI = glob.glob(os.path.join(ai_upload_folder, "*"))
        image_urls_AI = [f"{ai_upload_folder}/{os.path.basename(img)}".replace("app/", "") for img in image_files_AI]

        # Move original images to past uploads
        for filename in os.listdir(ai_upload_folder):
            source_path = os.path.join(ai_upload_folder, filename)
            destination_path = os.path.join(past_upload_folder, filename)
            if os.path.isfile(source_path):
                shutil.copy2(source_path, destination_path)

        print("All files copied to past upload directory!")

        # Update task status and store AI images in database
        cursor.execute("""
            UPDATE tasks
            SET status = 'completed', images = ?
            WHERE user_id = ?
        """, (",".join(image_urls_AI), user_id))
        db.commit()

    except Exception as e:
        cursor.execute("UPDATE tasks SET status = 'error', result = ? WHERE user_id = ?", (str(e), user_id))
        db.commit()

    finally:
        db.close()  # Ensure the database connection is closed


@app.route('/check_status', methods=['GET'])
def check_status():
    """Checks the status of the AI processing task from the database."""
    if 'user_id' not in session:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    db = get_db()
    task = db.execute("SELECT status, images FROM tasks WHERE user_id = ?", (session['user_id'],)).fetchone()

    if not task:
        return jsonify({"status": "pending", "images": []})

    return jsonify({
        "status": task["status"],
        "images": task["images"].split(",") if task["images"] else []
    })

@app.route('/download-folder', methods=['GET'])
def download_folder():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    db = get_db()
    
    # Retrieve AI upload directory from the database
    user = db.execute("SELECT ai_upload_dir FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    if not user:
        return jsonify({"error": "User not found"}), 404

    ai_upload_folder = user['ai_upload_dir']
    zip_file_path = os.path.join(ai_upload_folder.replace("app/", "").replace("AI_uploads", ""), "AI_uploads.zip")

    try:
        # Compress the folder into a zip file
        if not os.path.exists(zip_file_path):
            shutil.make_archive(ai_upload_folder, 'zip', ai_upload_folder)
        # Serve the zip file
        response = send_file(
            zip_file_path,
            as_attachment=True,
            download_name="images.zip",
            mimetype='application/zip'
        )

        # Delete the zip file after serving
        os.remove("app/" + zip_file_path)

        return response
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)