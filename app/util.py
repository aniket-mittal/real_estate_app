"""
Utility functions for real-estate application
"""

#%% Import 3rd-party software
import requests
import cloudinary
import requests
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os
from PIL import Image
import math
import numpy as np

#%% Utility Functions
def run_api(url, headers, input_image, room_type, design_style="scandinavian", num_images=1, scale_factor=1, color_scheme="COLOR_SCHEME_0", specialty_decor="SPECIALITY_DECOR_0"):
    """
    Runs Decor8 API to generate enhanced images

    :param url: String referring to Decor8 API URL
    :param headers: Dictionary referring to Decor 8 API Headers (Content-Type & Authorization API Key)
    :param input_image: String referring to URL of input image
    :param room_type: String referring to room type of image; Choose from ["livingroom", "kitchen", "diningroom", "bedroom", "bathroom", "kidsroom", "familyroom", "readingnook", "sunroom", "walkincloset", "mudroom", "toyroom", "office", "foyer", "powderroom", "laundryroom", "gym", "basement", "garage", "balcony", "cafe", "homebar", "study_room", "front_porch", "back_porch", "back_patio", "openplan", "boardroom", "meetingroom", "openworkspace", "privateoffice"]
    :param design_style: String referring to designated decoration style; DEFAULT = "scandinavian", Choose from ["minimalist", "scandinavian", "industrial", "boho", "traditional", "artdeco", "midcenturymodern", "coastal", "tropical", "eclectic", "contemporary", "frenchcountry", "rustic", "shabbychic", "vintage", "country", "modern", "asian_zen", "hollywoodregency", "bauhaus", "mediterranean", "farmhouse", "victorian", "gothic", "moroccan", "southwestern", "transitional", "maximalist", "arabic", "japandi", "retrofuturism", "artnouveau"]
    :param num_images: Integer referring to number of images to process; DEFAULT = 1
    :param scale_factor: Integer referring to factor to upscale image; Scale up to factor 8 corresponding to 6144 pixels; DEFAULT = 1
    :param color_scheme: String referring to designated color_scheme; choose from 0-20, DEFAULT = 'COLOR_SCHEME_0'
    :param specialty_decor: String referring to custom specialty decoration settings; choose from 0-7, DEFAULT = 'SPECIALITY_DECOR_0'
    :return: List containing AI enhanced image URLs with chosen parameters
    """
    input = {
        "input_image_url": input_image,
        "room_type": room_type,
        "design_style": design_style,
        "num_images": num_images,
        "scale_factor": scale_factor,
        "color_scheme": color_scheme,
        "speciality_decor": specialty_decor,
        "keep_original_floor": True
    }
    response = requests.post(url, headers=headers, json=input)
    if response.status_code == 200:
        print("Room designs generated successfully!")
        images = response.json()
        print(images)
        response = images.get("info", {}).get("images", [])
        return response[0]['url']
    else:
        print(f"Error: {response.status_code} - {response.text}")


def upload_image(image):
    """
    Uploads a singular image to cloudinary to generate an image URL

    :param image: Byte type object containing image file (not filepath) 
    :return: String containing image URL
    """
    try:
        response = cloudinary.uploader.upload(image)
        image_url = response.get("secure_url")
        print(f"Image URL generated: {image_url}")
        return image_url
    except Exception as e:
        print(f"Error uploading image: {e}")
        return None
    
def generate_new_AI_images(session, url, headers):
    dictionary_of_items = session  # Convert dict_items to a regular dictionary
    list_of_urls = []
    
    for i in range(len(dictionary_of_items['image_paths'])):
        image_url = upload_image("app/static/" + dictionary_of_items['image_paths'][i])  # Use indexed access for 'image_paths'
        if not dictionary_of_items['selected_specialty_decor']:
            dictionary_of_items['selected_specialty_decor'] = "SPECIALITY_DECOR_0"
        list_of_urls.append(run_api(
            url, 
            headers, 
            image_url, 
            dictionary_of_items['room_types'][i], 
            dictionary_of_items['selected_room_style'].rsplit('.', 1)[0], 
            1, 
            dictionary_of_items['upscale_factors'][i], 
            dictionary_of_items['color_schemes'][i], 
            dictionary_of_items['selected_specialty_decor']
        ))
    
    return list_of_urls

def download_images(image_urls, output_folder):
    for i, url in enumerate(image_urls, start=1):
        try:
            response = requests.get(url)
            response.raise_for_status()  # Check if the request was successful
            
            # Save the image with a sequential filename
            file_path = f"{output_folder}image_{i}.jpg"
            with open(file_path, "wb") as f:
                f.write(response.content)
            
            print(f"Image {i} downloaded and saved as {file_path}")
        except requests.exceptions.RequestException as e:
            print(f"Failed to download image {i} from {url}. Error: {e}")


def save_image_grid(image_folder, save_folder, output_filename="image_grid.png"):
    """
    Creates a grid of images from a folder and saves it as an image in the same folder.
    
    Parameters:
        image_folder (str): Path to the folder containing images.
        output_filename (str): Name of the output file (default: 'image_grid.png').
    """
    # Load images from folder
    image_files = [os.path.join(image_folder, file) for file in os.listdir(image_folder) if file.lower().endswith(('png', 'jpg', 'jpeg', 'bmp', 'gif'))]

    # If no images are found, raise an error
    if not image_files:
        raise ValueError("No image files found in the specified folder.")
    
    # Determine grid size
    image_count = len(image_files)
    cols = math.ceil(math.sqrt(image_count))  # Use square root to approximate equal grid
    rows = math.ceil(image_count / cols)

    # Create subplots
    fig, axes = plt.subplots(rows, cols, figsize=(25, 20))

    # If only one subplot, make axes a list for consistency
    if image_count == 1:
        axes = [axes]

    # Flatten the axes array for easier iteration
    elif isinstance(axes, np.ndarray):
        axes = axes.flatten()

    # Plot each image
    for ax, img_path in zip(axes, image_files):
        img = Image.open(img_path)
        ax.imshow(img)
        ax.axis('off')  # Hide axes for cleaner display

    # Hide unused subplots
    for ax in axes[len(image_files):]:
        ax.axis('off')

    plt.tight_layout()

    # Save the figure to the specified folder
    output_path = os.path.join(save_folder, output_filename)
    fig.savefig(output_path, dpi=300, transparent=True)
    plt.close(fig)  # Close the figure to release memory

    print(f"Image grid saved to: {output_path}")
