import numpy as np  
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from mpl_toolkits.mplot3d import Axes3D
import os
from pathlib import Path
from scipy.ndimage import convolve
import pymap3d as pm

class Config:
    def __init__(self):
        # OFDM Parameters
        self.c = 3e8  # Speed of light in m/s
        self.base_scs = 15e3  # Base subcarrier spacing in Hz
        self.u = 3  # Numerology
        self.fc = 25.6e9  # Carrier frequency in Hz
        self.subcarrier_spacing = self.base_scs * 2**self.u  # Subcarrier spacing 
        self.number_subcarriers = 1024 # Number of FFT points
        self.number_cp = self.number_subcarriers   # Length of cyclic prefix
        self.ofdm_symbols_duration = 1 / self.subcarrier_spacing  # Duration of one OFDM symbol
        self.Ts = 1 / (self.number_subcarriers * self.subcarrier_spacing)  # Sampling period
        self.fs = self.number_subcarriers * self.subcarrier_spacing  # Sampling frequency
        self.zc_u = 25  # ZC sequence root index

        # Radar frame parameters
        self.frame_period = 400e-3  
        self.number_symbols_per_radar_frame = 512
        self.pri = 8.92e-6 * 2 * 6 # Pulse Repetition Interval
        self.cpi = self.number_symbols_per_radar_frame * self.pri

        # Resolution and unambiguous range/velocity
        self.delay_bin = 1 / (self.number_subcarriers * self.subcarrier_spacing)
        self.range_bin = self.c * self.delay_bin / 2
        self.doppler_bin = 1 / self.cpi
        self.velocity_bin = self.doppler_bin * self.c / (2 * self.fc)
        self.unambiguous_range = self.range_bin * self.number_subcarriers
        self.unambiguous_velocity = self.velocity_bin * self.number_symbols_per_radar_frame / 2

        # Plotting parameters
        self.ranges_seq = np.arange(self.number_subcarriers) * self.range_bin
        self.velocity_seq = np.arange(-self.number_symbols_per_radar_frame // 2, self.number_symbols_per_radar_frame // 2) * self.velocity_bin
        self.position_bs = self.generate_positions_bs_dict()

    def generate_positions_bs_dict(self):
        positions_bs_dict = {}
        for bs_id in ["21", "22", "23", "24"]:
            if bs_id == "21":
                # [latitude, longitude, altitude]
                bs_gps = [31.87483116,118.81556122 ,13.75+5.5]
                # [yaw, pitch, roll]
                # [z, y, x] -> ENU; x is zero when pointing east.
                bs_pose = [47.999, 0.181, -68.856]
            elif bs_id == "22":
                bs_gps = [31.87482205,118.81460069,13.1+5.5]
                bs_pose = [49.103, 2.862, -53.383]
            elif bs_id == "23":
                bs_gps = [31.87421618,118.81460101,13.66+5.5]
                bs_pose = [50.576, 0.566, -138.557]
            elif bs_id == "24":
                bs_gps = [31.87421372,118.8155616,13.32+5.5]
                bs_pose = [53.663, -2.911, -140.136]
            positions_bs_dict[bs_id] = {
                "latitude": bs_gps[0],
                "longitude": bs_gps[1],
                "altitude": bs_gps[2],
                "yaw": bs_pose[0],
                "pitch": bs_pose[1],
                "roll": bs_pose[2],
                "gps": bs_gps,
                "pose": bs_pose
            }
        return positions_bs_dict
        # Generate the position dictionary based on the base-station ID.
cfg = Config()

class PointTarget:
    """Simulated point-target class.
    Attributes:
        distance (float): Target distance (m)
        velocity (float): Target radial velocity (m/s)
        avg_rcs (float): Average radar cross section of the target (m^2)
        swerling_model (str): Swerling model type ('Swerling0', 'Swerling1', 'Swerling2', 'Swerling3', 'Swerling4')
    Methods:
        get_rcs(): Get the current RCS value.
        refresh_rcs(): Refresh the RCS value (used by Swerling 1 and 3 models).
        update(time_elapsed): Update the target position and RCS value.
    """
    def __init__(self, trajectory, avg_rcs, swerling_model='Swerling0'):
        self.trajectory = trajectory  # Trajectory instance passed in from above.
        self.avg_rcs = avg_rcs
        self.swerling_model = swerling_model
        self._current_rcs = None
        self.target_dict = self.generate_position_target()

        self.distance, self.velocity = self.trajectory.get_state(0)
        
    def generate_position_target(self):
        # [latitude, longitude, altitude]
        target_gps = [None, None, None]
        # [yaw, pitch, roll]
        return {
            "timestamp": None,
            "latitude": target_gps[0],
            "longitude": target_gps[1],
            "altitude": target_gps[2],
            "gps": target_gps,
            "distance_to_bs21": None, 
            "distance_to_bs22": None,
            "distance_to_bs23": None,
            "distance_to_bs24": None,
            "velocity": [None, None, None],
            "velocity_to_bs21": None,
            "velocity_to_bs22": None,
            "velocity_to_bs23": None,
            "velocity_to_bs24": None
            
        }
    def get_rcs(self):
        if self.swerling_model in ['Swerling1', 'Swerling3'] and self._current_rcs is not None:
            return self._current_rcs

        if self.swerling_model == 'Swerling0':
            rcs = self.avg_rcs
        elif self.swerling_model in ['Swerling1', 'Swerling3']:
            rcs = np.random.chisquare(df=2) * (self.avg_rcs / 2)
            
        elif self.swerling_model in ['Swerling2', 'Swerling4']:
            rcs = np.random.chisquare(df=4) * (self.avg_rcs / 4)
        else:
            raise ValueError(f"Unknown Swerling model: {self.swerling_model}")
        
        if self.swerling_model in ['Swerling1', 'Swerling3']:
            self._current_rcs = rcs

        return rcs
    
    def refresh_rcs(self):
        self._current_rcs = None
        self.get_rcs()

    def update(self, time_elapsed):
        self.distance, self.velocity = self.trajectory.get_state(time_elapsed)
        self.refresh_rcs()


class Trajectory:
    """Base trajectory class."""
    def get_state(self, t):
        """Return (distance, velocity)."""
        raise NotImplementedError


class LinearTrajectory(Trajectory):
    """Constant-velocity linear motion."""
    def __init__(self, d0, v0):
        self.d0 = d0
        self.v0 = v0
    def get_state(self, t):
        return self.d0 + self.v0 * t, self.v0

class AcceleratedTrajectory(Trajectory):
    """Constant-acceleration motion."""
    def __init__(self, d0, v0, a):
        self.d0 = d0
        self.v0 = v0
        self.a = a
    def get_state(self, t):
        v_t = self.v0 + self.a * t
        d_t = self.d0 + self.v0 * t + 0.5 * self.a * (t**2)
        return d_t, v_t

class OscillatingTrajectory(Trajectory):
    """Harmonic/sinusoidal motion, used to simulate UAV hover jitter or back-and-forth inspection."""
    def __init__(self, d_center, amplitude, frequency, phase=0):
        self.d_center = d_center
        self.A = amplitude
        self.f = frequency
        self.phi = phase
    def get_state(self, t):
        omega = 2 * np.pi * self.f
        d_t = self.d_center + self.A * np.sin(omega * t + self.phi)
        v_t = self.A * omega * np.cos(omega * t + self.phi)
        return d_t, v_t

class DistributedTarget(PointTarget):
    """
    Simulate a distributed target with physical extent.
    This is implemented by generating multiple sub-scatterers around the center point.
    """
    def __init__(self, trajectory, avg_rcs, num_scatterers=5, range_spread=5, velocity_spread=0.2, swerling_model='Swerling1'):
        super().__init__(trajectory, avg_rcs, swerling_model)
        self.num_scatterers = num_scatterers
        # Pre-generate the relative offsets of the scatterers from a Gaussian distribution.
        self.r_offsets = np.random.normal(0, range_spread, num_scatterers)
        self.v_offsets = np.random.normal(0, velocity_spread, num_scatterers)
        # Weight each scatterer to mimic a shape with a strong center and weaker edges.
        self.weights = np.exp(-(self.r_offsets**2 + self.v_offsets**2) / (2 * (range_spread/2)**2))
        self.weights /= np.sum(self.weights)

    def get_scatterers(self):
        """Return the current distance and velocity for all scatterers."""
        scatterer_list = []
        for i in range(self.num_scatterers):
            s_dist = self.distance + self.r_offsets[i]
            s_vel = self.velocity + self.v_offsets[i]
            # Each point shares a weighted portion of the total RCS.
            s_rcs = self.get_rcs() * self.weights[i]
            scatterer_list.append((s_dist, s_vel, s_rcs))
        return scatterer_list
    

# Random trajectory generation helpers
def generate_random_trajectory(distance_range=(30, 1000), velocity_range=(-10, 10), acceleration_range=(-2, 2), amplitude_range=(5, 20), frequency=0.2):
    choice = np.random.choice(['linear', 'accel', 'osc'])
    if choice == 'linear':
        return LinearTrajectory(d0=np.random.uniform(*distance_range), v0=np.random.uniform(*velocity_range))
    elif choice == 'accel':
        return AcceleratedTrajectory(d0=np.random.uniform(*distance_range), v0=np.random.uniform(*velocity_range), a=np.random.uniform(*acceleration_range))
    else:
        return OscillatingTrajectory(d_center=np.random.uniform(*distance_range), amplitude=np.random.uniform(*amplitude_range), frequency=frequency)

def generate_random_linear_trajectory(distance_range=(30, cfg.unambiguous_range), velocity_range=(-cfg.unambiguous_velocity, cfg.unambiguous_velocity),num_trajectories=10):
    trajectories = []
    for _ in range(num_trajectories):
        d0 = np.random.uniform(*distance_range)
        v0 = np.random.uniform(*velocity_range)
        trajectories.append(LinearTrajectory(d0, v0))
    return trajectories

def get_label_info(cfg, target):
    """
    Compute the target coordinates on the RD map and the normalized labels.
    """
    # 1. Compute the range-bin index.
    # distance = index * range_bin -> index = distance / range_bin
    range_idx = target.distance / cfg.range_bin
    
    # 2. Compute the Doppler-bin index.
    # velocity_seq spans offsets from -V_max to V_max.
    # index = (velocity / velocity_bin) + (N_symbols / 2)
    doppler_idx = (target.velocity / cfg.velocity_bin) + (cfg.number_symbols_per_radar_frame // 2)
    
    # 3. Normalize coordinates, as commonly used by deep-learning models such as YOLO.
    norm_range = range_idx / cfg.number_subcarriers
    norm_doppler = doppler_idx / cfg.number_symbols_per_radar_frame
    
    return {
        "range_idx": float(range_idx),
        "doppler_idx": float(doppler_idx),
        "norm_range": float(norm_range),
        "norm_doppler": float(norm_doppler),
        "range_m": float(target.distance),
        "velocity_m_s": float(target.velocity),
        "rcs": float(target.get_rcs())  # Instantaneous RCS at the current frame.
    }

def generate_heatmap(cfg, target_list, sigma=1.5):
    heatmap = np.zeros((cfg.number_subcarriers, cfg.number_symbols_per_radar_frame))
    for target in target_list:
        info = get_label_info(cfg, target)
        r0, d0 = int(round(info['range_idx'])), int(round(info['doppler_idx']))
        
        # Generate a Gaussian distribution around r0 and d0.
        for i in range(max(0, r0-6), min(cfg.number_subcarriers, r0+6)):
            for j in range(max(0, d0-6), min(cfg.number_symbols_per_radar_frame, d0+6)):
                dist_sq = (i - info['range_idx'])**2 + (j - info['doppler_idx'])**2
                heatmap[i, j] = max(heatmap[i, j], np.exp(-dist_sq / (2 * sigma**2)))
    return heatmap

def get_yolo_label(cfg, target, width_bins=3, height_bins=3):
    info = get_label_info(cfg, target)
    # Assume the target occupies a 3x3-bin region in the RD map.
    w = width_bins / cfg.number_symbols_per_radar_frame
    h = height_bins / cfg.number_subcarriers

    return [0, info['norm_doppler'], info['norm_range'], w, h]


def read_bin_file_iq_channel(filename: Path | str, beam_id: int, symbol_id: int, rx_id: int):
    """Read raw range and iq data from .bin file
    Args:
        filename (Path): path to the .bin file
        beam_id (int): beam id
        symbol_id (int): symbol id
        rx_id (int): rx id
    Returns:
        range_matrix (np.ndarray): raw range data matrix of shape (1024, 512)
        iq_matrix (np.ndarray): iq data matrix of shape (1024, 512)
    Raises:
        None
    """
    data = np.fromfile(filename, dtype='>i2')
    scan_idx = np.arange(512)
    # Derive group_id from beam_id.
    group_id = beam_id // 6
    # Derive beam_id_ from beam_id.
    beam_id_ = beam_id % 6
    # symbols_idx[scan_idx] = 2*512*30*rx_id + 2*512*beam_id + 2*scan_idx + symbol_id
    symbols_idx = 6*512*2*2*group_id + 6*2*2*scan_idx + 2*2*beam_id_ + 2*symbol_id + rx_id

    # Each symbol has 1024 samples; each sample has I and Q, both stored as int16.
    base_pos = symbols_idx*1024 * 2 
    indices = base_pos[:, None] + np.arange(2048)
    raw_data = data[indices]  # shape: (512, 2048)
    data_i = raw_data[:, 0::2]  # shape: (512, 1024)
    data_q = raw_data[:, 1::2]  # shape: (512, 1024)
    iq_range  = np.zeros((1024, 512), dtype=np.complex64)
    iq_range = data_i.T + 1j * data_q.T
    # range_matrix = np.zeros((2,1024, 512), dtype=np.int16)
    # range_matrix[0,:,:] = data_i.T
    # range_matrix[1,:,:] = data_q.T
    iq_channel = np.fft.fft(iq_range, axis=0)

    return iq_channel


def synthesize_simtarget_plus_realbackground(cfg, targets, real_background_iq_data, ref_peak_power, target_snr_db=15.0):
    # Estimate the noise floor.
    real_background_rv_map = channel_to_rv_map(real_background_iq_data)
    noise_floor = np.median(real_background_rv_map)
    # Compute a fixed amplitude scaling factor.
    desired_avg_target_power = noise_floor * (10 ** (target_snr_db / 10.0))
    fixed_scale_factor = np.sqrt(desired_avg_target_power / ref_peak_power)
    # Generate the target signal using the scaling factor.
    sim_target_radar_channel_matrix = generate_radar_channel_matrix(cfg, targets, signal_amplitude=fixed_scale_factor)
    # Validate the instantaneous SNR; it should fluctuate around 15 dB.
    current_rv = channel_to_rv_map(sim_target_radar_channel_matrix)
    current_peak = np.max(current_rv)
    current_snr = 10 * np.log10(current_peak / noise_floor)
    # Add the background.
    sim_target_plus_background_iq_data = sim_target_radar_channel_matrix + real_background_iq_data
    return sim_target_plus_background_iq_data

def synthesize_with_calibration(cfg, targets, bg_iq, ref_peak_power, target_snr_db=15.0):
    """
    Synthesis function with range calibration.
    """
    # 1. Convert the background to the RV domain for calibration detection.
    # Note: calibrate_rv_matrix_adaptive was originally designed for RV matrices.
    bg_rv = channel_to_rv_map(bg_iq)
    
    # 2. Estimate the offset and calibrate. Here we directly roll the IQ data.
    # Assume the strongest background point corresponds to a zero-range offset caused by self-interference.
    range_profile = np.mean(bg_rv, axis=1)
    k_offset = np.argmax(range_profile)
    # print(f"   -> Detected range offset: {k_offset} bins")
    # Compute the phase ramp: exp(j * 2 * pi * k * offset / N)
    k = np.arange(cfg.number_subcarriers)[:, None]  # shape (1024, 1)
    # Note: k_offset is derived from the IFFT result, so the direction must match.
    phase_ramp = np.exp(1j * 2 * np.pi * k * k_offset / cfg.number_subcarriers)
    calibrated_bg_iq = bg_iq * phase_ramp
    
    # 3. Estimate the noise floor of the calibrated background.
    calibrated_bg_rv = channel_to_rv_map(calibrated_bg_iq)
    noise_floor = np.median(calibrated_bg_rv)
    
    # 4. Compute the target scaling factor.
    desired_avg_target_power = noise_floor * (10 ** (target_snr_db / 10.0))
    fixed_scale_factor = np.sqrt(desired_avg_target_power / ref_peak_power)
    
    # 5. Generate the simulated target and add it to the calibrated background.
    sim_target_iq = generate_radar_channel_matrix(cfg, targets, signal_amplitude=fixed_scale_factor)
    combined_iq = sim_target_iq + calibrated_bg_iq
    
    return combined_iq, k_offset

def synthesize_simtarget_plus_gaussian_noise(cfg, targets, target_snr_db=15.0, noise_variance=1.0):
    """
    Generate a simulated target overlaid with additive white Gaussian noise.
    
    Args:
        cfg: Configuration object.
        ref_peak_power: Peak power of the reference target (RCS=1), used to calibrate target amplitude.
        target_snr_db: Target signal-to-noise ratio on the RD map (dB).
        noise_variance: Variance of the time-domain complex noise.
        
    Returns:
        sim_target_plus_noise_iq_data: Overlaid IQ data.
    """
    # 1. Generate time-domain complex Gaussian white noise.
    # Noise power P_n = E[|n|^2] = 2 * sigma^2 if the real and imaginary parts each have variance sigma^2.
    # Here we control the total variance directly.
    shape = (cfg.number_subcarriers, cfg.number_symbols_per_radar_frame)
    scale = np.sqrt(noise_variance / 2)
    noise_iq_data = scale * (np.random.randn(*shape) + 1j * np.random.randn(*shape))
    
    # 2. Estimate the noise floor on the RD map.
    noise_rv_map = channel_to_rv_map(noise_iq_data)
    noise_floor = np.median(noise_rv_map)
    
    # 3. Compute the target amplitude scaling factor.
    desired_avg_target_power = noise_floor * (10 ** (target_snr_db / 10.0))
    # fixed_scale_factor = np.sqrt(desired_avg_target_power / ref_peak_power)

    # 4. Compute the target signal channel response matrix using a fixed scaling factor to keep a stable average SNR.
    sim_target_radar_channel_matrix = generate_radar_channel_matrix(cfg, targets)
    signal_peak_power = np.max(channel_to_rv_map(sim_target_radar_channel_matrix))
    scale_factor = np.sqrt(desired_avg_target_power / signal_peak_power)
    sim_target_radar_channel_matrix *= scale_factor
    
    # 5. Add the noise.
    sim_target_plus_noise_iq_data = sim_target_radar_channel_matrix + noise_iq_data

    
    return sim_target_plus_noise_iq_data

def ca_cfar_2d(rv_map, guard_cells=(2, 2), training_cells=(5, 5), pfa=1e-6):
    """
    Perform CA-CFAR detection on a 2D RV map.

    Args:
        rv_map: 2D numpy array, linear power spectrum (not dB).
        guard_cells: (g_r, g_d) number of guard cells on each side in range and Doppler.
        training_cells: (t_r, t_d) number of reference cells on each side in range and Doppler.
        pfa: Probability of false alarm.
        
    Returns:
        detections: 2D boolean array, True indicates a detection.
        threshold_map: 2D array, threshold computed for each cell.
    """
    rows, cols = rv_map.shape
    g_r, g_d = guard_cells
    t_r, t_d = training_cells
    
    # 1. Compute the total number of reference cells N.
    # Full window size: (2*t_r + 2*g_r + 1) x (2*t_d + 2*g_d + 1)
    # Guard window size: (2*g_r + 1) x (2*g_d + 1)
    full_window_size = (2 * (t_r + g_r) + 1) * (2 * (t_d + g_d) + 1)
    guard_window_size = (2 * g_r + 1) * (2 * g_d + 1)
    N = full_window_size - guard_window_size
    
    # 2. Compute the scaling factor alpha.
    # For CA-CFAR, alpha = N * (Pfa^(-1/N) - 1)
    alpha = N * (pfa**(-1/N) - 1)
    
    # 3. Use convolution to quickly compute the sum of the reference cells.
    # Create a kernel with zeros at the center (CUT + Guard) and ones around it (Training).
    kernel_r = 2 * (t_r + g_r) + 1
    kernel_d = 2 * (t_d + g_d) + 1
    kernel = np.ones((kernel_r, kernel_d))
    
    # Set the guard region and CUT to zero.
    guard_start_r = t_r
    guard_end_r = t_r + 2 * g_r + 1
    guard_start_d = t_d
    guard_end_d = t_d + 2 * g_d + 1
    kernel[guard_start_r:guard_end_r, guard_start_d:guard_end_d] = 0
    
    # Compute the power sum of the reference cells around each point.
    # mode='constant' pads the edges with zeros, which is acceptable for radar edge detection; alternatively use 'wrap' for circular convolution.
    noise_sum = convolve(rv_map, kernel, mode='constant', cval=0.0)
    
    # 4. Compute the noise average and threshold.
    noise_level = noise_sum / N
    threshold_map = alpha * noise_level
    
    # 5. Detection.
    detections = (rv_map > threshold_map)
    
    return detections, threshold_map


def get_channel_taps_frequency_domain(cfg, targets, symbol_idx):
    taps = np.zeros(cfg.number_subcarriers, dtype=complex)
    time_elapsed = symbol_idx * cfg.pri
    
    for target in targets:
            # If this is a distributed target, iterate over all of its internal scatterers.
        points = target.get_scatterers() if isinstance(target, DistributedTarget) else [(target.distance, target.velocity, target.get_rcs())]
        
        for dist, vel, rcs in points:
            delay = 2 * dist / cfg.c
            doppler = -2 * vel * cfg.fc / cfg.c
            doppler_phase = np.exp(1j * 2 * np.pi * doppler * time_elapsed)
            k = np.arange(cfg.number_subcarriers)
            path_phase = np.exp(-1j * 2 * np.pi * k * cfg.subcarrier_spacing * delay)
            taps += np.sqrt(rcs) * path_phase * doppler_phase
    return taps
 
def generate_radar_channel_matrix(cfg, targets, signal_amplitude=1.0):

    a_radar_frame = np.zeros((cfg.number_subcarriers, cfg.number_symbols_per_radar_frame), dtype=complex)

    for symbol_idx in range(cfg.number_symbols_per_radar_frame):
        a_radar_frame[:, symbol_idx] = get_channel_taps_frequency_domain(cfg, targets, symbol_idx) * signal_amplitude

    return a_radar_frame

def add_window_to_channel_matrix(radar_frame, window_type='hamming'):
    n_sc, n_sym = radar_frame.shape
    if window_type == 'hamming':
        w_range = np.hamming(n_sc)[:, None]  # Window along the range dimension.
        w_doppler = np.hamming(n_sym)[None, :]  # Window along the Doppler dimension.
    else:
        w_range, w_doppler = 1.0, 1.0
    
    windowed_radar_frame = radar_frame * w_range * w_doppler
    return windowed_radar_frame

def generate_noise_background_channel_matrix(cfg, noise_variance=1.0):
    shape = (cfg.number_subcarriers, cfg.number_symbols_per_radar_frame)
    scale = np.sqrt(noise_variance / 2)
    noise_channel_matrix = scale * (np.random.randn(*shape) + 1j * np.random.randn(*shape))  
  
    return noise_channel_matrix

def combine_target_to_background(cfg, target_channel, background_channel, target_snr_db=15.0):
    # 1. Compute noise floor from background
    bg_rv = channel_to_rv_map(background_channel)
    noise_floor = np.median(bg_rv)

    # 2. Compute fixed amplitude scale factor based on desired SNR
    desired_avg_target_power = noise_floor * (10 ** (target_snr_db / 10.0))
    ref_peak_power = np.max(channel_to_rv_map(target_channel))
    fixed_scale_factor = np.sqrt(desired_avg_target_power / ref_peak_power)

    # 3. Scale target channel matrix
    scaled_target_channel = target_channel * fixed_scale_factor

    # 4. Combine scaled target with background
    combined_channel = scaled_target_channel + background_channel
    
    # 5. Optionally, compute and print the actual SNR of the combined signal
    combined_rv = channel_to_rv_map(combined_channel)
    combined_peak = np.max(combined_rv)
    actual_snr_db = 10 * np.log10(combined_peak / noise_floor)
    # print(f"   Desired SNR: {target_snr_db} dB, Actual SNR after combination: {actual_snr_db:.2f} dB")

    return combined_channel

def channel_to_rv_map(radar_frame):
    """
    Convert radar channel matrix to range-velocity map.
    Args:
        radar_frame (np.ndarray): Radar channel matrix of shape (num_subcarriers, num_symbols)
    Returns:
        rv_map (np.ndarray): Range-Velocity map of shape (num_subcarriers, num_symbols)
    """
    range_matrix = np.fft.ifft(radar_frame, axis=0)
    range_doppler_matrix = np.fft.ifft(range_matrix, axis=1)
    range_doppler_shifted_matrix = np.fft.fftshift(range_doppler_matrix, axes=1)
    
    rv_map = range_doppler_shifted_matrix
    rv_map = np.abs(rv_map) ** 2
    
    return rv_map

def channel_to_rv_map_windowed(radar_frame, window_type='hamming'):
    """
    Convert an RV map with windowing applied.
    Args:
        radar_frame: Raw channel matrix.
        window_type: 'hamming', 'hann', 'blackman', etc.
    """
    n_sc, n_sym = radar_frame.shape # [1024, 512]
    
    # 1. Prepare the window functions.
    if window_type == 'hamming':
        w_range = np.hamming(n_sc)[:, None]  # Window along the range dimension.
        w_doppler = np.hamming(n_sym)[None, :]  # Window along the Doppler dimension.
    else:
        w_range, w_doppler = 1.0, 1.0
        
    # 2. Apply the window function before performing the IFFT.
    # Range-dimension processing.
    range_matrix = np.fft.ifft(radar_frame * w_range, axis=0)
    
    # 3. Doppler-dimension processing.
    range_doppler_matrix = np.fft.ifft(range_matrix * w_doppler, axis=1)
    range_doppler_shifted_matrix = np.fft.fftshift(range_doppler_matrix, axes=1)
    
    rv_map = np.abs(range_doppler_shifted_matrix) ** 2
    return rv_map

def range_to_rv_map(range_matrix):
    """
    Convert range matrix to range-velocity map.
    Args:
        range_matrix (np.ndarray): Range matrix of shape (num_subcarriers, num_symbols)
    Returns:
        rv_map (np.ndarray): Range-Velocity map of shape (num_subcarriers, num_symbols)
    """
    range_doppler_matrix = np.fft.ifft(range_matrix, axis=1)
    range_doppler_shifted_matrix = np.fft.fftshift(range_doppler_matrix, axes=1)
    
    rv_map = range_doppler_shifted_matrix
    rv_map = np.abs(rv_map) ** 2
    
    return rv_map

def range_to_channel_matrix(range_matrix):
    """ Convert range matrix to radar channel matrix in frequency domain.
    Args:
        range_matrix (np.ndarray): Range matrix of shape (num_subcarriers, num_symbols)
    Returns:
        radar_frame (np.ndarray): Radar channel matrix in frequency domain of shape (num_subcarriers, num_symbols)
    
    """
    radar_frame = np.fft.fft(range_matrix, axis=0)
    return radar_frame

def nomalize_log_power_map(power_map):
    log_power_map = 10 * np.log10(power_map)
    log_power_map -= np.max(log_power_map)
    return log_power_map

def calibrate_rv_matrix_adaptive(rv_matrix):
    """
    Adaptively calibrate an RV matrix to remove range bias caused by self-interference.

    Logic:
    1. Projection reduction: average the 2D RV matrix along the Doppler axis to obtain a 1D range profile.
    2. Feature extraction: find the peak in the range profile (the self-interference line).
    3. Offset estimation: extract the index k_offset of the maximum-energy point.
    4. Circular shift: use numpy.roll to move the matrix along the range axis so that k_offset returns to 0.
    """
    # 1. Projection reduction.
    range_profile = np.mean(rv_matrix, axis=1)
    
    # 2. Feature extraction and 3. offset estimation.
    # Assume the strongest-energy point is the zero-range bias caused by self-interference.
    k_offset = np.argmax(range_profile)
    
    print(f"  - Detected Range Bias Offset: {k_offset} bins")
    
    # 4. Circular shift.
    # Move k_offset to zero, equivalent to shifting left by k_offset.
    calibrated_matrix = np.roll(rv_matrix, -k_offset, axis=0)
    
    return calibrated_matrix

def plot_2d_range_doppler(cfg, rd_map: np.ndarray, plot_dir: Path | str,  filename: str, cbar_label='Normalized Power (dB)', title='2D Range-Doppler Map'):
    """Plot and save a 2D range-Doppler map."""
    plot_dir = Path(plot_dir)
    plot_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 6))
    im = ax.imshow(rd_map, aspect='auto', cmap='plasma', origin='lower', 
                    extent=[cfg.velocity_seq[0], cfg.velocity_seq[-1], cfg.ranges_seq[0], cfg.ranges_seq[-1]],vmin=-140, vmax=0)
    fig.colorbar(im, ax=ax, label=cbar_label)
    ax.set_title(title)
    ax.set_xlabel('Velocity (m/s)')
    ax.set_ylabel('Range (m)')
    
    save_path = plot_dir / filename
    plt.savefig(save_path, dpi=300)
    # plt.show()
    plt.close(fig)
    print(f"{filename} saved to {plot_dir}")

def plot_cn_2d_range_doppler(cfg, rd_map: np.ndarray, plot_dir: Path | str, title : str, filename: str, cbar_label='Normalized Power (dB)'):
    """Plot and save a 2D range-Doppler map."""
    plot_dir = Path(plot_dir)
    plot_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 6))
    im = ax.imshow(rd_map, aspect='auto', cmap='plasma', origin='lower', 
                    extent=[cfg.velocity_seq[0], cfg.velocity_seq[-1], cfg.ranges_seq[0], cfg.ranges_seq[-1]],vmin=-140, vmax=0)
    fig.colorbar(im, ax=ax, label=cbar_label)
    ax.set_title(title)
    ax.set_xlabel('Velocity (m/s)')
    ax.set_ylabel('Range (m)')
    
    save_path = plot_dir / ("cn_" + filename)
    plt.savefig(save_path, dpi=300)
    # plt.show()
    plt.close(fig)
    print(f"{filename} saved to {plot_dir}")
    
def plot_cfar_results(cfg, rv_map: np.ndarray, detections: np.ndarray, plot_dir: Path | str, title: str, filename: str, targets=None):
    """
    Plot CFAR detection results and optionally mark the ground truth.

    Args:
        cfg: Configuration object.
        rv_map: 2D RD spectrum.
        detections: Boolean detection matrix.
        title: Plot title.
        filename: Output filename.
        targets: (Optional) target list used to draw the ground truth.
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    plot_dir = Path(plot_dir)
    # 1. Draw the original RD map as the background.
    log_rv = nomalize_log_power_map(rv_map)
    im = ax.imshow(log_rv, aspect='auto', cmap='plasma', origin='lower',
                   extent=[cfg.velocity_seq[0], cfg.velocity_seq[-1], cfg.ranges_seq[0], cfg.ranges_seq[-1]],vmax=0,vmin=-140)
    fig.colorbar(im, ax=ax, label='Normalized Power (dB)')
    
    # 2. Draw the CFAR detections.
    det_indices = np.argwhere(detections)
    if len(det_indices) > 0:
        det_ranges = det_indices[:, 0] * cfg.range_bin
        det_velocities = cfg.velocity_seq[det_indices[:, 1]]
        
        # Use black 'x' markers for detections and keep the size modest to reduce occlusion.
        ax.scatter(det_velocities, det_ranges, c='black', marker='x', s=40, label='CFAR Detections', alpha=0.9)

    # 3. Draw the ground truth using red circles.
    if targets is not None:
        gt_velocities = []
        gt_ranges = []
        for target in targets:
            gt_velocities.append(target.velocity)
            gt_ranges.append(target.distance)
        
        # Mark GT with hollow red circles (facecolors='none').
        ax.scatter(gt_velocities, gt_ranges, edgecolors='red', facecolors='none', 
                   marker='o', s=150, linewidths=2, label='Ground Truth')

    ax.legend(loc='upper right')
    ax.set_title(title)
    ax.set_xlabel('Velocity (m/s)')
    ax.set_ylabel('Range (m)')
    
    save_path = plot_dir / filename
    plt.savefig(save_path, dpi=300)
    # plt.show()
    plt.close(fig)
    print(f"{filename} saved to {plot_dir}")

def plot_cn_cfar_results(cfg, rv_map, detections, title, filename, targets=None):
    """
    Plot CFAR detection results and optionally mark the ground truth.

    Args:
        cfg: Configuration object.
        rv_map: 2D RD spectrum.
        detections: Boolean detection matrix.
        title: Plot title.
        filename: Output filename.
        targets: (Optional) target list used to draw the ground truth.
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # 1. Draw the original RD map as the background.
    log_rv = nomalize_log_power_map(rv_map)
    im = ax.imshow(log_rv, aspect='auto', cmap='plasma', origin='lower',
                   extent=[cfg.velocity_seq[0], cfg.velocity_seq[-1], cfg.ranges_seq[0], cfg.ranges_seq[-1]],vmax=0,vmin=-140)
    fig.colorbar(im, ax=ax, label='Normalized Power (dB)')
    
    # 2. Draw the CFAR detections.
    det_indices = np.argwhere(detections)
    if len(det_indices) > 0:
        det_ranges = det_indices[:, 0] * cfg.range_bin
        det_velocities = cfg.velocity_seq[det_indices[:, 1]]
        
        # Use black 'x' markers for detections and keep the size modest to reduce occlusion.
        ax.scatter(det_velocities, det_ranges, c='black', marker='x', s=40, label='CFAR Detections', alpha=0.9)

    # 3. Draw the ground truth using red circles.
    if targets is not None:
        gt_velocities = []
        gt_ranges = []
        for target in targets:
            gt_velocities.append(target.velocity)
            gt_ranges.append(target.distance)
        
        # Mark GT with hollow red circles (facecolors='none').
        ax.scatter(gt_velocities, gt_ranges, edgecolors='red', facecolors='none', 
               marker='o', s=150, linewidths=2, label='Ground Truth')

    ax.legend(loc='upper right')
    ax.set_title(title)
    ax.set_xlabel('Velocity (m/s)')
    ax.set_ylabel('Range (m)')
    
    save_path = os.path.join(cfg.results_rv_plots_dir, "cn_"+filename)
    plt.savefig(save_path, dpi=300)
    # plt.show()
    plt.close(fig)
    print(f"{filename} saved to {cfg.results_rv_plots_dir}")

def plot_gif_from_images(image_paths, output_gif_path, duration=0.5, loop=0):
    import imageio
    images = []
    for filename in image_paths:
        images.append(imageio.imread(filename))
    imageio.mimsave(output_gif_path, images, duration=duration, loop=loop)
    print(f"GIF saved to {output_gif_path}")

def plot_3d_motion_gif(origin_gps: list, target_timestamps: list, target_gps: list, save_path: str):
    """
    Generates a 3D GIF of a moving target in the ENU coordinate system.

    Args:
        origin_gps (list): (latitude, longitude, altitude) of the ENU origin.
        target_timestamps (list): List of timestamps for the target.
        target_gps (list or np.ndarray): List of (latitude, longitude, altitude) for the target.
        save_path (str or Path): Path to save the GIF.
    """
    lat0, lon0, h0 = origin_gps
    
    # Convert target GPS to ENU
    target_gps = np.array(target_gps)
    lats = target_gps[:, 0]
    lons = target_gps[:, 1]
    alts = target_gps[:, 2]
    
    e, n, u = pm.geodetic2enu(lats, lons, alts, lat0, lon0, h0)
    
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')
    
    # Set limits with some padding
    pad = 10
    ax.set_xlim(min(e) - pad, max(e) + pad)
    ax.set_ylim(min(n) - pad, max(n) + pad)
    ax.set_zlim(min(u) - pad, max(u) + pad)
    
    ax.set_xlabel('East (m)')
    ax.set_ylabel('North (m)')
    ax.set_zlabel('Up (m)')
    
    # Plot origin
    ax.scatter(0, 0, 0, c='red', marker='^', s=100, label='Origin')
    
    # Initialize target marker and trajectory
    target_marker, = ax.plot([], [], [], 'bo', markersize=8, label='Target')
    trajectory, = ax.plot([], [], [], 'b--', alpha=0.5)
    
    ax.legend()
    
    def update(frame):
        current_e = e[frame]
        current_n = n[frame]
        current_u = u[frame]
        
        target_marker.set_data([current_e], [current_n])
        target_marker.set_3d_properties([current_u])
        
        # Show trajectory up to current frame
        trajectory.set_data(e[:frame+1], n[:frame+1])
        trajectory.set_3d_properties(u[:frame+1])
        
        ax.set_title(f"Timestamp: {target_timestamps[frame]}")
        return target_marker, trajectory
    
    ani = animation.FuncAnimation(fig, update, frames=len(target_timestamps), interval=200, blit=False)
    
    ani.save(save_path, writer='pillow', fps=5)
    plt.close(fig)
    print(f"Saved 3D motion GIF to {save_path}")
