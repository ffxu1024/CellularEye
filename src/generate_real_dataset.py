from pathlib import Path
import multiprocessing as mp
import argparse
import numpy as np
import pandas as pd
import pymap3d as pm
from PIL import Image
import yaml
from tqdm import tqdm
from datetime import datetime
from collections import deque
from scipy.interpolate import interp1d
from scipy.ndimage import median_filter
from core import (
    Config, DistributedTarget, LinearTrajectory, 
    generate_radar_channel_matrix, read_bin_file_iq_channel, 
    synthesize_with_calibration, generate_random_linear_trajectory,
    channel_to_rv_map, nomalize_log_power_map, add_window_to_channel_matrix,combine_target_to_background
)

# ROI / snapping parameters
ROI_RANGE_BINS = 5
ROI_DOPPLER_BINS = 21
PEAK_MIN_SNR_DB = 10.0
DC_EXCLUSION_BINS = 11
ZERO_DOPPLER_EXCLUSION_BINS = 11

# Temporal smoothing parameters
MEDIAN_FILTER_KERNEL = 5        # Kernel size for 1D median filter (must be odd)
OUTLIER_RESIDUAL_THRESHOLD = 8  # Max allowed deviation (in bins) from median-filtered value
INTERP_MAX_GAP = 3              # Max consecutive invalid frames to interpolate across


def build_coarse_gt_fn(timestamps: list, coords: np.ndarray, cfg: Config, bs_id: int):
    """
    Build global cubic interpolation functions for distance and velocity.
    Returns a function: get_coarse_gt(target_timestamp) -> (distance_m, velocity_m_s) or (None, None)
    """
    if len(timestamps) < 2:
        return lambda _t: (None, None)

    bs_pos = cfg.position_bs[str(bs_id)]
    bs_lat, bs_lon, bs_alt = bs_pos['latitude'], bs_pos['longitude'], bs_pos['altitude']
    ecef_bs = np.array(pm.geodetic2ecef(bs_lat, bs_lon, bs_alt))

    # Convert GT to seconds
    t0 = timestamps[0]
    ts_seconds = np.array([(t - t0).total_seconds() for t in timestamps], dtype=np.float64)

    # Distance series
    distances = []
    for lat, lon, alt in coords:
        ecef_tgt = np.array(pm.geodetic2ecef(lat, lon, alt))
        distances.append(np.linalg.norm(ecef_tgt - ecef_bs))
    distances = np.asarray(distances, dtype=np.float64)

    # Velocity series (numerical derivative)
    velocities = np.gradient(distances, ts_seconds, edge_order=1)

    # Cubic interpolation for distance and velocity
    dist_interp = interp1d(ts_seconds, distances, kind='cubic', bounds_error=False, fill_value="extrapolate")
    vel_interp = interp1d(ts_seconds, velocities, kind='cubic', bounds_error=False, fill_value="extrapolate")

    def get_coarse_gt(target_timestamp: datetime):
        query_s = (target_timestamp - t0).total_seconds()
        if not np.isfinite(query_s):
            return None, None
        d = float(dist_interp(query_s))
        v = float(vel_interp(query_s))
        if not (np.isfinite(d) and np.isfinite(v)):
            return None, None
        return d, v

    return get_coarse_gt

def snap_peak_in_roi(
    power_map: np.ndarray,
    r_idx: float,
    d_idx: float,
    cfg: Config,
    roi_range_bins: int = ROI_RANGE_BINS,
    roi_doppler_bins: int = ROI_DOPPLER_BINS,
    min_snr_db: float = PEAK_MIN_SNR_DB
):
    """
    Snap to the strongest peak within ROI. Returns (r_idx, d_idx, snr_db) or (None, None, None).
    """
    num_r, num_d = power_map.shape
    r_center = int(round(r_idx))
    d_center = int(round(d_idx))

    r_start = max(0, r_center - roi_range_bins)
    r_end = min(num_r, r_center + roi_range_bins + 1)
    d_start = max(0, d_center - roi_doppler_bins)
    d_end = min(num_d, d_center + roi_doppler_bins + 1)

    if r_start >= r_end or d_start >= d_end:
        return None, None, None

    roi = power_map[r_start:r_end, d_start:d_end].copy()

    # Eliminate DC / zero-Doppler interference
    # Zero Doppler columns
    zero_d = cfg.number_symbols_per_radar_frame // 2
    zd_start = max(d_start, zero_d - ZERO_DOPPLER_EXCLUSION_BINS)
    zd_end = min(d_end, zero_d + ZERO_DOPPLER_EXCLUSION_BINS + 1)
    if zd_start < zd_end:
        roi[:, (zd_start - d_start):(zd_end - d_start)] = 0.0

    # DC range rows
    dc_r_start = max(r_start, 0)
    dc_r_end = min(r_end, DC_EXCLUSION_BINS)
    if dc_r_start < dc_r_end:
        roi[(dc_r_start - r_start):(dc_r_end - r_start), :] = 0.0

    peak_idx = np.unravel_index(np.argmax(roi), roi.shape)
    peak_val = roi[peak_idx]

    noise_floor = np.median(roi[roi > 0]) if np.any(roi > 0) else np.median(roi)
    noise_floor = max(noise_floor, 1e-12)
    peak_snr_db = 10.0 * np.log10(peak_val / noise_floor) if peak_val > 0 else -np.inf

    if not np.isfinite(peak_snr_db) or peak_snr_db < min_snr_db:
        return None, None, None

    snapped_r = r_start + int(peak_idx[0])
    snapped_d = d_start + int(peak_idx[1])
    return float(snapped_r), float(snapped_d), float(peak_snr_db)

def generate_yolo_label_from_indices(cfg: Config, range_idx: float, doppler_idx: float, width_bin: int, height_bin: int) -> list:
    """
    Generate YOLO label from snapped RD indices.
    """
    x_center = doppler_idx / cfg.number_symbols_per_radar_frame
    y_center = range_idx / cfg.number_subcarriers
    width = width_bin / cfg.number_symbols_per_radar_frame
    height = height_bin / cfg.number_subcarriers

    # Match vertically flipped images (np.flipud in save_rd_image)
    y_center = 1.0 - y_center

    x_center = np.clip(x_center, 0.0, 1.0)
    y_center = np.clip(y_center, 0.0, 1.0)

    return [0, x_center, y_center, width, height]


def calculate_k_offset(iq_data: np.ndarray) -> int:
    """
    Calculate k_offset for system bias correction.
    """
    rv_map = channel_to_rv_map(iq_data)
    range_profile = np.mean(rv_map, axis=1)
    k_offset = np.argmax(range_profile)
    return k_offset

def apply_phase_correction(iq_data: np.ndarray, k_offset: int, num_subcarriers: int) -> np.ndarray:
    """
    Apply phase correction to IQ data based on k_offset.
    """
    k = np.arange(num_subcarriers)[:, None]
    phase_ramp = np.exp(1j * 2 * np.pi * k * k_offset / num_subcarriers)
    return iq_data * phase_ramp

def load_ground_truth(gt_file: Path) -> tuple:
    """
    Load ground truth GPS data from text file.
    """
    df = pd.read_csv(gt_file, header=None, names=['timestamp_str', 'latitude', 'longitude', 'altitude'])
    df['timestamp'] = pd.to_datetime(df['timestamp_str'], format='%Y_%m_%d_%H_%M_%S_%f')
    
    timestamps = df['timestamp'].tolist()
    coords = df[['latitude', 'longitude', 'altitude']].values
    
    return timestamps, coords


def save_yolo_label(label: list, output_path: Path):
    """
    Save YOLO format label to text file.
    """
    with open(output_path, 'w') as f:
        f.write(f"{int(label[0])} {label[1]:.6f} {label[2]:.6f} {label[3]:.6f} {label[4]:.6f}\n")

def save_rd_image(rv_map: np.ndarray, output_path: Path, cfg: Config = None):
    """
    Save RD map as image file.
    """
    log_map = nomalize_log_power_map(rv_map)
    img_array = ((log_map + 140) / 140 * 255).clip(0, 255).astype(np.uint8)
    img_array = np.flipud(img_array)
    img = Image.fromarray(img_array, mode='L')
    img.save(output_path)


# ============================================================================
# Two-Pass Trajectory Smoothing helpers
# ============================================================================

def smooth_trajectory(trajectory_data: list,
                      median_kernel: int = MEDIAN_FILTER_KERNEL,
                      residual_thresh: float = OUTLIER_RESIDUAL_THRESHOLD,
                      interp_max_gap: int = INTERP_MAX_GAP) -> list:
    """
    Pass 2 – Outlier rejection via temporal median filtering and interpolation.

    Steps performed on *both* r_idx and d_idx independently:
      1. Extract continuous segments of valid entries.
      2. Apply a 1-D median filter along each segment.
      3. Flag samples whose residual (|raw – median|) exceeds ``residual_thresh``
         as invalid (likely noise catches).
      4. For short gaps (≤ ``interp_max_gap`` consecutive invalids surrounded by
         valid neighbours), linearly interpolate the indices.
      5. Replace raw indices with median-filtered values for surviving valid frames.

    Args:
        trajectory_data: list of dicts produced by Pass 1. Modified **in-place**
            and also returned for convenience.
        median_kernel: size of the 1-D median filter (must be odd).
        residual_thresh: max allowed |raw − median| in bins before a sample is
            declared an outlier.
        interp_max_gap: maximum run of consecutive invalid frames that may be
            filled by linear interpolation.

    Returns:
        The same ``trajectory_data`` list, updated with smoothed indices and
        validity flags.
    """
    n = len(trajectory_data)
    if n == 0:
        return trajectory_data

    # --- helpers to vectorise valid entries --------------------------------
    valid = np.array([d['valid'] for d in trajectory_data], dtype=bool)
    r_raw = np.full(n, np.nan, dtype=np.float64)
    d_raw = np.full(n, np.nan, dtype=np.float64)

    for i, d in enumerate(trajectory_data):
        if d['valid']:
            r_raw[i] = d['r_idx']
            d_raw[i] = d['d_idx']

    # --- per-axis smoothing ------------------------------------------------
    for raw_arr, key in [(r_raw, 'r_idx'), (d_raw, 'd_idx')]:
        # 1) Identify continuous valid segments
        segments = _find_valid_segments(valid)

        for seg_start, seg_end in segments:
            seg_len = seg_end - seg_start
            if seg_len < 2:
                continue  # nothing to filter

            seg_vals = raw_arr[seg_start:seg_end].copy()

            # 2) Median filter inside the segment
            kern = min(median_kernel, seg_len if seg_len % 2 == 1 else seg_len - 1)
            kern = max(kern, 1)
            med_vals = median_filter(seg_vals, size=kern, mode='nearest')

            # 3) Flag outliers (residual too large)
            residuals = np.abs(seg_vals - med_vals)
            outlier_mask = residuals > residual_thresh

            if np.any(outlier_mask):
                for local_i in np.where(outlier_mask)[0]:
                    global_i = seg_start + local_i
                    valid[global_i] = False
                    raw_arr[global_i] = np.nan

            # 4) Replace surviving values with median-filtered version
            for local_i in range(seg_len):
                global_i = seg_start + local_i
                if valid[global_i]:
                    raw_arr[global_i] = med_vals[local_i]

        # 5) Interpolate short gaps of invalid frames
        _interpolate_short_gaps(raw_arr, valid, interp_max_gap)

    # --- write smoothed values back ----------------------------------------
    outliers_removed = 0
    interpolated = 0
    for i, d in enumerate(trajectory_data):
        was_valid = d['valid']
        now_valid = valid[i] and np.isfinite(r_raw[i]) and np.isfinite(d_raw[i])

        if now_valid:
            d['r_idx'] = float(r_raw[i])
            d['d_idx'] = float(d_raw[i])
            d['valid'] = True
            if not was_valid:
                interpolated += 1
        else:
            d['valid'] = False
            if was_valid:
                outliers_removed += 1

    print(f"    [Smoothing] outliers removed: {outliers_removed}, "
          f"gaps interpolated: {interpolated}, "
          f"valid after smoothing: {int(valid.sum())}/{n}")

    return trajectory_data


def _find_valid_segments(valid: np.ndarray) -> list:
    """
    Return a list of (start, end) index tuples for contiguous runs of True
    in the boolean array ``valid``.
    """
    segments = []
    in_segment = False
    start = 0
    for i, v in enumerate(valid):
        if v and not in_segment:
            start = i
            in_segment = True
        elif not v and in_segment:
            segments.append((start, i))
            in_segment = False
    if in_segment:
        segments.append((start, len(valid)))
    return segments


def _interpolate_short_gaps(arr: np.ndarray, valid: np.ndarray, max_gap: int):
    """
    Fill short runs (≤ ``max_gap``) of invalid entries in ``arr`` by linear
    interpolation between the nearest valid neighbours.  Updates ``arr`` and
    ``valid`` **in-place**.
    """
    n = len(arr)
    i = 0
    while i < n:
        if not valid[i]:
            # find the extent of this gap
            gap_start = i
            while i < n and not valid[i]:
                i += 1
            gap_end = i  # first valid after gap (or n)
            gap_len = gap_end - gap_start

            if gap_len <= max_gap and gap_start > 0 and gap_end < n:
                # both sides have valid neighbours → interpolate
                left_val = arr[gap_start - 1]
                right_val = arr[gap_end]
                for j in range(gap_start, gap_end):
                    alpha = (j - gap_start + 1) / (gap_len + 1)
                    arr[j] = left_val + alpha * (right_val - left_val)
                    valid[j] = True
        else:
            i += 1


# ============================================================================
# Main per-collection worker (three-pass)
# ============================================================================

def _generate_real_uav_dataset(task):
    collection, args, cfg, output_dir = task
    print(f"\nProcessing collection: {collection.name}")

    # --- locate data -------------------------------------------------------
    bs_path = collection / "mmw" / f"{args.bs_id}"
    bin_files = sorted(bs_path.glob("*.bin"))
    if not bin_files:
        print(f"No .bin files found in {bs_path}. Skipping.")
        return None
    num_frames = len(bin_files)
    print(f"Found {num_frames} frames in collection {collection.name}.")

    gt_path = collection / "uav"
    gt_files = list(gt_path.glob("*.txt"))
    if not gt_files:
        print(f"  Warning: No ground truth file found in {gt_path}")
        return None
    gt_file = gt_files[0]
    timestamps, coords = load_ground_truth(gt_file)

    # Build global interpolation function for coarse GT
    get_coarse_gt = build_coarse_gt_fn(timestamps, coords, cfg, args.bs_id)

    # ======================================================================
    # Pass 1 – Extraction: loop through frames, snap peaks, collect data
    # ======================================================================
    print(f"  Pass 1: Extracting trajectory from {num_frames} frames …")
    trajectory_data = []

    for frame_idx, frame_file in enumerate(tqdm(
            bin_files,
            desc=f"  [Pass 1] {collection.name}",
            leave=False)):
        entry = {
            'frame_idx': frame_idx,
            'frame_file': frame_file,
            'timestamp': None,
            'r_idx': None,
            'd_idx': None,
            'valid': False,
        }

        try:
            bin_timestamp = datetime.strptime(frame_file.stem, "%Y_%m_%d_%H_%M_%S_%f")
        except ValueError:
            trajectory_data.append(entry)
            continue

        entry['timestamp'] = bin_timestamp

        # Align time: GPS(UTC) = radar_time(TAI) – offset
        query_time = bin_timestamp - pd.Timedelta(seconds=args.utc_offset_seconds)

        # Coarse GT from interpolation
        distance, velocity = get_coarse_gt(query_time)
        if distance is None or velocity is None:
            trajectory_data.append(entry)
            continue

        # Read radar data
        channel_matrix = read_bin_file_iq_channel(
            frame_file, beam_id=args.beam_id,
            rx_id=args.rx_id, symbol_id=args.symbol_id)
        k_offset = calculate_k_offset(channel_matrix)
        corrected_iq = apply_phase_correction(
            channel_matrix, k_offset, cfg.number_subcarriers)

        rv_map = channel_to_rv_map(corrected_iq)
        power_map = np.abs(rv_map)

        # Coarse indices
        coarse_r_idx = distance / cfg.range_bin
        coarse_d_idx = (velocity / cfg.velocity_bin) + \
                       (cfg.number_symbols_per_radar_frame // 2)

        if args.no_peaksnap:
            entry['r_idx'] = coarse_r_idx
            entry['d_idx'] = coarse_d_idx
            entry['valid'] = True
            trajectory_data.append(entry)
            continue

        # Peak snapping in ROI
        snapped_r, snapped_d, peak_snr_db = snap_peak_in_roi(
            power_map, coarse_r_idx, coarse_d_idx, cfg,
            roi_range_bins=ROI_RANGE_BINS,
            roi_doppler_bins=ROI_DOPPLER_BINS,
            min_snr_db=PEAK_MIN_SNR_DB)
        
        if snapped_r is not None and snapped_d is not None:
            entry['r_idx'] = snapped_r
            entry['d_idx'] = snapped_d
            entry['valid'] = True


        trajectory_data.append(entry)

    valid_pass1 = sum(1 for e in trajectory_data if e['valid'])
    print(f"  Pass 1 done: {valid_pass1}/{num_frames} frames with valid peaks.")

    if valid_pass1 == 0:
        print(f"  No valid frames in {collection.name}. Skipping entirely.")
        return {"samples": 0, "train_samples": 0, "val_samples": 0, "test_samples": 0}

    # ======================================================================
    # Pass 2 – Outlier Rejection via Temporal Smoothing
    # ======================================================================
    
    valid_pass2 = valid_pass1

    if args.no_smoothing:
        print("  [Warning] Trajectory smoothing is disabled. This may lead to more outliers in the dataset.")
    else:
        print(f"  Pass 2: Smoothing trajectory …")
        trajectory_data = smooth_trajectory(
            trajectory_data,
            median_kernel=args.median_kernel,
            residual_thresh=args.outlier_thresh,
            interp_max_gap=args.interp_max_gap)

        valid_pass2 = sum(1 for e in trajectory_data if e['valid'])
        print(f"  Pass 2 done: {valid_pass2}/{num_frames} valid after smoothing.")

        if valid_pass2 == 0:
            print(f"  No valid frames remain after smoothing for {collection.name}.")
            return {"samples": 0, "train_samples": 0, "val_samples": 0, "test_samples": 0}



    # ======================================================================
    # Pass 3 – Dataset Generation: re-read RD maps & save with smoothed labels
    # ======================================================================
    print(f"  Pass 3: Generating dataset ({valid_pass2} samples) …")
    local_stat = {"samples": 0, "train_samples": 0, "val_samples": 0, "test_samples": 0}

    for entry in tqdm(trajectory_data,
                      desc=f"  [Pass 3] {collection.name}",
                      leave=False):
        if not entry['valid']:
            continue

        frame_file = entry['frame_file']
        frame_idx = entry['frame_idx']

        # Re-read and process radar data (keeps RAM bounded)
        channel_matrix = read_bin_file_iq_channel(
            frame_file, beam_id=args.beam_id,
            rx_id=args.rx_id, symbol_id=args.symbol_id)
        k_offset = calculate_k_offset(channel_matrix)
        corrected_iq = apply_phase_correction(
            channel_matrix, k_offset, cfg.number_subcarriers)
        rv_map = channel_to_rv_map(corrected_iq)

        # Generate YOLO label from *smoothed* indices
        label = generate_yolo_label_from_indices(
            cfg, entry['r_idx'], entry['d_idx'],
            args.width_bin, args.height_bin)

        # Train / val / test split (80 / 10 / 10 by frame order)
        # if frame_idx < int(0.8 * num_frames):
        #     dataset_type = "train"
        #     local_stat["train_samples"] += 1
        # elif frame_idx < int(0.9 * num_frames):
        #     dataset_type = "val"
        #     local_stat["val_samples"] += 1
        # else:
        #     dataset_type = "test"
        #     local_stat["test_samples"] += 1
        # Only train and val 
        if frame_idx < int(0.9 * num_frames):
            dataset_type = "train"
            local_stat["train_samples"] += 1
        else:
            dataset_type = "val"
            local_stat["val_samples"] += 1

        image_output_path = (output_dir / "images" / dataset_type /
                             f"{collection.name}_{frame_file.stem}.png")
        label_output_path = (output_dir / "labels" / dataset_type /
                             f"{collection.name}_{frame_file.stem}.txt")
        save_rd_image(rv_map, image_output_path, cfg)
        save_yolo_label(label, label_output_path)
        local_stat["samples"] += 1

    print(f"Finished collection {collection.name}: "
          f"{local_stat['samples']} samples "
          f"({local_stat['train_samples']} train, "
          f"{local_stat['val_samples']} val, "
          f"{local_stat['test_samples']} test)")
    return local_stat


def main():
    parser = argparse.ArgumentParser(
        description="Generate real-UAV radar dataset for YOLO training "
                    "(with two-pass trajectory smoothing)")
    parser.add_argument("--num_trajectory", type=int, default=300,
                        help="Number of trajectories to generate")
    # parser.add_argument("--input_dir", type=str,
    #                     default="/Volumes/T9/Data/public_data/gt",
    #                     help="Directory containing input radar data")
    parser.add_argument("--input_dir", type=str,
                        default="data/gt",
                        help="Directory containing input radar data")
    parser.add_argument("--output_dir", type=str,
                        default="datasets/real_uav",
                        help="Directory to save generated dataset")
    parser.add_argument("--cfg_dir", type=str,
                        default="cfg/datasets",
                        help="Directory to save YOLO config files")
    parser.add_argument("--snr_mean", type=float, default=50.0,
                        help="Mean SNR for synthetic data")
    parser.add_argument("--snr_std", type=float, default=10.0,
                        help="Standard deviation of SNR for synthetic data")
    parser.add_argument("--width_bin", type=int, default=10,
                        help="Width of bounding box in bins")
    parser.add_argument("--height_bin", type=int, default=10,
                        help="Height of bounding box in bins")
    parser.add_argument("--bs_id", type=int, default=23,
                        help="BS ID to use")
    parser.add_argument("--beam_id", type=int, default=14,
                        help="Beam ID to use")
    parser.add_argument("--rx_id", type=int, default=0,
                        help="RX ID to use")
    parser.add_argument("--symbol_id", type=int, default=0,
                        help="Symbol ID to use")
    parser.add_argument("--utc_offset_seconds", type=int, default=37,
                        help="Time offset in seconds to align radar and GPS timestamps")
    # Smoothing hyper-parameters (exposed as CLI args)
    parser.add_argument("--median_kernel", type=int,
                        default=MEDIAN_FILTER_KERNEL,
                        help="Kernel size for 1-D median filter (odd)")
    parser.add_argument("--outlier_thresh", type=float,
                        default=OUTLIER_RESIDUAL_THRESHOLD,
                        help="Max |raw-median| in bins before flagging outlier")
    parser.add_argument("--interp_max_gap", type=int,
                        default=INTERP_MAX_GAP,
                        help="Max consecutive invalid frames to interpolate")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility")
    parser.add_argument("--no_peaksnap", action="store_true",
                        help="Whether to perform peak snapping in ROI (Pass 1)")
    parser.add_argument("--no_smoothing", action="store_true",
                        help="Whether to skip Pass 2 trajectory smoothing")
    

    args = parser.parse_args()
    cfg = Config()

    print(f"Configuration of radar parameters: "
          f"Range bin size: {cfg.range_bin} m, "
          f"Velocity bin size: {cfg.velocity_bin} m/s, "
          f"Number of subcarriers: {cfg.number_subcarriers}, "
          f"Number of symbols per radar frame: "
          f"{cfg.number_symbols_per_radar_frame}")
    roi_r = ROI_RANGE_BINS * cfg.range_bin
    roi_v = ROI_DOPPLER_BINS * cfg.velocity_bin
    print(f"ROI size: {roi_r:.2f} m in range, {roi_v:.2f} m/s in velocity")
    print(f"Smoothing: median_kernel={args.median_kernel}, "
          f"outlier_thresh={args.outlier_thresh} bins, "
          f"interp_max_gap={args.interp_max_gap}")

    np.random.seed(args.seed)
    yaml_cfg_dir = Path(args.cfg_dir)
    yaml_cfg_dir.mkdir(parents=True, exist_ok=True)
    # Create output directories
    # save as  output_dir_bs{args.bs_id}_beam{args.beam_id}"
    output_dir = f"{args.output_dir}_bs{args.bs_id}_beam{args.beam_id}_w{args.width_bin}h{args.height_bin}_correct-label-bin"
    if args.no_peaksnap:
        print("  [Warning] Peak snapping in ROI is disabled. This may lead to noisier labels.")
        output_dir += "_no_peaksnap"
    if args.no_smoothing:
        print("  [Warning] Trajectory smoothing is disabled. This may lead to more outliers in the dataset.")
        output_dir += "_no_smoothing"
    print(f"\nOutput directory: {output_dir}")
    output_dir = Path(output_dir)

    for split in ("train", "val", "test"):
        (output_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_dir / "labels" / split).mkdir(parents=True, exist_ok=True)

    collections = [d for d in Path(args.input_dir).iterdir() if d.is_dir()]
    if not collections:
        print(f"\nError: No collections found in {args.input_dir}")
        return

    print(f"\nFound {len(collections)} collections to process")

    total_stat = {"samples": 0, "train_samples": 0, "val_samples": 0, "test_samples": 0}

    tasks = [(collection, args, cfg, output_dir)
             for collection in collections]

    with mp.Pool(processes=mp.cpu_count()) as pool:
        for stat in tqdm(pool.imap_unordered(_generate_real_uav_dataset, tasks),
                         total=len(tasks)):
            if stat is not None:
                total_stat["samples"] += stat["samples"]
                total_stat["train_samples"] += stat["train_samples"]
                total_stat["val_samples"] += stat["val_samples"]
                total_stat["test_samples"] += stat["test_samples"]
                
    yolo_cfg = {
        "path": str(output_dir),
        "train": "images/train",
        "val": "images/val",
        "names": {
            0: "uav"
        }
    }
    suffix_str = ""
    if args.no_peaksnap:
        suffix_str += "_no_peaksnap"
    if args.no_smoothing:
        suffix_str += "_no_smoothing"

    yaml_cfg_path = yaml_cfg_dir / f"real_uav_bs{args.bs_id}_beam{args.beam_id}_w{args.width_bin}h{args.height_bin}_correct-label-bin{suffix_str}.yaml"
    print(f"\nSaving YOLO config file to: {yaml_cfg_path}")
    with open(yaml_cfg_path, "w") as f:
        yaml.dump(yolo_cfg, f)
    
    print("\n" + '=' * 60)
    print("Dataset generation completed.")
    print(f"Total samples: {total_stat['samples']} "
          f"({total_stat['train_samples']} train, "
          f"{total_stat['val_samples']} val, "
          f"{total_stat['test_samples']} test)")
    print('=' * 60)


if __name__ == "__main__":
    main()
