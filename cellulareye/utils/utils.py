import numpy as np
from pathlib import Path
from PIL import Image
import pandas as pd
import pymap3d as pm
from cellulareye.configs.configs import ScenarioConfig, ISACConfig
from scipy.interpolate import interp1d
from scipy.ndimage import median_filter

# =================== Radar data loading and processing functions ===================
def required_iq_bin_samples(beam_id: int, symbol_id: int, rx_id: int) -> int:
    """Return the minimum number of big-endian int16 values needed by the reader."""
    if not 0 <= beam_id < 30 or symbol_id not in (0, 1) or rx_id not in (0, 1):
        raise ValueError("beam_id must be 0..29; symbol_id and rx_id must be 0 or 1")

    scan_idx = np.arange(512)
    group_id = beam_id // 6
    beam_id_in_group = beam_id % 6
    symbols_idx = (
        6 * 512 * 2 * 2 * group_id
        + 6 * 2 * 2 * scan_idx
        + 2 * 2 * beam_id_in_group
        + 2 * symbol_id
        + rx_id
    )
    return int(symbols_idx[-1] * 1024 * 2 + 2048)


def validate_iq_bin_file(filename: Path | str, beam_id: int, symbol_id: int, rx_id: int) -> None:
    """Raise a descriptive error when a radar frame is too short for IQ extraction."""
    path = Path(filename)
    required_samples = required_iq_bin_samples(beam_id, symbol_id, rx_id)
    actual_bytes = path.stat().st_size
    actual_samples, remainder = divmod(actual_bytes, np.dtype(">i2").itemsize)
    if remainder or actual_samples < required_samples:
        raise ValueError(
            f"Invalid radar bin file {path}: beam {beam_id}, symbol {symbol_id}, "
            f"receiver {rx_id} require at least {required_samples} big-endian int16 "
            f"samples ({required_samples * 2} bytes), but the file contains "
            f"{actual_samples} samples ({actual_bytes} bytes). The file is truncated "
            f"or uses an incompatible capture format."
        )


def load_iq_channel_from_bin_file(filename: Path | str, beam_id: int, symbol_id: int, rx_id: int):
    """
    Load IQ channel data from a binary file for a specific beam, symbol, and receiver.
    """
    validate_iq_bin_file(filename, beam_id, symbol_id, rx_id)
    data = np.memmap(filename, dtype='>i2', mode='r')
    scan_idx = np.arange(512)
    # get group_id from beam_id
    group_id = beam_id // 6
    # get beam_id_ from beam_id
    beam_id_ = beam_id % 6
    # symbols_idx[scan_idx] = 2*512*30*rx_id +  2*512*beam_id + 2*scan_idx + symbol_id
    symbols_idx = 6*512*2*2*group_id + 6*2*2*scan_idx + 2*2*beam_id_ + 2*symbol_id + rx_id

    # each symbol has 1024 samples, each sample has I and Q, each is int16
    base_pos = symbols_idx*1024 * 2
    indices = base_pos[:, None] + np.arange(2048)
    raw_data = data[indices] # shape: (512, 2048)
    data_i = raw_data[:, 0::2] # shape: (512, 1024)
    data_q = raw_data[:, 1::2] # shape: (512, 1024)
    iq_range  = np.zeros((1024, 512), dtype=np.complex64)
    iq_range = data_i.T + 1j * data_q.T

    iq_channel = np.fft.fft(iq_range, axis=0)

    return iq_channel

def load_iq_channels_from_bin_files(all_files: list[Path | str], beam_id: int, symbol_id: int, rx_id: int):
    print(f"\nReading I/Q channel data from {len(all_files)} bin files...")

    return [load_iq_channel_from_bin_file(filename, beam_id, symbol_id, rx_id) for filename in all_files]

def channel_to_rv_map(radar_frame, mode = "original") -> np.ndarray:
    """
    Convert radar channel matrix to RD map using 2D FFT.
    """
    range_matrix = np.fft.ifft(radar_frame, axis=0)
    range_doppler_matrix = np.fft.ifft(range_matrix, axis=1)
    range_doppler_shifted_matrix = np.fft.fftshift(range_doppler_matrix, axes=1)

    rv_map = range_doppler_shifted_matrix

    if mode == "original":
        rv_map = rv_map
    if mode == "power":
        rv_map = np.abs(rv_map)**2
    if mode == "magnitude":
        rv_map = np.abs(rv_map)
    if mode == "log_power":
        rv_map = 10 * np.log10(np.abs(rv_map)**2 + 1e-12)
    if mode == "normalized_log_power":
        log_power_map = 10 * np.log10(np.abs(rv_map)**2 + 1e-12) # avoid -inf values, equal to clip the minimum value to -120 dB
        log_power_map -= np.max(log_power_map)
        rv_map = log_power_map
    return rv_map

def channels_to_rv_maps(channels, mode="log_power"):
    print(f"\nConverting radar channels to RV maps using mode: {mode}...")
    rd_maps = [channel_to_rv_map(channel, mode=mode) for channel in channels]
    rd_maps_stack = np.stack(rd_maps, axis=0)
    mean_power = np.mean(rd_maps_stack)
    std_power = np.std(rd_maps_stack)
    max_power = np.max(rd_maps_stack)
    median_power = np.median(rd_maps_stack)
    print(f"  - RD maps shape: {rd_maps_stack.shape} ")
    print(f"  - Mean power across frames: {mean_power:.2f} dB")
    print(f"  - Std power across frames: {std_power:.2f} dB")
    print(f"  - Median power (noise floor) across frames: {median_power:.2f} dB")
    print(f"  - Max power across frames: {max_power:.2f} dB")
    return rd_maps

def nomalize_log_power_map(power_map):
    log_power_map = 10 * np.log10(power_map)
    log_power_map -= np.max(log_power_map)
    return log_power_map

def load_bin_file(collection_path: Path | str, modality: str, bs_id: str):

    bin_dir = Path(collection_path) / modality / bs_id

    bin_files = sorted(bin_dir.glob("*.bin"))
    if not bin_files:
        return [], []
    bin_timename = [bin_file.stem for bin_file in bin_files]
    first_bin_time = bin_timename[0] if bin_timename else "N/A"
    first_bin_datetime = pd.to_datetime(first_bin_time, format='%Y_%m_%d_%H_%M_%S_%f')
    bin_date_year = first_bin_datetime.year
    bin_date_month = first_bin_datetime.month
    print("\n" + "-"*30 + " Finding Bin Data " + "-"*30 + "\n")
    print(f"Finding {len(bin_files)} .bin files in directory: {bin_dir}")
    print(f"Collection datetime: {first_bin_datetime}")
    print(f"Collection dateyear: {bin_date_year}; Month: {bin_date_month}")
    TAI_UTC_offset = 0.0 if bin_date_year == 2026 and 1 <= bin_date_month <= 5 else 37.0
    print(f"TAI-UTC offset: {TAI_UTC_offset} seconds, GT(UTC) = radar_time(TAI) – offset")
    # before .bin is timestamp,e.g. 2025_12_10_12_02_30_000.bin

    bin_timestamps = pd.to_datetime(bin_timename, format='%Y_%m_%d_%H_%M_%S_%f') - pd.to_timedelta(TAI_UTC_offset, unit='s')
    bin_timestamps = bin_timestamps.tolist()
    if bin_files:
        print("\n" + "-"*30 + " Found bin files " + "-"*30 + "\n")
        print(f"Found bin files {len(bin_files)}")
        print(f"First 5 bin files: {[bin_file.name for bin_file in bin_files[:5]]}")
        print(f"Bin timestamps range: {bin_timestamps[0]} to {bin_timestamps[-1]}")
    else:
        print("No bin files found.")
    return bin_files, bin_timestamps

def load_gt_data(collection_path: Path | str, target_type: str) -> dict[str, tuple[list, np.ndarray, pd.DataFrame]]:
    """Load all available target trajectories, keyed by their GT file name.

    GT files use the flat layout ``<target_type>/data_<target_id>.txt``. A
    collection may therefore contain zero, one, or multiple UAV trajectories.
    """
    gt_dir = Path(collection_path) / target_type
    gt_files = sorted(gt_dir.glob("data_*.txt"))

    if not gt_files:
        print("GT file not found.")
        return {}

    print("\n" + "-" * 30 + " Found GT files " + "-" * 30 + "\n")
    print(f"Found GT files: {len(gt_files)}")
    tracks = {}
    for gt_file in gt_files:
        target_id = gt_file.stem.removeprefix("data_")
        with open(gt_file, 'r', encoding='utf-8') as file_handle:
            tokens = file_handle.read().split()

        if tokens and tokens[0] == 'time':
            num_cols = 6
            data_tokens = tokens[num_cols:]
            rows = [data_tokens[index:index + num_cols] for index in range(0, len(data_tokens), num_cols)]
            df = pd.DataFrame(rows, columns=['timestamp_str', 'latitude', 'longitude', 'altitude', 'speed_h', 'speed_v'])
            df[['latitude', 'longitude', 'altitude']] = df[['latitude', 'longitude', 'altitude']].astype(float)
        else:
            df = pd.read_csv(gt_file, header=None, names=['timestamp_str', 'latitude', 'longitude', 'altitude'])

        df['timestamp'] = pd.to_datetime(df['timestamp_str'], format='%Y_%m_%d_%H_%M_%S_%f')
        gt_timestamps = df['timestamp'].tolist()
        coords = df[['latitude', 'longitude', 'altitude']].to_numpy()
        tracks[target_id] = (gt_timestamps, coords, df)
        print(f"  - {target_id}: {gt_file.name}, {len(gt_timestamps)} samples, {gt_timestamps[0]} to {gt_timestamps[-1]}")

    return tracks

def check_collection_and_gt_overlap(bin_timestamps: list, gt_timestamps: list) -> list:
    # gt time contain collection time or not
    gt_collection_overlap = (gt_timestamps[0] <= bin_timestamps[0]) and (gt_timestamps[-1] >= bin_timestamps[-1])
    print(f"\nCollection time overlaps with GT time: {gt_collection_overlap}")
    if gt_collection_overlap:
        print(f"Collection time range: {bin_timestamps[0]} to {bin_timestamps[-1]}")
        print(f"GT time range: {gt_timestamps[0]} to {gt_timestamps[-1]}")
    else:
        print("Collection time does not overlap with GT time.")
        print(f"Collection time range: {bin_timestamps[0]} to {bin_timestamps[-1]}")
        print(f"GT time range: {gt_timestamps[0]} to {gt_timestamps[-1]}")
    # find the list of GT that overlaps with collection time
    overlapping_gt_indices = [i for i, t in enumerate(gt_timestamps) if bin_timestamps[0] <= t <= bin_timestamps[-1]]
    print(f"Number of GT samples overlapping with collection time: {len(overlapping_gt_indices)}")
    if overlapping_gt_indices:
        print(f"Overlapping GT timestamps: {[gt_timestamps[i] for i in overlapping_gt_indices]}")

    return overlapping_gt_indices

def calibrate_rd_maps_batch(rd_maps: np.ndarray | list) -> tuple[np.ndarray, int]:
    """
    Adaptively calibrate a sequence of Range-Doppler (RD) maps to eliminate range bias
    caused by self-interference, using a stable global offset.

    Instead of correcting each frame independently (which causes temporal jitter),
    this method computes the most frequent delay offset (the mode) across the entire
    sequence and applies it globally.

    Args:
        rd_maps: A list of 2D RD maps or a 3D numpy array [num_frames, num_range, num_doppler].

    Returns:
        calibrated_maps (np.ndarray): The 3D array of calibrated RD maps.
        global_offset (int): The stable range offset bin that was applied.
    """
    # 1. Standardize input to a 3D numpy array [frames, range, doppler]
    if isinstance(rd_maps, list):
        rd_maps = np.stack(rd_maps, axis=0)
    elif rd_maps.ndim != 3:
        raise ValueError("Input must be a 3D array or a list of 2D RD maps.")

    # 2. Projection: Average across the Doppler (velocity) axis for all frames
    # Resulting shape: [frames, range]
    range_profiles = np.mean(rd_maps, axis=2)

    # 3. Feature Extraction: Find the range bin with maximum energy for each frame
    # Resulting shape: [frames]
    frame_offsets = np.argmax(range_profiles, axis=1)

    # 4. Global Offset Calculation: Find the most common offset (mode) among all frames
    # np.bincount is extremely fast for finding the most frequent non-negative integer
    global_offset = int(np.bincount(frame_offsets).argmax())

    print(f"  - Applied Uniform Range Bias Offset: {global_offset} bins")

    # 5. Circular Shift: Roll the entire 3D matrix along the range axis (axis=1)
    calibrated_maps = np.roll(rd_maps, -global_offset, axis=1)

    return calibrated_maps, global_offset

# =================== GT and radar data alignment functions ===================
def LLA_to_ENU(scenario: ScenarioConfig, coords: np.ndarray) -> tuple[np.ndarray, dict]:
    """Convert LLA coordinates to ENU coordinates, using BS 24 as the reference point."""
    bs21 = scenario.base_stations["21"]
    bs22 = scenario.base_stations["22"]
    bs23 = scenario.base_stations["23"]
    bs24 = scenario.base_stations["24"]
    ref_point = bs24
    bs21_enu = pm.geodetic2enu(bs21.latitude, bs21.longitude, bs21.altitude, ref_point.latitude, ref_point.longitude, ref_point.altitude)
    bs22_enu = pm.geodetic2enu(bs22.latitude, bs22.longitude, bs22.altitude, ref_point.latitude, ref_point.longitude, ref_point.altitude)
    bs23_enu = pm.geodetic2enu(bs23.latitude, bs23.longitude, bs23.altitude, ref_point.latitude, ref_point.longitude, ref_point.altitude)
    bs24_enu = pm.geodetic2enu(bs24.latitude, bs24.longitude, bs24.altitude, ref_point.latitude, ref_point.longitude, ref_point.altitude)
    gt_enu = np.array([pm.geodetic2enu(lat, lon, alt, ref_point.latitude, ref_point.longitude, ref_point.altitude) for lat, lon, alt in coords])
    enu_bs = {
        "21": bs21_enu,
        "22": bs22_enu,
        "23": bs23_enu,
        "24": bs24_enu
    }
    return gt_enu, enu_bs

def coarse_rd_labeling(gt_enu: np.ndarray,
                       gt_timestamps: list,
                       bin_timestamps: list,
                       bs_enu: np.ndarray,
                       cfg: ISACConfig,
                       tx_bs_enu: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """
    Directly interpolate Ground Truth (GT) and compute finite differences to
    estimate Range-Doppler (RD) indices.

    Without ``tx_bs_enu``, the measurement is monostatic and range is the
    receiver-to-UAV distance. With it, range is the equivalent bistatic value
    ``(|Tx-UAV| + |UAV-Rx|) / 2``.
    """
    if len(gt_timestamps) < 2:
        return np.full(len(bin_timestamps), np.nan), np.full(len(bin_timestamps), np.nan)

    t0 = gt_timestamps[0]
    t_gt = np.array([(t - t0).total_seconds() for t in gt_timestamps], dtype=np.float64)
    t_radar = np.array([(t - t0).total_seconds() for t in bin_timestamps], dtype=np.float64)

    # Calculate monostatic or equivalent bistatic range time series.
    rx_distances = np.linalg.norm(gt_enu - bs_enu, axis=1)
    if tx_bs_enu is None:
        distances = rx_distances
        geometry = "monostatic"
    else:
        tx_distances = np.linalg.norm(gt_enu - tx_bs_enu, axis=1)
        distances = (tx_distances + rx_distances) / 2.0
        geometry = "bistatic equivalent"

    # Calculate the radial velocity time series
    # (The first derivative of distance with respect to time is the radial velocity)
    velocities = np.gradient(distances, t_gt, edge_order=1)

    # Build interpolation functions and evaluate at radar timestamps
    dist_interp = interp1d(t_gt, distances, kind='cubic' if len(t_gt) >= 4 else 'linear', bounds_error=False, fill_value="extrapolate")
    vel_interp = interp1d(t_gt, velocities, kind='cubic' if len(t_gt) >= 4 else 'linear', bounds_error=False, fill_value="extrapolate")

    dist_radar = dist_interp(t_radar)
    vel_radar = vel_interp(t_radar)

    # Convert physical values to resolution bin indices
    coarse_r_idx = dist_radar / cfg.range_bin
    coarse_d_idx = (vel_radar / cfg.velocity_bin) + (cfg.number_symbols_per_radar_frame // 2)
    # print("Coarse_r_idx:", coarse_r_idx)
    # print("Coarse_d_idx:", coarse_d_idx)
    print(f"  - Coarse RD labeling completed using {geometry} geometry, interpolation, and finite differences.")
    return coarse_r_idx, coarse_d_idx

def precise_rd_labeling(rd_maps: np.ndarray | list,
                        gt_enu: np.ndarray,
                        gt_timestamps: list,
                        bin_timestamps: list,
                        bs_enu: np.ndarray,
                        cfg: ISACConfig,
                        tx_bs_enu: np.ndarray | None = None,
                        roi_range_bins: int = 5,
                        roi_doppler_bins: int = 10,
                        min_snr_db: float = 10.0,
                        median_kernel: int = 5,
                        outlier_thresh: float = 8.0,
                        interp_max_gap: int = 3) -> tuple[np.ndarray, np.ndarray]:
    """
    (Advanced) High-precision aligned RD indices:
    Step 1: Compute basic coarse indices via trajectory interpolation.
    Step 2: Perform peak snapping within a Region of Interest (ROI) and remove static clutter.
    Step 3: Apply temporal smoothing (outlier rejection + short gap interpolation).
    """
    if isinstance(rd_maps, list):
        rd_maps = np.stack(rd_maps, axis=0) # Shape: [Frames, Range, Doppler]

    num_frames, num_r, num_d = rd_maps.shape
    coarse_r, coarse_d = coarse_rd_labeling(
        gt_enu, gt_timestamps, bin_timestamps, bs_enu, cfg, tx_bs_enu=tx_bs_enu
    )

    refined_r = np.full(num_frames, np.nan)
    refined_d = np.full(num_frames, np.nan)
    zero_d_center = cfg.number_symbols_per_radar_frame // 2

    # --- Step 1: Scan each frame for Peak Snapping ---
    for i in range(num_frames):
        if np.isnan(coarse_r[i]) or np.isnan(coarse_d[i]):
            continue

        r_c, d_c = int(round(coarse_r[i])), int(round(coarse_d[i]))

        # Define the ROI boundaries
        r_strt, r_end = max(0, r_c - roi_range_bins), min(num_r, r_c + roi_range_bins + 1)
        d_strt, d_end = max(0, d_c - roi_doppler_bins), min(num_d, d_c + roi_doppler_bins + 1)
        if r_strt >= r_end or d_strt >= d_end:
            continue

        roi = rd_maps[i, r_strt:r_end, d_strt:d_end].copy()

        # Exclude artifacts from zero-Doppler and DC components
        # Comupte the set intersection
        zd_strt, zd_end = max(d_strt, zero_d_center - 11), min(d_end, zero_d_center + 12)
        if zd_strt < zd_end:
            roi[:, (zd_strt - d_strt):(zd_end - d_strt)] = -np.inf

        dc_strt, dc_end = max(r_strt, 0), min(r_end, 11)
        if dc_strt < dc_end:
            roi[(dc_strt - r_strt):(dc_end - r_strt), :] = -np.inf

        if np.isinf(roi).all():
            continue

        peak_idx = np.unravel_index(np.argmax(roi), roi.shape) # unravel the index to 2D
        peak_val = roi[peak_idx]
        valid_roi = roi[roi > -np.inf]
        noise_floor = np.median(valid_roi) if valid_roi.size > 0 else np.nan

        if np.isnan(noise_floor):
            continue

        # Since the input is 10*log10 scaled (dB), SNR = peak - noise
        if (peak_val - noise_floor) >= min_snr_db:
            refined_r[i] = r_strt + peak_idx[0]
            refined_d[i] = d_strt + peak_idx[1]

    # --- Step 2: Trajectory continuity smoothing and correction (Temporal Smoothing) ---
    valid = (~np.isnan(refined_r)) & (~np.isnan(refined_d))

    def apply_smoothing(arr, valid_mask):
        smoothed = arr.copy()
        new_valid = valid_mask.copy()

        # Find continuous valid segments
        segments = []
        start, in_seg = 0, False
        for idx, val in enumerate(new_valid):
            if val and not in_seg:
                start, in_seg = idx, True
            elif not val and in_seg:
                segments.append((start, idx))
                in_seg = False
        if in_seg:
            segments.append((start, len(new_valid)))

        # Frame-wise median filtering to reject jumping outliers
        for s, e in segments:
            seg_len = e - s
            if seg_len < 2:
                continue
            kern = max(1, min(median_kernel, seg_len if seg_len % 2 == 1 else seg_len - 1))

            med_vals = median_filter(smoothed[s:e], size=kern, mode='nearest')
            outliers = np.abs(smoothed[s:e] - med_vals) > outlier_thresh

            if np.any(outliers):
                smoothed[s:e][outliers] = np.nan
                new_valid[s:e][outliers] = False
            smoothed[s:e][~outliers] = med_vals[~outliers]

        # Re-interpolate to fill short gaps
        n = len(smoothed)
        i = 0
        while i < n:
            if not new_valid[i]:
                gap_s = i
                while i < n and not new_valid[i]:
                    i += 1
                gap_e = i
                gap_len = gap_e - gap_s

                if gap_len <= interp_max_gap and gap_s > 0 and gap_e < n:
                    left, right = smoothed[gap_s - 1], smoothed[gap_e]
                    for j in range(gap_s, gap_e):
                        alpha = (j - gap_s + 1) / (gap_len + 1)
                        smoothed[j] = left + alpha * (right - left)
                        new_valid[j] = True
            else:
                i += 1
        return smoothed, new_valid

    refined_r, valid_r = apply_smoothing(refined_r, valid)
    refined_d, valid_d = apply_smoothing(refined_d, valid_r)

    # Intersect valid masks to ensure coordinates are concurrently valid
    final_valid = valid_r & valid_d
    refined_r[~final_valid] = np.nan
    refined_d[~final_valid] = np.nan

    return refined_r, refined_d


def coarse_anchored_rd_labeling(rd_maps: np.ndarray | list,
                                gt_enu: np.ndarray,
                                gt_timestamps: list,
                                bin_timestamps: list,
                                bs_enu: np.ndarray,
                                cfg: ISACConfig,
                                tx_bs_enu: np.ndarray | None = None,
                                roi_range_bins: int = 5,
                                roi_doppler_bins: int = 10,
                                zero_doppler_half_width: int = 11,
                                min_snr_db: float = 10.0) -> tuple[np.ndarray, np.ndarray]:
    """Refine coarse RD labels only when a moving-target peak is observable.

    The coarse GPS trajectory constrains the search region. A zero-Doppler
    notch is applied before detection, and frames without a sufficiently
    prominent local peak remain ``NaN`` rather than being interpolated.
    """
    if isinstance(rd_maps, list):
        rd_maps = np.stack(rd_maps, axis=0)

    num_frames, num_r, num_d = rd_maps.shape
    coarse_r, coarse_d = coarse_rd_labeling(
        gt_enu, gt_timestamps, bin_timestamps, bs_enu, cfg, tx_bs_enu=tx_bs_enu
    )
    refined_r = np.full(num_frames, np.nan)
    refined_d = np.full(num_frames, np.nan)
    zero_doppler_center = cfg.number_symbols_per_radar_frame // 2
    zero_doppler_start = max(0, zero_doppler_center - zero_doppler_half_width)
    zero_doppler_end = min(num_d, zero_doppler_center + zero_doppler_half_width + 1)

    for frame_index in range(num_frames):
        if np.isnan(coarse_r[frame_index]) or np.isnan(coarse_d[frame_index]):
            continue

        range_center = int(round(coarse_r[frame_index]))
        doppler_center = int(round(coarse_d[frame_index]))
        range_start = max(0, range_center - roi_range_bins)
        range_end = min(num_r, range_center + roi_range_bins + 1)
        doppler_start = max(0, doppler_center - roi_doppler_bins)
        doppler_end = min(num_d, doppler_center + roi_doppler_bins + 1)
        if range_start >= range_end or doppler_start >= doppler_end:
            continue

        roi = rd_maps[frame_index, range_start:range_end, doppler_start:doppler_end].copy()
        notch_start = max(doppler_start, zero_doppler_start)
        notch_end = min(doppler_end, zero_doppler_end)
        if notch_start < notch_end:
            roi[:, notch_start - doppler_start:notch_end - doppler_start] = -np.inf

        if np.isneginf(roi).all():
            continue

        peak_index = np.unravel_index(np.argmax(roi), roi.shape)
        peak_value = roi[peak_index]
        valid_cells = roi[np.isfinite(roi)]
        noise_floor = np.median(valid_cells) if valid_cells.size else np.nan
        if np.isfinite(noise_floor) and peak_value - noise_floor >= min_snr_db:
            refined_r[frame_index] = range_start + peak_index[0]
            refined_d[frame_index] = doppler_start + peak_index[1]

    return refined_r, refined_d



# =================== Dataset ETL functions =================== #
def create_yolo_label(r_idx: float, d_idx: float, w_bins: int, h_bins: int, cfg: ISACConfig) -> str:
    """
    Converts RD bin indices into normalized YOLO bounding box coordinates.
    Precisely compensates for the geometrically centered pixel shift (+0.5)
    and handles the vertical flip constraint.
    """
    W = cfg.number_symbols_per_radar_frame
    H = cfg.number_subcarriers

    # +0.5 shifts the coordinate to the exact geometric center of the bin
    exact_d_center = d_idx + 0.5
    exact_r_center = r_idx + 0.5

    # 1. X-axis (Doppler): Standard mapping
    x_c = np.clip(exact_d_center / W, 0.0, 1.0)

    # 2. Y-axis (Range): Mapped top-down for YOLO after a bottom-up np.flipud() image generation
    # Formula: (H - idx - 0.5) / H = 1.0 - (idx + 0.5) / H
    y_c = np.clip(1.0 - (exact_r_center / H), 0.0, 1.0)

    w = w_bins / W
    h = h_bins / H

    return f"0 {x_c:.6f} {y_c:.6f} {w:.6f} {h:.6f}\n"

def save_rd_image_for_yolo(
    log_power_map: np.ndarray,
    filepath: Path,
    vmin: float = -40.0,
    vmax: float = 70.0,
):
    """
    Saves a 2D Range-Doppler log map as an 8-bit PNG image.
    Flips the image so Range=0 is located at the bottom visual edge.
    """
    if vmin >= vmax:
        raise ValueError("vmin must be smaller than vmax")

    img_array = ((log_power_map - vmin) / (vmax - vmin) * 255)
    img_array = img_array.clip(0, 255).astype(np.uint8)
    img_array = np.flipud(img_array)

    img = Image.fromarray(img_array, mode='L')
    img.save(filepath)


def precise_rd_labeling_closest(rd_maps: np.ndarray | list,
                        gt_enu: np.ndarray,
                        gt_timestamps: list,
                        bin_timestamps: list,
                        bs_enu: np.ndarray,
                        cfg: ISACConfig,
                        tx_bs_enu: np.ndarray | None = None,
                        roi_range_bins: int = 5,
                        roi_doppler_bins: int = 27,
                        min_snr_db: float = 10.0,
                        median_kernel: int = 5,
                        outlier_thresh: float = 8.0,
                        interp_max_gap: int = 3,
                        label_mode: str = "peak_snap",
                        direct_path_near_bins: int = 20,
                        direct_path_far_bins: int = 5,
                        direct_path_track_range_bins: int = 3,
                        direct_path_track_doppler_bins: int = 5,
                        direct_path_max_range_jump_bins: int = 5,
                        direct_path_max_doppler_jump_bins: int = 5,
                        direct_path_confirmation_frames: int = 3,
                        direct_path_min_snr_db: float = 15.0,
                        direct_path_fallback_snr_db: float = 12.0,
                        direct_path_max_gap_frames: int = 2,
                        direct_path_blob_min_pixels: int = 4,
                        direct_path_blob_min_range_span: int = 2,
                        direct_path_blob_min_doppler_span: int = 2,
                        direct_path_global_min_support_fraction: float = 0.5,
                        direct_path_global_min_consecutive_frames: int = 4,
                        direct_path_global_range_tolerance_bins: float = 2.0,
                        direct_path_global_doppler_tolerance_bins: float = 4.0,
                        direct_path_global_max_interpolation_gap_frames: int = 3,
                        peak_snap_global_min_snr_db: float = 10.0,
                        peak_snap_global_fallback_snr_db: float = 7.0,
                        peak_snap_global_blob_min_pixels: int = 3,
                        peak_snap_global_blob_min_range_span: int = 2,
                        peak_snap_global_blob_min_doppler_span: int = 2,
                        peak_snap_track_range_bins: int = 3,
                        peak_snap_track_doppler_bins: int = 4) -> tuple[np.ndarray, np.ndarray]:
    """
    (Advanced) High-precision aligned RD indices:
    Step 1: Compute basic coarse indices via trajectory interpolation.
    Step 2: Select a peak within the RTK-constrained Doppler region and remove static clutter.
    Step 3: Apply temporal continuity checks.

    ``label_mode="peak_snap"`` preserves the original local-maximum behavior.
    ``label_mode="direct_path"`` selects the nearest valid local range peak in a
    tight asymmetric RTK range gate, which favors the shortest visible UAV path
    without admitting distant hardware artifacts. It then uses the smoothed
    direct-path trajectory to re-snap each frame to a nearby observed peak.

    ``label_mode="direct_path_blob"`` uses the same range gate and temporal
    tracker, but first groups thresholded pixels into 8-connected bright blobs.
    Only blobs with a minimum 2D extent are candidates, which suppresses
    isolated noise pixels before the nearest-path selection.

    ``label_mode="direct_path_blob_global"`` first detects blobs for every
    frame, then selects one collection-level branch.  A branch is defined by
    a stable range residual relative to the RTK coarse track.  Among branches
    with sufficient support and consecutive detections, the nearest one is
    selected; frames without that branch are left unlabelled rather than
    switching to a farther reflection. Its Doppler trajectory is estimated
    from the reliable detections, so short weak gaps can be recovered using
    fallback blobs while Doppler outliers are rejected.

    ``label_mode="peak_snap_global"`` uses the symmetric coarse ROI and the
    same collection-level consistency checks, but selects the stable blob
    branch closest to the coarse middle-peak prediction rather than the
    nearest-range branch.

    ``label_mode="peak_snap_tracked"`` retains the original per-frame
    peak-snap candidates, uses temporal smoothing only to predict their track,
    and re-snaps each prediction to an observed local peak. This avoids
    exporting the median trajectory at a position between physical peaks.
    """
    if isinstance(rd_maps, list):
        rd_maps = np.stack(rd_maps, axis=0) # Shape: [Frames, Range, Doppler]

    if label_mode not in {"peak_snap", "peak_snap_tracked", "peak_snap_global", "direct_path", "direct_path_blob", "direct_path_blob_global"}:
        raise ValueError("Unsupported label_mode.")
    if direct_path_near_bins < 0 or direct_path_far_bins < 0:
        raise ValueError("Direct-path range gates must be non-negative.")
    if direct_path_track_range_bins < 0 or direct_path_track_doppler_bins < 0:
        raise ValueError("Direct-path tracking gates must be non-negative.")
    if direct_path_max_range_jump_bins < 0 or direct_path_max_doppler_jump_bins < 0:
        raise ValueError("Direct-path continuity gates must be non-negative.")
    if direct_path_confirmation_frames < 1:
        raise ValueError("direct_path_confirmation_frames must be at least one.")
    if direct_path_max_gap_frames < 0:
        raise ValueError("direct_path_max_gap_frames must be non-negative.")
    if direct_path_blob_min_pixels < 1:
        raise ValueError("direct_path_blob_min_pixels must be at least one.")
    if direct_path_blob_min_range_span < 1 or direct_path_blob_min_doppler_span < 1:
        raise ValueError("Direct-path blob spans must be at least one.")
    if not 0.0 < direct_path_global_min_support_fraction <= 1.0:
        raise ValueError("direct_path_global_min_support_fraction must be in (0, 1].")
    if direct_path_global_min_consecutive_frames < 1:
        raise ValueError("direct_path_global_min_consecutive_frames must be at least one.")
    if direct_path_global_range_tolerance_bins < 0:
        raise ValueError("direct_path_global_range_tolerance_bins must be non-negative.")
    if direct_path_global_doppler_tolerance_bins < 0:
        raise ValueError("direct_path_global_doppler_tolerance_bins must be non-negative.")
    if direct_path_global_max_interpolation_gap_frames < 0:
        raise ValueError("direct_path_global_max_interpolation_gap_frames must be non-negative.")
    if peak_snap_global_fallback_snr_db > peak_snap_global_min_snr_db:
        raise ValueError("Peak-snap global fallback SNR must not exceed its primary SNR.")
    if peak_snap_global_blob_min_pixels < 1:
        raise ValueError("peak_snap_global_blob_min_pixels must be at least one.")
    if peak_snap_global_blob_min_range_span < 1 or peak_snap_global_blob_min_doppler_span < 1:
        raise ValueError("Peak-snap global blob spans must be at least one.")
    if peak_snap_track_range_bins < 0 or peak_snap_track_doppler_bins < 0:
        raise ValueError("Peak-snap tracking gates must be non-negative.")
    if direct_path_fallback_snr_db > direct_path_min_snr_db:
        raise ValueError("Fallback SNR must not exceed the direct-path SNR threshold.")

    num_frames, num_r, num_d = rd_maps.shape
    coarse_r, coarse_d = coarse_rd_labeling(
        gt_enu, gt_timestamps, bin_timestamps, bs_enu, cfg, tx_bs_enu=tx_bs_enu,
    )

    refined_r = np.full(num_frames, np.nan)
    refined_d = np.full(num_frames, np.nan)
    direct_candidates = [[] for _ in range(num_frames)]
    fallback_candidates = [[] for _ in range(num_frames)]
    zero_d_center = cfg.number_symbols_per_radar_frame // 2

    # --- Step 1: Scan each frame for Peak Snapping ---
    for i in range(num_frames):
        if np.isnan(coarse_r[i]) or np.isnan(coarse_d[i]):
            continue

        r_c = int(round(coarse_r[i]))
        d_c = int(round(coarse_d[i]))

        # Define the ROI boundaries
        if label_mode in {"direct_path", "direct_path_blob", "direct_path_blob_global"}:
            r_strt = max(0, r_c - direct_path_near_bins)
            r_end = min(num_r, r_c + direct_path_far_bins + 1)
        else:
            r_strt = max(0, r_c - roi_range_bins)
            r_end = min(num_r, r_c + roi_range_bins + 1)
        d_strt, d_end = max(0, d_c - roi_doppler_bins), min(num_d, d_c + roi_doppler_bins + 1)
        if r_strt >= r_end or d_strt >= d_end:
            continue

        roi = rd_maps[i, r_strt:r_end, d_strt:d_end].copy()

        # Exclude artifacts from zero-Doppler and DC components
        # Comupte the set intersection
        zd_strt, zd_end = max(d_strt, zero_d_center - 11), min(d_end, zero_d_center + 12)
        if zd_strt < zd_end:
            roi[:, (zd_strt - d_strt):(zd_end - d_strt)] = -np.inf

        dc_strt, dc_end = max(r_strt, 0), min(r_end, 11)
        if dc_strt < dc_end:
            roi[(dc_strt - r_strt):(dc_end - r_strt), :] = -np.inf

        if np.isinf(roi).all():
            continue

        valid_roi = roi[roi > -np.inf]
        noise_floor = np.median(valid_roi) if valid_roi.size > 0 else np.nan

        if np.isnan(noise_floor):
            continue

        if label_mode in {"direct_path_blob", "direct_path_blob_global", "peak_snap_global"}:
            if label_mode == "peak_snap_global":
                primary_snr = peak_snap_global_min_snr_db
                fallback_snr = peak_snap_global_fallback_snr_db
                blob_min_pixels = peak_snap_global_blob_min_pixels
                blob_min_range_span = peak_snap_global_blob_min_range_span
                blob_min_doppler_span = peak_snap_global_blob_min_doppler_span
            else:
                primary_snr = direct_path_min_snr_db
                fallback_snr = direct_path_fallback_snr_db
                blob_min_pixels = direct_path_blob_min_pixels
                blob_min_range_span = direct_path_blob_min_range_span
                blob_min_doppler_span = direct_path_blob_min_doppler_span
            def extract_blob_candidates(snr_threshold: float) -> list[tuple[int, int]]:
                """Return target-like bright blobs, ordered from near to far range."""
                active = np.isfinite(roi) & ((roi - noise_floor) >= snr_threshold)
                components, num_components = label(active, structure=np.ones((3, 3), dtype=int))
                candidates = []
                for component_id in range(1, num_components + 1):
                    component = components == component_id
                    rows, cols = np.nonzero(component)
                    if rows.size < blob_min_pixels:
                        continue
                    if (rows.max() - rows.min() + 1) < blob_min_range_span:
                        continue
                    if (cols.max() - cols.min() + 1) < blob_min_doppler_span:
                        continue

                    component_values = np.where(component, roi, -np.inf)
                    peak_r, peak_d = np.unravel_index(np.argmax(component_values), component_values.shape)
                    candidates.append((r_strt + int(peak_r), d_strt + int(peak_d)))
                return sorted(candidates, key=lambda candidate: candidate[0])

            direct_candidates[i] = extract_blob_candidates(primary_snr)
            fallback_candidates[i] = extract_blob_candidates(fallback_snr)
            continue

        if label_mode in {"peak_snap", "peak_snap_tracked"}:
            peak_idx = np.unravel_index(np.argmax(roi), roi.shape)
            peak_val = roi[peak_idx]
            if (peak_val - noise_floor) >= min_snr_db:
                refined_r[i] = r_strt + peak_idx[0]
                refined_d[i] = d_strt + peak_idx[1]
            continue

        # Keep range-local maxima only, then choose the earliest visible path.
        range_profile = np.max(roi, axis=1)
        local_peaks = np.flatnonzero(
            (range_profile[1:-1] >= range_profile[:-2])
            & (range_profile[1:-1] > range_profile[2:])
        ) + 1
        peak_snr = range_profile[local_peaks] - noise_floor
        if label_mode == "direct_path":
            fallback_peaks = local_peaks[peak_snr >= direct_path_fallback_snr_db]
            valid_peaks = local_peaks[peak_snr >= direct_path_min_snr_db]
            fallback_candidates[i] = [
                (r_strt + peak_r, d_strt + int(np.argmax(roi[peak_r])))
                for peak_r in fallback_peaks
            ]
        else:
            valid_peaks = local_peaks[peak_snr >= min_snr_db]
        if valid_peaks.size == 0:
            continue

        direct_candidates[i] = [
            (r_strt + peak_r, d_strt + int(np.argmax(roi[peak_r])))
            for peak_r in valid_peaks
        ]

    if label_mode in {"direct_path_blob_global", "peak_snap_global"}:
        # Absolute range changes with the UAV trajectory.  Cluster candidate
        # blobs in residual space instead: a physical propagation branch has
        # an approximately constant (blob_range - coarse_range) residual.
        required_support = int(np.ceil(num_frames * direct_path_global_min_support_fraction))
        branches = []
        for seed_i, seed_candidates in enumerate(direct_candidates):
            for seed_r, _ in seed_candidates:
                seed_residual = seed_r - coarse_r[seed_i]
                matched = []
                longest_run = 0
                current_run = 0
                for frame_i, frame_candidates in enumerate(direct_candidates):
                    consistent = [
                        candidate for candidate in frame_candidates
                        if abs((candidate[0] - coarse_r[frame_i]) - seed_residual)
                        <= direct_path_global_range_tolerance_bins
                    ]
                    if consistent:
                        selected = min(
                            consistent,
                            key=lambda candidate: abs((candidate[0] - coarse_r[frame_i]) - seed_residual),
                        )
                        matched.append((frame_i, selected))
                        current_run += 1
                        longest_run = max(longest_run, current_run)
                    else:
                        current_run = 0

                if len(matched) < required_support or longest_run < direct_path_global_min_consecutive_frames:
                    continue
                residuals = np.array([candidate[0] - coarse_r[frame_i] for frame_i, candidate in matched])
                branches.append((
                    float(np.median(residuals)),
                    len(matched),
                    longest_run,
                    float(np.median(np.abs(residuals - np.median(residuals)))),
                ))

        if branches:
            if label_mode == "direct_path_blob_global":
                # Direct-path policy: select the nearest stable propagation branch.
                branch_key = lambda branch: (branch[0], -branch[1], -branch[2], branch[3])
                branch_name = "direct-path"
            else:
                # Peak-snap policy: corrected coarse geometry predicts the
                # desired middle peak, so choose the stable branch nearest it.
                branch_key = lambda branch: (abs(branch[0]), -branch[1], -branch[2], branch[3])
                branch_name = "peak-snap"
            branch_residual, support, longest_run, residual_mad = min(branches, key=branch_key)
            print(
                f"  - Selected global {branch_name} blob branch: "
                f"range residual {branch_residual:.2f} bins, "
                f"support {support}/{num_frames}, longest run {longest_run}."
            )
            strict_candidates = [None] * num_frames
            for frame_i, frame_candidates in enumerate(direct_candidates):
                consistent = [
                    candidate for candidate in frame_candidates
                    if abs((candidate[0] - coarse_r[frame_i]) - branch_residual)
                    <= direct_path_global_range_tolerance_bins
                ]
                if consistent:
                    strict_candidates[frame_i] = min(
                        consistent,
                        key=lambda candidate: abs((candidate[0] - coarse_r[frame_i]) - branch_residual),
                    )

            # Reject isolated Doppler outliers using the neighbouring strict
            # detections.  Range has already been assigned to the collection
            # branch, so this test only protects the velocity coordinate.
            reliable = np.array([candidate is not None for candidate in strict_candidates])
            strict_d = np.array([
                np.nan if candidate is None else candidate[1]
                for candidate in strict_candidates
            ], dtype=float)
            for frame_i in np.flatnonzero(reliable):
                neighbours = np.flatnonzero(reliable)
                left = neighbours[neighbours < frame_i]
                right = neighbours[neighbours > frame_i]
                if left.size > 0 and right.size > 0:
                    left_i, right_i = left[-1], right[0]
                    alpha = (frame_i - left_i) / (right_i - left_i)
                    expected_d = strict_d[left_i] + alpha * (strict_d[right_i] - strict_d[left_i])
                elif left.size >= 2:
                    # At a sequence end, extrapolate from the preceding two
                    # anchors instead of automatically trusting a new blob.
                    left_i, previous_i = left[-1], left[-2]
                    slope = (strict_d[left_i] - strict_d[previous_i]) / (left_i - previous_i)
                    expected_d = strict_d[left_i] + slope * (frame_i - left_i)
                elif right.size >= 2:
                    # Symmetric protection for an outlier at a sequence start.
                    right_i, following_i = right[0], right[1]
                    slope = (strict_d[following_i] - strict_d[right_i]) / (following_i - right_i)
                    expected_d = strict_d[right_i] - slope * (right_i - frame_i)
                else:
                    continue
                if abs(strict_d[frame_i] - expected_d) > direct_path_global_doppler_tolerance_bins:
                    reliable[frame_i] = False

            # Interpolate only short gaps between reliable anchors.  A
            # fallback candidate must still lie on both the selected range
            # branch and this Doppler trajectory before it can be exported.
            expected_d = np.full(num_frames, np.nan)
            anchors = np.flatnonzero(reliable)
            expected_d[anchors] = strict_d[anchors]
            for left_i, right_i in zip(anchors[:-1], anchors[1:]):
                gap = right_i - left_i - 1
                if gap > direct_path_global_max_interpolation_gap_frames:
                    continue
                expected_d[left_i:right_i + 1] = np.linspace(
                    strict_d[left_i], strict_d[right_i], right_i - left_i + 1,
                )

            strict_count = 0
            recovered_count = 0
            for frame_i, predicted_d in enumerate(expected_d):
                if np.isnan(predicted_d):
                    continue
                strict_branch_candidates = [
                    candidate for candidate in direct_candidates[frame_i]
                    if abs((candidate[0] - coarse_r[frame_i]) - branch_residual)
                    <= direct_path_global_range_tolerance_bins
                ]
                fallback_branch_candidates = [
                    candidate for candidate in fallback_candidates[frame_i]
                    if abs((candidate[0] - coarse_r[frame_i]) - branch_residual)
                    <= direct_path_global_range_tolerance_bins
                    and candidate not in strict_branch_candidates
                ]
                compatible = [
                    (candidate, True) for candidate in strict_branch_candidates
                    if abs(candidate[1] - predicted_d) <= direct_path_global_doppler_tolerance_bins
                ] + [
                    (candidate, False) for candidate in fallback_branch_candidates
                    if abs(candidate[1] - predicted_d) <= direct_path_global_doppler_tolerance_bins
                ]
                if not compatible:
                    continue
                selected, is_strict = min(
                    compatible,
                    key=lambda item: (
                        abs(item[0][1] - predicted_d),
                        abs((item[0][0] - coarse_r[frame_i]) - branch_residual),
                    ),
                )
                refined_r[frame_i], refined_d[frame_i] = selected
                if is_strict:
                    strict_count += 1
                else:
                    recovered_count += 1
            print(
                f"  - Exported {strict_count} strict and {recovered_count} "
                "Doppler-consistent fallback labels."
            )
        else:
            print("  - No stable global blob branch found; collection skipped.")

    elif label_mode in {"direct_path", "direct_path_blob"}:
        previous = None
        confirmation_count = 0
        gap_count = 0
        for i, candidates in enumerate(direct_candidates):
            if previous is None and not candidates:
                gap_count += 1
                if gap_count > direct_path_max_gap_frames:
                    confirmation_count = 0
                continue
            if previous is None:
                selected = candidates[0]
                confirmation_count = 1
                gap_count = 0
            else:
                prev_i, prev_r, prev_d = previous
                expected_r = prev_r + coarse_r[i] - coarse_r[prev_i]
                expected_d = prev_d + coarse_d[i] - coarse_d[prev_i]
                continuous = [
                    candidate for candidate in candidates
                    if abs(candidate[0] - expected_r) <= direct_path_max_range_jump_bins
                    and abs(candidate[1] - expected_d) <= direct_path_max_doppler_jump_bins
                ]
                if not continuous and confirmation_count >= direct_path_confirmation_frames:
                    continuous = [
                        candidate for candidate in fallback_candidates[i]
                        if abs(candidate[0] - expected_r) <= direct_path_max_range_jump_bins
                        and abs(candidate[1] - expected_d) <= direct_path_max_doppler_jump_bins
                    ]
                if not continuous:
                    gap_count += 1
                    if gap_count > direct_path_max_gap_frames:
                        previous = None
                        confirmation_count = 0
                    continue
                selected = continuous[0]
                confirmation_count += 1
                gap_count = 0
            if confirmation_count >= direct_path_confirmation_frames:
                refined_r[i], refined_d[i] = selected
            previous = (i, *selected)

    # --- Step 2: Trajectory continuity smoothing and correction (Temporal Smoothing) ---
    valid = (~np.isnan(refined_r)) & (~np.isnan(refined_d))

    def apply_smoothing(arr, valid_mask, interpolate_gaps=True):
        smoothed = arr.copy()
        new_valid = valid_mask.copy()

        # Find continuous valid segments
        segments = []
        start, in_seg = 0, False
        for idx, val in enumerate(new_valid):
            if val and not in_seg:
                start, in_seg = idx, True
            elif not val and in_seg:
                segments.append((start, idx))
                in_seg = False
        if in_seg:
            segments.append((start, len(new_valid)))

        # Frame-wise median filtering to reject jumping outliers
        for s, e in segments:
            seg_len = e - s
            if seg_len < 2:
                continue
            kern = max(1, min(median_kernel, seg_len if seg_len % 2 == 1 else seg_len - 1))

            med_vals = median_filter(smoothed[s:e], size=kern, mode='nearest')
            outliers = np.abs(smoothed[s:e] - med_vals) > outlier_thresh

            if np.any(outliers):
                smoothed[s:e][outliers] = np.nan
                new_valid[s:e][outliers] = False
            smoothed[s:e][~outliers] = med_vals[~outliers]

        # Re-interpolate to fill short gaps
        n = len(smoothed)
        i = 0
        while i < n:
            if not new_valid[i]:
                gap_s = i
                while i < n and not new_valid[i]:
                    i += 1
                gap_e = i
                gap_len = gap_e - gap_s

                if interpolate_gaps and gap_len <= interp_max_gap and gap_s > 0 and gap_e < n:
                    left, right = smoothed[gap_s - 1], smoothed[gap_e]
                    for j in range(gap_s, gap_e):
                        alpha = (j - gap_s + 1) / (gap_len + 1)
                        smoothed[j] = left + alpha * (right - left)
                        new_valid[j] = True
            else:
                i += 1
        return smoothed, new_valid

    if label_mode in {"direct_path", "direct_path_blob", "direct_path_blob_global", "peak_snap_global"}:
        valid_r = valid.copy()
        valid_d = valid.copy()
    else:
        refined_r, valid_r = apply_smoothing(refined_r, valid)
        refined_d, valid_d = apply_smoothing(refined_d, valid_r)

    if label_mode == "peak_snap_tracked":
        # The smoother is a trajectory predictor only. Re-snap it to a real
        # observed peak so label centres never remain at a median position
        # between two physical RD peaks.
        predicted_r, predicted_d = refined_r.copy(), refined_d.copy()
        snapped_r = np.full(num_frames, np.nan)
        snapped_d = np.full(num_frames, np.nan)

        # Median filtering is deliberately conservative in the sequence
        # interior, but its ``nearest`` boundary mode can copy a bad first or
        # last measurement into the predictor.  For a contiguous measurement
        # segment, estimate only its endpoints from the next/previous stable
        # predicted points.  This is still just a search-window predictor:
        # the final label is always re-snapped to a measured RD peak below.
        raw_valid = valid.copy()
        prediction_valid = (
            valid_r & valid_d & np.isfinite(predicted_r) & np.isfinite(predicted_d)
        )

        def endpoint_prediction(endpoint: int, direction: int):
            anchors = []
            current = endpoint + direction
            while 0 <= current < num_frames and len(anchors) < 3:
                if prediction_valid[current]:
                    anchors.append(current)
                current += direction
            if len(anchors) < 2:
                return None
            anchor_t = np.asarray(anchors, dtype=float)
            range_fit = np.polyfit(anchor_t, predicted_r[anchors], deg=1)
            doppler_fit = np.polyfit(anchor_t, predicted_d[anchors], deg=1)
            return (
                float(np.polyval(range_fit, endpoint)),
                float(np.polyval(doppler_fit, endpoint)),
            )

        raw_indices = np.flatnonzero(raw_valid)
        if raw_indices.size:
            segment_start = raw_indices[0]
            previous = raw_indices[0]
            segments = []
            for current in raw_indices[1:]:
                if current != previous + 1:
                    segments.append((segment_start, previous))
                    segment_start = current
                previous = current
            segments.append((segment_start, previous))
            for start, end in segments:
                for endpoint, direction in ((start, 1), (end, -1)):
                    estimate = endpoint_prediction(endpoint, direction)
                    if estimate is not None:
                        predicted_r[endpoint], predicted_d[endpoint] = estimate
                        valid_r[endpoint] = True
                        valid_d[endpoint] = True

        for i in range(num_frames):
            if (
                not valid_r[i]
                or not valid_d[i]
                or not np.isfinite(predicted_r[i])
                or not np.isfinite(predicted_d[i])
            ):
                continue
            r_center, d_center = int(round(predicted_r[i])), int(round(predicted_d[i]))
            r_start = max(0, r_center - peak_snap_track_range_bins)
            r_end = min(num_r, r_center + peak_snap_track_range_bins + 1)
            d_start = max(0, d_center - peak_snap_track_doppler_bins)
            d_end = min(num_d, d_center + peak_snap_track_doppler_bins + 1)
            local_roi = rd_maps[i, r_start:r_end, d_start:d_end].copy()

            zd_start, zd_end = max(d_start, zero_d_center - 11), min(d_end, zero_d_center + 12)
            if zd_start < zd_end:
                local_roi[:, (zd_start - d_start):(zd_end - d_start)] = -np.inf
            dc_start, dc_end = max(r_start, 0), min(r_end, 11)
            if dc_start < dc_end:
                local_roi[(dc_start - r_start):(dc_end - r_start), :] = -np.inf
            if np.isinf(local_roi).all():
                continue

            local_noise = np.median(local_roi[np.isfinite(local_roi)])
            peak_r, peak_d = np.unravel_index(np.argmax(local_roi), local_roi.shape)
            if local_roi[peak_r, peak_d] - local_noise >= min_snr_db:
                snapped_r[i] = r_start + peak_r
                snapped_d[i] = d_start + peak_d

        refined_r, refined_d = snapped_r, snapped_d
        valid_r = ~np.isnan(refined_r)
        valid_d = ~np.isnan(refined_d)

    # Intersect valid masks to ensure coordinates are concurrently valid
    final_valid = valid_r & valid_d
    refined_r[~final_valid] = np.nan
    refined_d[~final_valid] = np.nan

    return refined_r, refined_d, coarse_r, coarse_d
