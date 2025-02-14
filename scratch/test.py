from util.py import run_api
import yaml

with open("app/config.yaml", "r") as file:
    config = yaml.safe_load(file)

image_link = 'https://drive.google.com/file/d/1ggwy3aRNiUH3NLaqtCvvExZ2ELry8W-v/view?usp=sharing'

image = run_api(config['url'], config['headers'], image_link, 'livingroom', 'scandinavian')

print(image)