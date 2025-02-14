#%% Import 3rd-party software
import requests
import cloudinary
import cloudinary.uploader
import yaml

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


with open("app/config.yaml", "r") as file:
    config = yaml.safe_load(file)

cloudinary.config(
    cloud_name=config["cloud_name"],
    api_key=config["api_key"],
    api_secret=config["api_secret"]
)

image_link = upload_image('/Users/aniketmittal/Desktop/real_estate_app/app/static/generic.png')

styles = ["SPECIALITY_DECOR_1", "SPECIALITY_DECOR_2", "SPECIALITY_DECOR_3", "SPECIALITY_DECOR_4", "SPECIALITY_DECOR_5", "SPECIALITY_DECOR_6", "SPECIALITY_DECOR_7"]

for style in styles:
    image = run_api(config['url'], config['headers'], image_link, 'livingroom', 'modern', specialty_decor=style)
    print(image)

# %%
