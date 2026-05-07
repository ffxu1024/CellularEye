"""
Description: Verify the real UAV dataset to ensure the correctness of the data and the alignment between the yolo labels and the images.
This script mark the label in the relavant images and check if the label is correct. 
"""

import argparse
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.animation as animation
def main():
    parser = argparse.ArgumentParser(description="Verify the real UAV dataset")
    parser.add_argument("--input_dir", type=str, default="./datasets/real_uav_no_smooth_peaksnap_bs23_beam14_w10h10", help="Path to the directory containing the dataset")
    parser.add_argument("--output_dir", type=str, default="./results/label_verification", help="Path to the directory to save the verification results")
    parser.add_argument("--collection_name", type=str, default="2025_12_06_12_00", help="Name of the collection to visualize")
    args = parser.parse_args()
    output_path = f"{args.output_dir}/{args.input_dir.split('/')[-1]}"
    input_path = Path(args.input_dir)
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)
    trajectory_files = list(input_path.rglob(f"{args.collection_name}_*.png"))
    trajectory_files = sorted(trajectory_files)
    label_files = list(input_path.rglob(f"{args.collection_name}_*.txt"))
    label_files = sorted(label_files)
    print(f"Found {len(trajectory_files)} trajectory files in {input_path}")
    # ramdom select 8 images and their corresponding labels to visualize


    # Plot the first 8 images with their labels
    fig, axs = plt.subplots(2, 4, figsize=(20, 10))
    for i in range(8):
        image_file = trajectory_files[i]
        label_file = label_files[i]
        print(f"Processing {image_file} and {label_file}...")
        # Load the image
        img = plt.imread(image_file)
        axs[i // 4, i % 4].imshow(img)
        # Load the labels
        with open(label_file, "r") as f:
            lines = f.readlines()
            for line in lines:
                class_id, x_center, y_center, width, height = map(float, line.strip().split())
                # Convert from relative coordinates to absolute coordinates
                img_height, img_width = img.shape
                x_center *= img_width
                y_center *= img_height
                width *= img_width
                height *= img_height
                # Calculate the top-left corner of the bounding box
                x_min = int(x_center - width / 2)
                y_min = int(y_center - height / 2)
                # Draw the bounding box on the image
                rect = plt.Rectangle((x_min, y_min), int(width), int(height), edgecolor='red', facecolor='none', linewidth=1)
                axs[i // 4, i % 4].add_patch(rect)
        axs[i // 4, i % 4].set_title("RV Map with Label")
        axs[i // 4, i % 4].axis('off')
    plt.suptitle("Real UAV Dataset Verification", fontsize=16)
    plt.tight_layout()
    plt.savefig(output_path / f"{args.collection_name}_grid.png")
    plt.show()

    # Plot and save GIF for specific trajectory and label from same collection, for example, 2025_12_04_12_00_2025_12_04_12_02_00_080.png is from collection 2025_12_04_12_00 
    # Find all trajectory in train dataset
    

    # 
    # 
    fig, ax = plt.subplots(figsize=(10, 10))
    def animate(i):
        image_file = trajectory_files[i]
        label_file = label_files[i]
        print(f"Processing {image_file} and {label_file}...")
        # Load the image
        img = plt.imread(image_file)
        ax.imshow(img)
        # Load the labels
        with open(label_file, "r") as f:
            lines = f.readlines()
            for line in lines:
                class_id, x_center, y_center, width, height = map(float, line.strip().split())
                # Convert from relative coordinates to absolute coordinates
                img_height, img_width = img.shape
                x_center *= img_width
                y_center *= img_height
                width *= img_width
                height *= img_height
                # Calculate the top-left corner of the bounding box
                x_min = int(x_center - width / 2)
                y_min = int(y_center - height / 2)
                # Draw the bounding box on the image
                rect = plt.Rectangle((x_min, y_min), int(width), int(height), edgecolor='red', facecolor='none', linewidth=1)
                ax.add_patch(rect)
        ax.set_title(f"image: {image_file.name}")
        ax.axis('off')
    ani = animation.FuncAnimation(fig, animate, frames=len(trajectory_files), repeat=False)
    ani.save(output_path / f"{args.collection_name}_traj.gif", writer='pillow', fps=10)
    # save all frames as png
    plt.savefig(output_path / f"{args.collection_name}_traj.png")

    # Plot the trajectory without labels and save as GIF and png
    fig, ax = plt.subplots(figsize=(10, 10))
    def animate_no_label(i):
        image_file = trajectory_files[i]
        print(f"Processing {image_file}...")
        # Load the image
        img = plt.imread(image_file)
        ax.imshow(img)
        ax.set_title(f"image: {image_file.name}")
        ax.axis('off')
    ani_no_label = animation.FuncAnimation(fig, animate_no_label, frames=len(trajectory_files), repeat=False)
    ani_no_label.save(output_path / f"{args.collection_name}_traj_no_label.gif", writer='pillow', fps=10)
    # save all frames as png
    plt.savefig(output_path / f"{args.collection_name}_traj_no_label.png")

    # ==========================
    # Added 1: RV map GIF with boxes but no history frames
    # ==========================
    fig_no_hist, ax_no_hist = plt.subplots(figsize=(10, 10))
    def animate_no_hist(i):
        ax_no_hist.clear()
        image_file = trajectory_files[i]
        label_file = label_files[i]
        print(f"[No History] Processing {image_file.name}...")
        img = plt.imread(image_file)
        ax_no_hist.imshow(img, cmap='gray')
        
        with open(label_file, "r") as f:
            lines = f.readlines()
            for line in lines:
                parts = line.strip().split()
                if len(parts) < 5: continue
                _, x_center, y_center, width, height = map(float, parts[:5])
                img_height, img_width = img.shape[:2] # Use [:2] to be compatible with different reading libraries
                x_center *= img_width
                y_center *= img_height
                width *= img_width
                height *= img_height
                x_min = int(x_center - width / 2)
                y_min = int(y_center - height / 2)
                rect = plt.Rectangle((x_min, y_min), int(width), int(height), edgecolor='red', facecolor='none', linewidth=1)
                ax_no_hist.add_patch(rect)
        ax_no_hist.set_title(f"image: {image_file.name} (No History)")
        ax_no_hist.axis('off')

    ani_no_hist = animation.FuncAnimation(fig_no_hist, animate_no_hist, frames=len(trajectory_files), repeat=False)
    ani_no_hist.save(output_path / f"{args.collection_name}_traj_no_hist.gif", writer='pillow', fps=10)
    fig_no_hist.savefig(output_path / f"{args.collection_name}_traj_no_hist.png")
    plt.close(fig_no_hist)

    # ==========================
    # Added 2: Target local patch animation and all single-frame PNG saving
    # ==========================
    patch_size = 128
    patch_output_dir = output_path / f"{args.collection_name}_patch_frames"
    patch_output_dir.mkdir(parents=True, exist_ok=True)

    fig_patch, ax_patch = plt.subplots(figsize=(6, 6))
    def animate_patch(i):
        ax_patch.clear()
        image_file = trajectory_files[i]
        label_file = label_files[i]
        img = plt.imread(image_file)
        ax_patch.imshow(img, cmap='gray')
        
        img_height, img_width = img.shape[:2]
        c_x, c_y = img_width / 2, img_height / 2
        
        with open(label_file, "r") as f:
            lines = f.readlines()
            # Use the first target in the txt file as Patch center
            if len(lines) > 0:
                parts = lines[0].strip().split()
                if len(parts) >= 5:
                    _, x_center, y_center, width, height = map(float, parts[:5])
                    c_x = x_center * img_width
                    c_y = y_center * img_height

            for line in lines:
                parts = line.strip().split()
                if len(parts) < 5: continue
                _, x_center, y_center, width, height = map(float, parts[:5])
                x_center *= img_width
                y_center *= img_height
                width *= img_width
                height *= img_height
                x_min = int(x_center - width / 2)
                y_min = int(y_center - height / 2)
                rect = plt.Rectangle((x_min, y_min), int(width), int(height), edgecolor='red', facecolor='none', linewidth=1.5)
                ax_patch.add_patch(rect)
                
        # Zoom in by scaling axes, keeping original index values
        ax_patch.set_xlim(c_x - patch_size/2, c_x + patch_size/2)
        ax_patch.set_ylim(c_y + patch_size/2, c_y - patch_size/2) # imshow y-axis is downwards by default
        
        ax_patch.set_title(f"Patch view of {image_file.name}")
        ax_patch.set_xlabel("Velocity Index (Doppler)")
        ax_patch.set_ylabel("Range Index")
        
        fig_patch.tight_layout()
        # Save the drawn single-frame images directly to directory
        fig_patch.savefig(patch_output_dir / f"patch_{image_file.name}")

    print(f"Generating Patch GIF and saving PNGs to {patch_output_dir}...")
    ani_patch = animation.FuncAnimation(fig_patch, animate_patch, frames=len(trajectory_files), repeat=False)
    ani_patch.save(output_path / f"{args.collection_name}_patch_traj.gif", writer='pillow', fps=10)
    fig_patch.savefig(output_path / f"{args.collection_name}_patch_traj.png")
    plt.close(fig_patch)

if __name__ == "__main__":
    main()
    np.random.seed(42)

