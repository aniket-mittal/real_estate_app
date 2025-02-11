import os
from PIL import Image
import matplotlib.pyplot as plt
from matplotlib import font_manager

def plot_images_side_by_side(folder_before, folder_after, output_path=None):
    # Load images from folders
    before_images = sorted([os.path.join(folder_before, f) for f in os.listdir(folder_before) if f.endswith(('png', 'jpg', 'jpeg'))])
    after_images = sorted([os.path.join(folder_after, f) for f in os.listdir(folder_after) if f.endswith(('png', 'jpg', 'jpeg'))])

    # Check if the number of images match
    if len(before_images) != len(after_images):
        raise ValueError("Number of images in both folders must be the same.")

    # Load Poppins font
    poppins_path = font_manager.findfont("Poppins")
    poppins_font = font_manager.FontProperties(fname=poppins_path) if poppins_path else None

    # Plot the images
    n_images = len(before_images)
    fig, axes = plt.subplots(nrows=n_images, ncols=2, figsize=(10, 5 * n_images))
    for idx, (before_path, after_path) in enumerate(zip(before_images, after_images)):
        # Load and plot "Before" image
        before_img = Image.open(before_path)
        axes[idx, 0].imshow(before_img)
        axes[idx, 0].set_title("Before", fontproperties=poppins_font, fontsize=16) if poppins_font else axes[idx, 0].set_title("Before", fontsize=16)
        axes[idx, 0].axis("off")

        # Load and plot "After" image
        after_img = Image.open(after_path)
        axes[idx, 1].imshow(after_img)
        axes[idx, 1].set_title("After", fontproperties=poppins_font, fontsize=16) if poppins_font else axes[idx, 1].set_title("After", fontsize=16)
        axes[idx, 1].axis("off")

    plt.tight_layout()

    # Save the plot or display it
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
    else:
        plt.show()


plot_images_side_by_side("app/static/uploads", "app/static/AI_uploads", "app/static/AI_uploads")