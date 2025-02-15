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
import pandas as pd
import shutil
import stripe

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
files = 0

UPLOAD_FOLDER = ''
AI_UPLOAD_FOLDER = ''
PAST_UPLOAD_FOLDER = ''
username = ''
user_csv_file = pd.read_csv('app/customers_info.csv')
num_of_images_to_buy = 0
subscription_to_buy = ''
cost_for_purchase = 0

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/authenticate', methods=['POST'])
def authenticate():
    global UPLOAD_FOLDER, AI_UPLOAD_FOLDER, PAST_UPLOAD_FOLDER, username, user_csv_file
    username_value = request.form.get('username')
    password = request.form.get('password')
    
    if username_value in user_csv_file['username'].values and password ==  user_csv_file.loc[user_csv_file['username'] == username_value, 'password'].iloc[0]: 
        session['user'] = username_value
        username = username_value
        UPLOAD_FOLDER = user_csv_file.loc[user_csv_file['username'] == username, 'upload_dir'].iloc[0]
        AI_UPLOAD_FOLDER = user_csv_file.loc[user_csv_file['username'] == username, 'ai_upload_dir'].iloc[0]
        PAST_UPLOAD_FOLDER = user_csv_file.loc[user_csv_file['username'] == username, 'past_upload_dir'].iloc[0]
        for file in glob.glob(os.path.join(UPLOAD_FOLDER, '*')):
            os.remove(file)
        for file in glob.glob(os.path.join(AI_UPLOAD_FOLDER, '*')):
            os.remove(file)
        return redirect(url_for('dashboard'))
    else:
        return render_template('login.html', error="Invalid credentials, please try again.")

@app.route('/create_account')
def create_account():
    return render_template('create_account.html')

@app.route('/register', methods=['POST'])
def register():
    global username, UPLOAD_FOLDER, AI_UPLOAD_FOLDER, PAST_UPLOAD_FOLDER, user_csv_file
    name = request.form.get('name')
    username_value = request.form.get('username')
    email = request.form.get('email')
    phone = request.form.get('phone')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    
    if password != confirm_password:
        return render_template('create_account.html', error="Passwords do not match.")

    new_user = {
        "username": username_value,
        "name": name,
        "email": email,
        "phone_number": phone,
        "password": password,
        "upload_dir": f'app/static/customers/{username_value}/uploads',
        "ai_upload_dir": f'app/static/customers/{username_value}/AI_uploads',
        "past_upload_dir": f'app/static/customers/{username_value}/past_uploads',
        "subscription": "No Plan",
        "remaining_photos": 0,
    }

    UPLOAD_FOLDER = new_user['upload_dir']
    AI_UPLOAD_FOLDER = new_user['ai_upload_dir']
    PAST_UPLOAD_FOLDER = new_user['past_upload_dir']
    username = username_value

    user_csv_file = pd.concat([user_csv_file, pd.DataFrame([new_user])], ignore_index=True)
    user_csv_file.to_csv("app/customers_info.csv", index=False)

    os.makedirs(UPLOAD_FOLDER)
    os.makedirs(AI_UPLOAD_FOLDER)
    os.makedirs(PAST_UPLOAD_FOLDER)

    # Store user data (replace with actual database logic)
    session['user'] = username_value
    return redirect(url_for('dashboard'))

@app.route('/account_settings')
def account_settings():
    global user_csv_file, username
    user_info = user_csv_file[user_csv_file['username'] == username].iloc[0]
    print(user_info)
    user_name = user_info['name']
    user_plan = user_info['subscription']
    if user_plan != "Subscription":
        user_plan = ''
    user_email = user_info['email']
    user_phone = user_info['phone_number']

    return render_template('account_settings.html', name=user_name, email=user_email, phone=user_phone, plan=user_plan)

@app.route('/delete-account', methods=['POST'])
def delete_account():
    global user_csv_file, username
    shutil.rmtree(UPLOAD_FOLDER.replace("/uploads", ""))
    user_csv_file = user_csv_file[user_csv_file['username'] != username]
    user_csv_file.to_csv("app/customers_info.csv", index=False)
    return jsonify({"message": "Account deleted successfully"}), 200

@app.route("/cancel_subscription", methods=['POST'])
def cancel_subscription():
    global user_csv_file, username
    user_csv_file.loc[user_csv_file['username'] == username, 'subscription'] = "No Plan"
    user_csv_file.to_csv("app/customers_info.csv", index=False)
    return jsonify({"message": "Subscription canceled successfully"}), 200

@app.route('/dashboard')
def dashboard():
    global user_csv_file, username
    # Fetch user details from the dataframe
    user_info = user_csv_file[user_csv_file['username'] == username].iloc[0]
    user_name = user_info['name']
    subscription_plan = user_info['subscription']
    remaining_images = user_info['remaining_photos']
    
    # Get the number of processed images
    if os.path.exists(PAST_UPLOAD_FOLDER):
        processed_images = len([f for f in os.listdir(PAST_UPLOAD_FOLDER) if os.path.isfile(os.path.join(PAST_UPLOAD_FOLDER, f))])
    else:
        processed_images = 0

    # Get image file paths
    images = [f"{PAST_UPLOAD_FOLDER}/{img}".replace("app/", "") for img in os.listdir(PAST_UPLOAD_FOLDER)] if processed_images > 0 else []

    return render_template('dashboard.html', 
                           user_name=user_name, 
                           subscription_plan=subscription_plan, 
                           remaining_images=remaining_images, 
                           processed_images=processed_images, 
                           images=images)

@app.route('/payment_options')
def payment_options():
    global user_csv_file, username
    user_current_subscription = user_csv_file.loc[user_csv_file['username'] == username, 'subscription'].iloc[0]
    print(user_current_subscription)
    return render_template('payment_options.html', current_subscription=user_current_subscription)

@app.route('/previous_images')
def previous_images():
    global PAST_UPLOAD_FOLDER
    image_files = glob.glob(os.path.join(PAST_UPLOAD_FOLDER, '*'))
    image_urls = [f"{PAST_UPLOAD_FOLDER.replace('app/', '')}/{os.path.basename(img)}" for img in image_files]
    print(image_urls)
    return render_template('previous_images.html', image_files=image_urls)

@app.route('/download_past_uploads')
def download_past_uploads():
    global PAST_UPLOAD_FOLDER
    ZIP_FILE_PATH = os.path.join(PAST_UPLOAD_FOLDER.replace("app/", "").replace("past_uploads", ""), "past_uploads.zip")
    try:
        # Compress the folder into a zip file
        if not os.path.exists(ZIP_FILE_PATH):
            shutil.make_archive(PAST_UPLOAD_FOLDER, 'zip', PAST_UPLOAD_FOLDER)
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
    global subscription_to_buy, num_of_images_to_buy, cost_for_purchase
    
    data = request.json
    subscription_to_buy = data.get('plan')
    num_of_images_to_buy = data.get('images', 0)
    if subscription_to_buy == "subscription":
        cost_for_purchase = 15.00
    elif subscription_to_buy == "buy_more_images":
        cost_for_purchase = num_of_images_to_buy * 0.8
    else:
        cost_for_purchase = num_of_images_to_buy * 1.5
    
    return jsonify({"status": "success"})

@app.route('/index')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    global user_csv_file, username
    user_info = user_csv_file[user_csv_file['username'] == username].iloc[0]
    remaining_images = user_info['remaining_photos']
    return render_template('index.html', remaining_images=remaining_images)

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
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(file_path)

            # Store the relative path (relative to the 'static' folder)
            session['image_paths'].append(f"{UPLOAD_FOLDER}/{filename}")
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
    if subscription_to_buy == "buy_more_images":
        plan = "Buy More Images"
    elif subscription_to_buy == "pay_as_you_go":
        plan = "Pay As You Go"
    else:
        plan = "Subscription"
    return render_template("checkout.html", num_of_images=num_of_images_to_buy, plan=plan, cost=cost_for_purchase)

@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    try:
        # Assume values are coming from the backend
        
        if subscription_to_buy == "subscription":
            # Create a Stripe Product
            product = stripe.Product.create(name=f"Subscription Plan - {num_of_images_to_buy} Images")
            
            # Create a Price Object for Subscription
            price = stripe.Price.create(
                unit_amount=int(cost_for_purchase * 100),  # Convert dollars to cents
                currency="usd",
                recurring={"interval": "month"},
                product=product.id,
            )
        else:
            # Create a Stripe Product
            product = stripe.Product.create(name=f"One-Time Purchase - {num_of_images_to_buy} Images")
            
            # Create a Price Object for One-Time Payment
            price = stripe.Price.create(
                unit_amount=int(cost_for_purchase * 100),  # Convert dollars to cents
                currency="usd",
                product=product.id,
            )
        print("Price Object Created:", price.id)  # Debugging
        # Create Stripe Checkout Session
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price": price.id,
                    "quantity": 1,
                }
            ],
            mode="subscription" if subscription_to_buy == "subscription" else "payment",
            success_url=url_for('success', _external=True),
            cancel_url=url_for('cancel', _external=True),
        )
        
        return jsonify({"id": session.id})
    except Exception as e:
        return jsonify(error=str(e)), 400

@app.route('/success')
def success():
    global user_csv_file, username, num_of_images_to_buy, subscription_to_buy
    user_csv_file.loc[user_csv_file['username'] == username, 'remaining_photos'] += num_of_images_to_buy
    if subscription_to_buy == "subscription":
        user_csv_file.loc[user_csv_file['username'] == username, 'subscription'] = "Subscription"
    if subscription_to_buy == "pay_as_you_go":
        user_csv_file.loc[user_csv_file['username'] == username, 'subscription'] = "Pay As You Go"
    user_csv_file.to_csv("app/customers_info.csv", index=False)
    return redirect(url_for('dashboard',  message="success"))

@app.route('/cancel')
def cancel():
    return redirect(url_for('dashboard',  message="failed"))

@app.route('/confirm_image', methods=['GET', 'POST'])
def confirm_image():
    global user_csv_file, username
    image_files = glob.glob(os.path.join(UPLOAD_FOLDER, '*'))  # Find all PNG images
    total_images = len(image_files)
    image_urls = [f"{UPLOAD_FOLDER}/{os.path.basename(img)}".replace("app/", "") for img in image_files]

    return render_template('confirm_image.html', total_images=total_images, image_urls=image_urls)

task_status = {"status": "pending", "result": None}
image_urls_AI = []

# Global variable to track task status
@app.route('/download', methods=['GET'])
def download():
    image_files = glob.glob(os.path.join(UPLOAD_FOLDER, '*'))
    user_csv_file.loc[user_csv_file['username'] == username, 'remaining_photos'] -= len(image_files)
    user_csv_file.to_csv("app/customers_info.csv", index=False)
    image_files = glob.glob(os.path.join(UPLOAD_FOLDER, '*'))  # Find all PNG images
    total_images = len(image_files)
    estimated_time = round(total_images * 0.5, 2)  # Estimate processing time

    def long_task():
        global task_status
        global image_urls_AI
        try:
            task_status["status"] = "processing"
            # new_image_urls = generate_new_AI_images(session_data, config['url'], config['headers'])
            # download_images(new_image_urls, AI_UPLOAD_FOLDER)
            image_file_AI = glob.glob(os.path.join(AI_UPLOAD_FOLDER, "*"))  # Find all PNG images
            image_urls_AI = [f"{AI_UPLOAD_FOLDER}/{os.path.basename(img)}".replace("app/", "") for img in image_file_AI]
            for filename in os.listdir(UPLOAD_FOLDER):
                source_path = os.path.join(UPLOAD_FOLDER, filename)
                destination_path = os.path.join(PAST_UPLOAD_FOLDER, filename)
                if os.path.isfile(source_path):
                    shutil.copy2(source_path, destination_path)
            print("All files copied to past upload directory!")
            task_status["status"] = "completed"
        except Exception as e:
            task_status["status"] = "error"
            task_status["result"] = str(e)

    # Start the task in a new thread
    session_data = dict(session.items())
    task_thread = threading.Thread(target=long_task)
    task_thread.start()

    return render_template('download.html', total_time=estimated_time, image_urls=image_urls_AI)

@app.route('/check_status', methods=['GET'])
def check_status():
    return jsonify({"status": task_status["status"], "images": image_urls_AI})

@app.route('/download-folder', methods=['GET'])
def download_folder():
    FOLDER_PATH = AI_UPLOAD_FOLDER
    ZIP_FILE_PATH = os.path.join(AI_UPLOAD_FOLDER.replace("app/", "").replace("AI_uploads", ""), "AI_uploads.zip")
    print(ZIP_FILE_PATH)
    try:
        # Compress the folder into a zip file
        if not os.path.exists(ZIP_FILE_PATH):
            shutil.make_archive(FOLDER_PATH, 'zip', FOLDER_PATH)
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

if __name__ == '__main__':
    app.run(debug=True)