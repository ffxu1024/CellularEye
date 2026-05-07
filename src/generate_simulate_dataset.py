"""
Generate simulated dataset first because it has no unaligned issue.
"""

import argparse
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd
from PIL import Image
from tqdm import tqdm
import multiprocessing as mp

from core import (
    Config, DistributedTarget, PointTarget, LinearTrajectory, 
    generate_radar_channel_matrix, channel_to_rv_map, add_window_to_channel_matrix, nomalize_log_power_map,combine_target_to_background, generate_noise_background_channel_matrix, generate_random_linear_trajectory,
    plot_2d_range_doppler
)

def calculate_snr(rv_map: np.ndarray, target_range_idx: int, target_doppler_idx: int, window_size: int = 20) -> float:
    """
    Calculate SNR for a target in the RV map.
    """
    # Define the target cell and noise window
    target_cell_power = rv_map[target_range_idx, target_doppler_idx]
    
    # Define noise window around the target cell (excluding the target cell itself)
    range_start = max(0, target_range_idx - window_size)
    range_end = min(rv_map.shape[0], target_range_idx + window_size + 1)
    doppler_start = max(0, target_doppler_idx - window_size)
    doppler_end = min(rv_map.shape[1], target_doppler_idx + window_size + 1)

    noise_window = rv_map[range_start:range_end, doppler_start:doppler_end]
    noise_window = np.delete(noise_window.flatten(), (window_size * 2 + 1) * window_size + window_size)  # Remove target cell

    # Calculate noise power as the median of the noise window
    noise_power = np.median(noise_window)

    # Calculate SNR in dB
    snr_db = 10 * np.log10(target_cell_power / noise_power) if noise_power > 0 else float('inf')
    
    return snr_db, noise_power, target_cell_power



def generate_yolo_label(cfg: Config, distance: float, velocity: float) -> list:
    """
    Generate YOLO format label from physical coordinates.
    
    YOLO format: [class_id, x_center, y_center, width, height] (all normalized 0-1)
    
    In RD map context:
    - x corresponds to Doppler/velocity dimension
    - y corresponds to Range dimension
    
    Args:
        cfg: Configuration object
        distance: Target distance in meters
        velocity: Target radial velocity in m/s
        
    Returns:
        list: [class_id, x_center, y_center, width, height]
    """
    # Calculate range bin index
    range_idx = distance / cfg.range_bin
    if range_idx >= cfg.number_subcarriers or range_idx < 0:
        range_idx = range_idx % cfg.number_subcarriers  # Wrap around for out-of-bounds
    # Calculate Doppler bin index (velocity_seq goes from -V_max to +V_max)
    doppler_idx = (velocity / cfg.velocity_bin) + (cfg.number_symbols_per_radar_frame // 2)
    if doppler_idx < 0 or doppler_idx >= cfg.number_symbols_per_radar_frame:
        doppler_idx = doppler_idx % cfg.number_symbols_per_radar_frame  # Wrap around for out-of-bounds
    # Normalize coordinates (0-1)
    # Note: In image coordinates, x is horizontal (Doppler), y is vertical (Range)
    x_center = doppler_idx / cfg.number_symbols_per_radar_frame
    y_center = range_idx / cfg.number_subcarriers
    
    # Bounding box size (normalized)
    width = BBOX_WIDTH_BINS / cfg.number_symbols_per_radar_frame
    height = BBOX_HEIGHT_BINS / cfg.number_subcarriers
    
    # Match vertically flipped images (np.flipud in save_rd_image)
    y_center = 1.0 - y_center

    # Clamp values to valid range
    x_center = np.clip(x_center, 0.0, 1.0)
    y_center = np.clip(y_center, 0.0, 1.0)
    if y_center==0.0 or y_center==1.0:
        print(f"Warning: y_center is at the edge (0 or 1). Check distance: {distance}, range_idx: {range_idx}, y_center: {y_center}")   
    # Class 0 = UAV
    return [0, x_center, y_center, width, height]

def save_rd_image(rv_map: np.ndarray, output_path: Path, cfg: Config = None):
    """
    Save RD map as image file.
    
    Args:
        rv_map: Power RV map
        output_path: Path to save image
        cfg: Optional config for plotting with axes
    """
    # Normalize to dB scale
    log_map = nomalize_log_power_map(rv_map)
    
    # Normalize to 0-255 for image
    # Map from [-140, 0] dB to [0, 255]
    img_array = ((log_map + 140) / 140 * 255).clip(0, 255).astype(np.uint8)
    
    # Flip vertically so origin is at bottom (like imshow with origin='lower')
    img_array = np.flipud(img_array)
    
    # Save as grayscale image
    img = Image.fromarray(img_array, mode='L')
    img.save(output_path)


def save_yolo_label(label: list, output_path: Path):
    """
    Save YOLO format label to text file.
    
    Args:
        label: [class_id, x_center, y_center, width, height]
        output_path: Path to save label file
    """
    with open(output_path, 'w') as f:
        f.write(f"{int(label[0])} {label[1]:.6f} {label[2]:.6f} {label[3]:.6f} {label[4]:.6f}\n")

def _process_one_trajectory(args_tuple):
    traj_idx, trajectory, args, cfg, output_dir = args_tuple
    
    sim_targets = DistributedTarget(trajectory=trajectory, avg_rcs=1, swerling_model='Swerling1')
    snr_db = np.random.normal(loc=args.snr_mean, scale=args.snr_std)

    local_stat = {"samples": 0, "train_samples": 0, "val_samples": 0}

    for frame_idx in range(args.frames_per_trajectory):
        target_channel_matrix = generate_radar_channel_matrix(cfg, [sim_targets], signal_amplitude=1.0)
        windowed_target_channel_matrix = add_window_to_channel_matrix(target_channel_matrix)

        noise_channel_matrix = generate_noise_background_channel_matrix(cfg, noise_variance=1.0)

        combined_channel_matrix = combine_target_to_background(
            cfg,
            target_channel=windowed_target_channel_matrix,
            background_channel=noise_channel_matrix,
            target_snr_db=snr_db
        )
        rv_map = channel_to_rv_map(combined_channel_matrix)

        time_elapsed = frame_idx * cfg.frame_period
        if frame_idx < int(0.9 * args.frames_per_trajectory):
            dataset_type = "train"
            local_stat["train_samples"] += 1
        else:
            dataset_type = "val"
            local_stat["val_samples"] += 1

        distance, velocity = trajectory.get_state(time_elapsed)
        yolo_label = generate_yolo_label(cfg, distance, velocity)
        if distance >= cfg.unambiguous_range or distance < 0:
            print(f"Warning: range {distance} is out of bounds for distance range {cfg.unambiguous_range}. Check traj {traj_idx}, frame {frame_idx}.")
        # Calculate Doppler bin index (velocity_seq goes from -V_max to +V_max)
        if velocity < -cfg.unambiguous_velocity or velocity >= cfg.unambiguous_velocity:
            print(f"Warning: velocity {velocity} is out of bounds for velocity {cfg.unambiguous_velocity}. Check traj {traj_idx}, frame {frame_idx}.")
        rv_output_path = output_dir / "images" / dataset_type / f"traj_{traj_idx}_frame_{frame_idx}.png"
        save_rd_image(rv_map, rv_output_path, cfg)

        label_output_path = output_dir / "labels" / dataset_type / f"traj_{traj_idx}_frame_{frame_idx}.txt"
        save_yolo_label(yolo_label, label_output_path)

        local_stat["samples"] += 1
        sim_targets.update(time_elapsed)

    return local_stat

def generate_simulated_data(args, cfg: Config, output_dir: Path):
    """
    Generate simulated dataset based on the provided configuration and save it to the specified output directory.
    """
    print(f"Generating simulated dataset with config: {cfg}")
    
    print("\n" + "=" * 60)
    print("Starting dataset generation...")
    print("=" * 60 )
    print("\n" + "-" * 50)
    print("Step 1: Read configuration and initialize parameters...")
    print("-" * 50)
    # Here you would read the configuration file and initialize any necessary parameters
    # real_snr_path = args.real_snr_path
    # real_snr_values = pd.read_parquet(real_snr_path)
    # mean_snr = real_snr_values['snr_db'].mean()
    # std_snr = real_snr_values['snr_db'].std()

    # print(f"Real SNR path: {real_snr_path}")
    # print(f"Real SNR values loaded: {real_snr_values.head()}")
    # print(f"Mean SNR: {mean_snr} dB, Std SNR: {std_snr} dB")
   
    print("\n" + "-" * 50)
    print("Step 2: Generate random trajectories...")
    print("-" * 50)

    #  Generate trajectories 
    num_trajectories = args.num_trajectories
    trajectories = generate_random_linear_trajectory(num_trajectories=num_trajectories)
    print(f"Generated {num_trajectories} random trajectories.")

    print("\n" + "-" * 50)
    print("Step 3: Synthesize radar data for each trajectory...")
    print("-" * 50)

    # 

    # 
    # sim_targets = DistributedTarget(trajectory=trajectories[1], avg_rcs=1, swerling_model='Swerling1') 

    # 
    # target_channel_matrix = generate_radar_channel_matrix(cfg, [sim_targets], signal_amplitude=1.0)
    # windowed_target_channel_matrix = add_window_to_channel_matrix(target_channel_matrix)

    # 
    # noise_channel_matrix = generate_noise_background_channel_matrix(cfg, noise_variance=1.0)

    # 
    # combined_channel_matrix = combine_target_to_background(cfg, target_channel=windowed_target_channel_matrix, background_channel=noise_channel_matrix, target_snr_db=45)
    
    #
    # rv_map = channel_to_rv_map(combined_channel_matrix)
    # nomalize_map = nomalize_log_power_map(rv_map)
    # plot_2d_range_doppler(cfg, nomalize_map, plot_dir=args.plot_dir, filename="Example_simulated_rv_map.png")
    
    total_stat = {
        "samples": 0,
        "train_samples": 0,
        "val_samples": 0,
        "trajectories": num_trajectories,
        "frames_per_trajectory": args.frames_per_trajectory,
    }
    
    # Paralle processing version
    tasks = [(traj_idx, trajectory, args, cfg, output_dir) for traj_idx, trajectory in enumerate(trajectories)]

    with mp.Pool(processes=mp.cpu_count()) as pool:
        for local_stat in tqdm(pool.imap_unordered(_process_one_trajectory, tasks), total=len(tasks), desc="Processing Trajectories"):
            total_stat["samples"] += local_stat["samples"]
            total_stat["train_samples"] += local_stat["train_samples"]
            total_stat["val_samples"] += local_stat["val_samples"]


    print("\n" + "=" * 60)
    print("Dataset generation completed!")
    print(f"Total samples: {total_stat['samples']}")
    print(f"Training samples: {total_stat['train_samples']}")
    print(f"Validation samples: {total_stat['val_samples']}")
    print("=" * 60)


    # time_elapsed = frame_idx * cfg.frame_period
    # for t in sim_targets:
    #     t.update(time_elapsed)
    


def main():
    parser = argparse.ArgumentParser(description="Generate Simulated Dataset")
    parser.add_argument(
        "--config", 
        type=str, 
        default="configs/simulate_dataset_config.yaml", 
        help="Path to the configuration file"
    )
    parser.add_argument(
        "--input_dir",
        type=str, 
        default="/Volumes/T9/Data/public_data/gt",
        help="Directory containing target ground truth data"
    )
    parser.add_argument(
        "--output_dir", 
        type=str, 
        default="datasets/pure_simulation",
        help="Directory to save the generated dataset"
    )
    parser.add_argument(
        "--real_snr_path",
        type=str,
        default="datasets/real_uav/snr_values.parquet",
        help="Path to the CSV file containing real statistical SNR data"
    )
    parser.add_argument(
        "--plot_dir",
        type=str,
        default="results/plots/rv_plots",
        help="Directory to save the generated plots"
    )
    parser.add_argument(
        "--num_trajectories",
        type=int,
        default=300,
        help="Number of samples to generate in the simulated dataset"
    )
    parser.add_argument(
        "--frames_per_trajectory",
        type=int,
        default=30,
        help="Number of frames per trajectory"
    )
    parser.add_argument(
        "--snr_mean",
        type=float,
        default=50.0,
        help="Mean SNR for the simulated targets"
    )
    parser.add_argument(
        "--snr_std",
        type=float,
        default=10.0,
        help="Standard deviation of SNR for the simulated targets"
    )
    
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility"
    )

    args = parser.parse_args()

    seed = args.seed
    np.random.seed(seed)

    cfg = Config()
    # Create output directories if they don't exist
    output_dir = Path(args.output_dir)
    image_dir = output_dir / "images"
    label_dir = output_dir / "labels"

    image_dir_train = image_dir / "train"
    image_dir_val = image_dir / "val"
    label_dir_train = label_dir / "train"
    label_dir_val = label_dir / "val"
    image_dir_train.mkdir(parents=True, exist_ok=True)
    image_dir_val.mkdir(parents=True, exist_ok=True)
    label_dir_train.mkdir(parents=True, exist_ok=True)
    label_dir_val.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("Configuration and directories set up:")
    print(f"Number of trajectories: {args.num_trajectories}")
    print(f"Frames per trajectory: {args.frames_per_trajectory}")
    print(f"SNR mean: {args.snr_mean} dB, SNR std: {args.snr_std} dB")
    print(f"Output directory: {output_dir}")
    print(f"Image directories: {image_dir_train}, {image_dir_val}")
    print(f"Label directories: {label_dir_train}, {label_dir_val}")
    print("=" * 60)

    # Here you would add the logic to generate the simulated dataset
    # using the functions and classes imported from core.py
    # This is a placeholder for demonstration purposes
    print("Generating simulated dataset...")
    generate_simulated_data(args=args, cfg=cfg, output_dir=output_dir)  # Replace None with actual config if needed
    
BBOX_WIDTH_BINS = 5  # Width of bounding box in Doppler bins
BBOX_HEIGHT_BINS = 5  # Height of bounding box in Range bins

if __name__ == "__main__":
   main()