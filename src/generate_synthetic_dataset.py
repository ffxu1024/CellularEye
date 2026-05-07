from pathlib import Path
import multiprocessing as mp
import argparse
import numpy as np
from PIL import Image
from tqdm import tqdm
from core import (
    Config, DistributedTarget, LinearTrajectory, 
    generate_radar_channel_matrix, read_bin_file_iq_channel, 
    synthesize_with_calibration, generate_random_linear_trajectory,
    channel_to_rv_map, nomalize_log_power_map, add_window_to_channel_matrix,combine_target_to_background
)       
def calculate_k_offset(iq_data: np.ndarray) -> int:
    """
    Calculate k_offset for system bias correction.
    
    This finds the strongest peak in the range profile (assumed to be DC/Self-Interference)
    and returns the offset needed to shift it to index 0.
    
    Args:
        iq_data: IQ channel data [num_subcarriers, num_symbols]
        
    Returns:
        int: k_offset value
    """
    # Convert to RV domain
    rv_map = channel_to_rv_map(iq_data)
    
    # Calculate range profile by averaging over Doppler dimension
    range_profile = np.mean(rv_map, axis=1)
    
    # Find peak (assumed to be 0-distance self-interference)
    k_offset = np.argmax(range_profile)
    
    return k_offset

def apply_phase_correction(iq_data: np.ndarray, k_offset: int, cfg: Config) -> np.ndarray:
    """
    Apply phase correction to IQ data based on k_offset.
    
    Args:
        iq_data: Raw IQ channel data
        k_offset: Calculated offset
        num_subcarriers: Number of subcarriers
        
    Returns:
        Corrected IQ data
    """
    k = np.arange(cfg.number_subcarriers)[:, None]
    phase_ramp = np.exp(1j * 2 * np.pi * k * k_offset / cfg.number_subcarriers)
    return iq_data * phase_ramp

def save_yolo_label(label: list, output_path: Path):
    """
    Save YOLO format label to text file.
    
    Args:
        label: [class_id, x_center, y_center, width, height]
        output_path: Path to save label file
    """
    with open(output_path, 'w') as f:
        f.write(f"{int(label[0])} {label[1]:.6f} {label[2]:.6f} {label[3]:.6f} {label[4]:.6f}\n")

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

def generate_yolo_label(cfg: Config, distance: float, velocity: float, width_bin: int, height_bin: int) -> list:
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
        width_bin: Width of the bounding box in bins
        height_bin: Height of the bounding box in bins
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
    width = width_bin / cfg.number_symbols_per_radar_frame
    height = height_bin / cfg.number_subcarriers
    
    # Match vertically flipped images (np.flipud in save_rd_image)
    y_center = 1.0 - y_center

    # Clamp values to valid range
    x_center = np.clip(x_center, 0.0, 1.0)
    y_center = np.clip(y_center, 0.0, 1.0)
    if y_center==0.0 or y_center==1.0:
        print(f"Warning: y_center is at the edge (0 or 1). Check distance: {distance}, range_idx: {range_idx}, y_center: {y_center}")   
    # Class 0 = UAV
    return [0, x_center, y_center, width, height]

def _generate_synthetic_data(task):
    traj_idx, trajectory, collection, args, cfg, output_dir = task
    # Set per-worker deterministic seed so results are reproducible across runs
    # but different between workers (each traj_idx gets a unique seed)
    np.random.seed(args.seed + traj_idx)
    print(f"Processing trajectory {traj_idx} with collection {collection.name}...")
    # 1. Read radar data from collection
    bs_path = collection / "mmw" / f"{args.bs_id}"
    bin_file = sorted(bs_path.glob("*.bin"))  # Assuming one bin file per collection
    if not bin_file:
        print(f"No .bin files found in {bs_path} for trajectory {traj_idx}. Skipping.")
        return
    num_frames = len(bin_file)
    print(f"Found {num_frames} frames in collection {collection.name} for trajectory {traj_idx}.")
    # 2. For each frame, synthesize radar data with the target trajectory and save RD map and YOLO label
    sim_targets = DistributedTarget(trajectory=trajectory, avg_rcs=1, swerling_model='Swerling1', num_scatterers=args.num_scatterers_per_target)  # Simulate multiple scatterers per target for more realistic signature
    local_stat = {
        "samples": 0,
        "train_samples": 0,
        "val_samples": 0
    }
    for frame_idx, bin_path in enumerate(bin_file):
        time_elapsed = frame_idx * cfg.frame_period
        # 1. Update target state to the current frame time BEFORE generation
        sim_targets.update(time_elapsed)

        # Simulated radar channel matrix for the target
        target_channel_matrix = generate_radar_channel_matrix(cfg, [sim_targets], signal_amplitude=1.0)
        if args.add_window:
            target_channel_matrix = add_window_to_channel_matrix(target_channel_matrix)
        # Read real radar data for background
        real_channel_matrix = read_bin_file_iq_channel(bin_path, beam_id=args.beam_id, symbol_id=args.symbol_id, rx_id=args.rx_id)
        k_offset = calculate_k_offset(real_channel_matrix)
        corrected_real_channel_matrix = apply_phase_correction(real_channel_matrix, k_offset, cfg)
        # Synthesize with calibration
        snr_db = np.random.normal(loc=args.snr_mean, scale=args.snr_std)
        synthetic_channel_matrix = combine_target_to_background(cfg, target_channel_matrix, corrected_real_channel_matrix, snr_db)
        # Convert to RV map
        rv_map = channel_to_rv_map(synthetic_channel_matrix)
        
        if frame_idx < int(0.9 * len(bin_file)):
            dataset_type = "train"
            local_stat["train_samples"] += 1
        else:
            dataset_type = "val"
            local_stat["val_samples"] += 1

        # 2. Get actual radar target center (considering scatterer random offsets)
        if hasattr(sim_targets, 'get_scatterers'):
            scatterers = sim_targets.get_scatterers()
            # Calculate the energy center based on RCS weights
            weights = np.array([s[2] for s in scatterers])
            if np.sum(weights) > 0:
                actual_dist = float(np.average([s[0] for s in scatterers], weights=weights))
                actual_vel = float(np.average([s[1] for s in scatterers], weights=weights))
            else:
                actual_dist, actual_vel = sim_targets.distance, sim_targets.velocity
        else:
            actual_dist, actual_vel = sim_targets.distance, sim_targets.velocity

        if actual_dist >= cfg.unambiguous_range or actual_dist < 0:
            print(f"Warning: range {actual_dist} is out of bounds for distance range {cfg.unambiguous_range}. Check traj {traj_idx}, frame {frame_idx}.")
        if actual_vel < -cfg.unambiguous_velocity or actual_vel >= cfg.unambiguous_velocity:
            print(f"Warning: velocity {actual_vel} is out of bounds for velocity {cfg.unambiguous_velocity}. Check traj {traj_idx}, frame {frame_idx}.")

        yolo_label = generate_yolo_label(cfg, actual_dist, actual_vel, args.width_bin, args.height_bin)

        rv_output_path = output_dir / "images" / dataset_type / f"traj_{traj_idx}_frame_{frame_idx}.png"
        save_rd_image(rv_map, rv_output_path, cfg)

        label_output_path = output_dir / "labels" / dataset_type / f"traj_{traj_idx}_frame_{frame_idx}.txt"
        save_yolo_label(yolo_label, label_output_path)

        local_stat["samples"] += 1

    print(f"Finished trajectory {traj_idx}. Generated {local_stat['samples']} samples ({local_stat['train_samples']} train, {local_stat['val_samples']} val).")
    return local_stat

def main():
    """
    Generate synthetic uav dataset based on the provided configuration and save it to the specified output directory.
    """
    parser = argparse.ArgumentParser(description="Generate synthetic radar data for YOLO training")
    parser.add_argument("--num_trajectory", type=int, default=300, help="Number of trajectories to generate")
    parser.add_argument("--input_dir", type=str, default="data/bg", help="Directory containing input radar data") 
    # parser.add_argument("--input_dir", type=str, default="/Volumes/T9/Data/public_data/bg", help="Directory containing input radar data") 
    parser.add_argument("--output_dir", type=str, default="datasets/synthetic_uav", help="Directory to save generated synthetic data")
    parser.add_argument("--cfg_dir", type=str, default="cfg/datasets", help="Directory to .yaml config file for YOLO datasets")
    parser.add_argument("--snr_mean", type=float, default=25.0, help="Mean SNR for synthetic data")  # 25
    parser.add_argument("--snr_std", type=float, default=10.0, help="Standard deviation of SNR for synthetic data")
    parser.add_argument("--width_bin", type=int, default=10, help="Width of bounding box in bins")
    parser.add_argument("--height_bin", type=int, default=10, help="Height of bounding box in bins")
    parser.add_argument("--num_scatterers_per_target", type=int, default=1, help="Number of scatterers to simulate per target for more realistic radar signature")
    parser.add_argument(
        "--initial_distance",
        type=int,
        default=100,
        help="Initial distance of the target in meters"
    )
    parser.add_argument(
        "--initial_velocity", 
        type=float,
        default=4.5,
        help="Initial velocity of the target in m/s"
    )
    parser.add_argument(
        "--bs_id",
        type=str,
        default="23",
        help="Base station ID to process"
    )
    parser.add_argument(
        "--beam_id",
        type=int,
        default=14,
        help="Beam ID for reading bin files"
    )
    parser.add_argument(
        "--rx_id",
        type=int,
        default=0,
        help="RX ID for reading bin files"
    )
    parser.add_argument(
        "--symbol_id",
        type=int,
        default=0,
        help="Symbol ID for reading bin files"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility"
    )
    parser.add_argument(
        "--real_uav_path",
        type=str,
        default="datasets/real_uav",
        help="Path to the real uav dataset"
    )
    parser.add_argument(
        "--same_number_with_real_dataset",
        default=True,
        help="Whether to use the same number of training samples as the real uav dataset"
    )
    parser.add_argument(
        "--add_window",
        action="store_true",
        help="Whether to use the same number of training samples as the real uav dataset"
    )   

    args = parser.parse_args()
    cfg = Config()
    np.random.seed(args.seed)
    # Create output directories if they don't exist

    real_train_samples = 0  # Default value; will be updated if same_number_with_real_dataset is True
    suffix = 0  # Default suffix for output YAML filename

    if args.same_number_with_real_dataset:
        print("\n " + "-" * 50)
        print("Adjusting number of trajectories to match real dataset...")
        print("-" * 50)
        # Count number of training samples in real uav dataset
        real_train_dir = Path(args.real_uav_path) / "labels" / "train"
        real_train_samples = len(list(real_train_dir.glob("*.txt")))
        print(f"Number of training samples in real UAV dataset: {real_train_samples}")
        collection = [p for p in Path(args.input_dir).iterdir() if p.is_dir()]
        mean_num_bin_files = np.mean([len(list((p / "mmw" / f"{args.bs_id}").glob("*.bin"))) for p in collection])
        print(f"Average number of .bin files per collection: {mean_num_bin_files}")
        bin_files_per_collection = [len(list((p / "mmw" / f"{args.bs_id}").glob("*.bin"))) for p in collection]
        if not bin_files_per_collection or bin_files_per_collection[0] == 0:
            print(f"Error: No .bin files found in {Path(args.input_dir) / 'mmw' / f'{args.bs_id}'}. Cannot adjust number of trajectories. Please check the input directory and beam ID.")
            return
        args.num_trajectory = real_train_samples // (int(0.9 * mean_num_bin_files)) + 1  # +1 to ensure we have enough samples
        print(f"Adjusted number of trajectories to generate based on real dataset: {args.num_trajectory}")
        args.output_dir = f"datasets/synthetic_uav_{real_train_samples}"
    
    args.output_dir = f"{args.output_dir}_bs{args.bs_id}_beam{args.beam_id}_snr{args.snr_mean}_std{args.snr_std}_scatterers{args.num_scatterers_per_target}_window{args.add_window}_w{args.width_bin}h{args.height_bin}_correct-label-bin"
    # If output_dir exist, add suffix to avoid overwriting
    if Path(args.output_dir).exists():
        suffix = 1
        new_output_dir = f"{args.output_dir}_{suffix}"
        while Path(new_output_dir).exists():
            suffix += 1
            new_output_dir = f"{args.output_dir}_{suffix}"
        args.output_dir = new_output_dir
        print(f"Output directory already exists. Changed output directory to: {args.output_dir}")

    output_dir = Path(args.output_dir)
    image_dir = output_dir / "images"
    label_dir = output_dir / "labels"
    image_train_dir = image_dir / "train"
    label_train_dir = label_dir / "train"
    image_val_dir = image_dir / "val" 
    label_val_dir = label_dir / "val"
    image_train_dir.mkdir(parents=True, exist_ok=True)
    label_train_dir.mkdir(parents=True, exist_ok=True)
    image_val_dir.mkdir(parents=True, exist_ok=True)
    label_val_dir.mkdir(parents=True, exist_ok=True)

    num_trajectories = args.num_trajectory

    print(f"Generating synthetic uav dataset with config: {cfg}")
    
    print("\n" + "=" * 60)
    print("Starting dataset generation...")
    print("=" * 60 )
    print("\n" + "-" * 50)
    print("Step 1: Read configuration and initialize parameters...")
    print("-" * 50)
    print(f"Input directory: {args.input_dir}")
    print(f"Output directory: {args.output_dir}")
    print(f"Number of trajectories to generate: {args.num_trajectory}")
    print(f"SNR mean: {args.snr_mean} dB, SNR std: {args.snr_std} dB")
    print(f"Bounding box width: {args.width_bin} bins, height: {args.height_bin} bins")

    print("\n" + "-" * 50)
    print(f"Step 2: Read real background radar data from input directory: {args.input_dir}...")
    print("-" * 50)

    input_path = Path(args.input_dir)
    # find all subdirectories in input_path
    collections = [d for d in input_path.iterdir() if d.is_dir()]
    if not collections:
        print(f"No subdirectories found in input directory: {args.input_dir}")
        return
    print(f"Found {len(collections)} collections in input directory.")
        
    if len(collections) >= num_trajectories:
        # random seletc num_trajectories collections
        collections = np.random.choice(collections, size=num_trajectories, replace=False)
        print(f"Randomly selected {num_trajectories} collections for trajectory generation.")
    else:
        print(f"Warning: Number of collections ({len(collections)}) is less than number of trajectories ({num_trajectories}). Some collections will be reused.")
        collections = np.random.choice(collections, size=num_trajectories, replace=True)
        # print(f"Randomly selected {num_trajectories} collections with replacement for trajectory generation.")
        # print(f"collection names: {[c.name for c in collections]}, repeated collections: {[c.name for c in collections if list(collections).count(c) > 1]}")


    print("\n" + "-" * 50)
    print("Step 3: Generate random trajectories...")
    print("-" * 50)

    #  Generate trajectories 
    trajectories = generate_random_linear_trajectory(distance_range=(args.initial_distance-10, args.initial_distance + 10), velocity_range=(args.initial_velocity-0.5, args.initial_velocity + 0.5), num_trajectories=num_trajectories)
    print(f"Generated {num_trajectories} random trajectories.")

    print("\n" + "-" * 50)
    print("Step 4: Synthesize radar data for each trajectory...")
    print("-" * 50)

    total_stat = {
        "samples": 0,
        "train_samples": 0,
        "val_samples": 0
    }
    # Generate synthetic data in parallel
    tasks = [(traj_idx, trajectory, collection, args, cfg, output_dir) for traj_idx, (trajectory, collection) in enumerate(zip(trajectories, collections))]

    print(f"tasks0: {tasks[0]} ...")  # Print first task for debugging
    
    with mp.Pool(processes=mp.cpu_count()) as pool:
        for stat in tqdm(pool.imap_unordered(_generate_synthetic_data, tasks), total=len(tasks)):
            if stat is not None:
                total_stat["samples"] += stat["samples"]
                total_stat["train_samples"] += stat["train_samples"]
                total_stat["val_samples"] += stat["val_samples"]

    if args.same_number_with_real_dataset and total_stat["train_samples"] > real_train_samples:
        print(f"Warning: Generated more training samples ({total_stat['train_samples']}) than real dataset ({real_train_samples}). Consider adjusting num_trajectory or check for duplicates in collections.")
        # Delete extra samples if we have generated more than needed
        excess_train_samples = total_stat["train_samples"] - real_train_samples
        if excess_train_samples > 0:
            print(f"Deleting {excess_train_samples} excess training samples...")
            train_images = sorted((image_train_dir).glob("*.png"))
            train_labels = sorted((label_train_dir).glob("*.txt"))
            for img_path, label_path in zip(train_images[:excess_train_samples], train_labels[:excess_train_samples]):
                img_path.unlink()
                label_path.unlink()
            total_stat["samples"] -= excess_train_samples
            total_stat["train_samples"] -= excess_train_samples
            print(f"Deleted {excess_train_samples} excess training samples. Updated total samples: {total_stat['samples']}, train samples: {total_stat['train_samples']}")
    if args.same_number_with_real_dataset and total_stat["train_samples"] < real_train_samples:
        print(f"Warning: Generated fewer training samples ({total_stat['train_samples']}) than real dataset ({real_train_samples}). Consider increasing num_trajectory or check for issues in data generation.")
    if args.same_number_with_real_dataset and total_stat["train_samples"] == real_train_samples:
        print(f"Successfully generated the same number of training samples as the real dataset: {total_stat['train_samples']} samples.")
    print("\n" + "=" * 60)
    print("Dataset generation completed!")
    print(f"Total samples generated: {total_stat['samples']} (Train: {total_stat['train_samples']}, Val: {total_stat['val_samples']})")
    print("=" * 60)
    # Save args and cfg as .yaml file in output_dir for future reference
    import yaml
    with open(output_dir / "config.yaml", "w") as f:
        yaml.dump({
            "args": vars(args),
            "cfg": vars(cfg)
        }, f)
    # save the .yaml config file for YOLO dataset, include train, val paths, class index, class names, eg: 0: uav
    yolo_cfg = {
        "path": str(output_dir),
        "train": "images/train",
        "val": "images/val",
        "names": {
            0: "uav"
        }
    }
    yolo_cfg_real_val = {
        "path": str(output_dir),
        "train": "images/train",
        "val": f"../real_uav_bs{args.bs_id}_beam{args.beam_id}_w{args.width_bin}h{args.height_bin}_correct-label-bin/images/val",
        "names": {
            0: "uav"
        }
    }

    if suffix > 0:
        suffix_str = f"_bs{args.bs_id}_beam{args.beam_id}_snr{args.snr_mean}_std{args.snr_std}_scatterers{args.num_scatterers_per_target}_window{args.add_window}_w{args.width_bin}h{args.height_bin}_correct-label-bin_{suffix}"
    else:
        suffix_str = f"_bs{args.bs_id}_beam{args.beam_id}_snr{args.snr_mean}_std{args.snr_std}_scatterers{args.num_scatterers_per_target}_window{args.add_window}_w{args.width_bin}h{args.height_bin}_correct-label-bin"

    with open(Path(args.cfg_dir) / f"synthetic_uav_{total_stat['train_samples']}{suffix_str}.yaml", "w") as f:
        yaml.dump(yolo_cfg, f)

    with open(Path(args.cfg_dir) / f"synthetic_uav_{total_stat['train_samples']}{suffix_str}_real_val.yaml", "w") as f:
        yaml.dump(yolo_cfg_real_val, f)

if __name__ == "__main__":
    main()


