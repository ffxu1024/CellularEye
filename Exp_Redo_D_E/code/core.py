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
                # [z, y, x ] - > ENU # x指向正东时为0
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
        # 根据 id_bs 生成位置字典的逻辑
cfg = Config()

class PointTarget:
    """模拟点目标类
    Attributes:
        distance (float): 目标距离 (m)
        velocity (float): 目标径向速度 (m/s)
        avg_rcs (float): 目标平均雷达截面积 (m^2)
        swerling_model (str): Swerling 模型类型 ('Swerling0', 'Swerling1', 'Swerling2', 'Swerling3', 'Swerling4')
    Methods:
        get_rcs(): 获取当前时刻的 RCS 值
        refresh_rcs(): 刷新 RCS 值（用于 Swerling 1 和 3 模型）
        update(time_elapsed): 更新目标位置和 RCS 值
    """
    def __init__(self, trajectory, avg_rcs, swerling_model='Swerling0'):
        self.trajectory = trajectory  # 传入上面的轨迹实例
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
    """轨迹基类"""
    def get_state(self, t):
        """返回 (distance, velocity)"""
        raise NotImplementedError


class LinearTrajectory(Trajectory):
    """匀速直线运动"""
    def __init__(self, d0, v0):
        self.d0 = d0
        self.v0 = v0
    def get_state(self, t):
        return self.d0 + self.v0 * t, self.v0

class AcceleratedTrajectory(Trajectory):
    """匀加速运动"""
    def __init__(self, d0, v0, a):
        self.d0 = d0
        self.v0 = v0
        self.a = a
    def get_state(self, t):
        v_t = self.v0 + self.a * t
        d_t = self.d0 + self.v0 * t + 0.5 * self.a * (t**2)
        return d_t, v_t

class OscillatingTrajectory(Trajectory):
    """简谐运动/正弦波动（模拟无人机悬停抖动或来回巡检）"""
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
    模拟具有物理尺寸的分布式目标。
    通过在中心点周围生成多个散射点（Sub-scatterers）来实现。
    """
    def __init__(self, trajectory, avg_rcs, num_scatterers=5, range_spread=5, velocity_spread=0.2, swerling_model='Swerling1'):
        super().__init__(trajectory, avg_rcs, swerling_model)
        self.num_scatterers = num_scatterers
        # 预生成散射点的相对偏移，服从高斯分布
        self.r_offsets = np.random.normal(0, range_spread, num_scatterers)
        self.v_offsets = np.random.normal(0, velocity_spread, num_scatterers)
        # 每个散射点的权重（模拟形状，中心强边缘弱）
        self.weights = np.exp(-(self.r_offsets**2 + self.v_offsets**2) / (2 * (range_spread/2)**2))
        self.weights /= np.sum(self.weights)

    def get_scatterers(self):
        """返回所有散射点的当前距离和速度列表"""
        scatterer_list = []
        for i in range(self.num_scatterers):
            s_dist = self.distance + self.r_offsets[i]
            s_vel = self.velocity + self.v_offsets[i]
            # 每个点分享总 RCS 的权重
            s_rcs = self.get_rcs() * self.weights[i]
            scatterer_list.append((s_dist, s_vel, s_rcs))
        return scatterer_list
    

# 随机化轨迹生成函数
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
    计算目标在 RD 谱上的坐标和归一化标签
    """
    # 1. 计算距离维索引 (Range Bin)
    # distance = index * range_bin -> index = distance / range_bin
    range_idx = target.distance / cfg.range_bin
    
    # 2. 计算速度维索引 (Doppler Bin)
    # velocity_seq 是从 -V_max 到 V_max 的偏移
    # index = (velocity / velocity_bin) + (N_symbols / 2)
    doppler_idx = (target.velocity / cfg.velocity_bin) + (cfg.number_symbols_per_radar_frame // 2)
    
    # 3. 归一化坐标 (常用于深度学习模型如 YOLO)
    norm_range = range_idx / cfg.number_subcarriers
    norm_doppler = doppler_idx / cfg.number_symbols_per_radar_frame
    
    return {
        "range_idx": float(range_idx),
        "doppler_idx": float(doppler_idx),
        "norm_range": float(norm_range),
        "norm_doppler": float(norm_doppler),
        "range_m": float(target.distance),
        "velocity_m_s": float(target.velocity),
        "rcs": float(target.get_rcs()) # 获取当前帧的瞬时RCS
    }

def generate_heatmap(cfg, target_list, sigma=1.5):
    heatmap = np.zeros((cfg.number_subcarriers, cfg.number_symbols_per_radar_frame))
    for target in target_list:
        info = get_label_info(cfg, target)
        r0, d0 = int(round(info['range_idx'])), int(round(info['doppler_idx']))
        
        # 在 r0, d0 附近生成高斯分布
        for i in range(max(0, r0-6), min(cfg.number_subcarriers, r0+6)):
            for j in range(max(0, d0-6), min(cfg.number_symbols_per_radar_frame, d0+6)):
                dist_sq = (i - info['range_idx'])**2 + (j - info['doppler_idx'])**2
                heatmap[i, j] = max(heatmap[i, j], np.exp(-dist_sq / (2 * sigma**2)))
    return heatmap

def get_yolo_label(cfg, target, width_bins=3, height_bins=3):
    info = get_label_info(cfg, target)
    # 假设目标在 RD 图上占据 3x3 个 bin
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
    # range_matrix = np.zeros((2,1024, 512), dtype=np.int16)
    # range_matrix[0,:,:] = data_i.T
    # range_matrix[1,:,:] = data_q.T
    iq_channel = np.fft.fft(iq_range, axis=0)

    return iq_channel


def synthesize_simtarget_plus_realbackground(cfg, targets, real_background_iq_data, ref_peak_power, target_snr_db=15.0):
    # 估计底噪
    real_background_rv_map = channel_to_rv_map(real_background_iq_data)
    noise_floor = np.median(real_background_rv_map)
    # 计算固定的幅度缩放因子
    desired_avg_target_power = noise_floor * (10 ** (target_snr_db / 10.0))
    fixed_scale_factor = np.sqrt(desired_avg_target_power / ref_peak_power)
    # 生成目标信号 (使用缩放因子)
    sim_target_radar_channel_matrix = generate_radar_channel_matrix(cfg, targets, signal_amplitude=fixed_scale_factor)
    # 验证一下当前的瞬时 SNR (它应该会在 15dB 上下波动)
    current_rv = channel_to_rv_map(sim_target_radar_channel_matrix)
    current_peak = np.max(current_rv)
    current_snr = 10 * np.log10(current_peak / noise_floor)
    # 叠加
    sim_target_plus_background_iq_data = sim_target_radar_channel_matrix + real_background_iq_data
    return sim_target_plus_background_iq_data

def synthesize_with_calibration(cfg, targets, bg_iq, ref_peak_power, target_snr_db=15.0):
    """
    带距离校正的合成函数
    """
    # 1. 转换背景到 RV 域进行校正检测
    # 注意：calibrate_rv_matrix_adaptive 原本是针对 RV 矩阵设计的
    bg_rv = channel_to_rv_map(bg_iq)
    
    # 2. 计算偏移并校正 (这里我们直接对 IQ 数据进行 roll 操作)
    # 假设背景最强点是自干扰带来的 0 距离偏移
    range_profile = np.mean(bg_rv, axis=1)
    k_offset = np.argmax(range_profile)
    # print(f"   -> Detected range offset: {k_offset} bins")
    # 计算相位坡度：exp(j * 2 * pi * k * offset / N)
    k = np.arange(cfg.number_subcarriers)[:, None] # 形状 (1024, 1)
    # 注意：k_offset 是从 IFFT 结果中找出的，方向要对应好
    phase_ramp = np.exp(1j * 2 * np.pi * k * k_offset / cfg.number_subcarriers)
    calibrated_bg_iq = bg_iq * phase_ramp
    
    # 3. 估计校正后背景的底噪
    calibrated_bg_rv = channel_to_rv_map(calibrated_bg_iq)
    noise_floor = np.median(calibrated_bg_rv)
    
    # 4. 计算目标缩放因子
    desired_avg_target_power = noise_floor * (10 ** (target_snr_db / 10.0))
    fixed_scale_factor = np.sqrt(desired_avg_target_power / ref_peak_power)
    
    # 5. 生成仿真目标并叠加
    sim_target_iq = generate_radar_channel_matrix(cfg, targets, signal_amplitude=fixed_scale_factor)
    combined_iq = sim_target_iq + calibrated_bg_iq
    
    return combined_iq, k_offset

def synthesize_simtarget_plus_gaussian_noise(cfg, targets, target_snr_db=15.0, noise_variance=1.0):
    """
    生成仿真目标叠加高斯白噪声背景。
    
    Args:
        cfg: 配置对象
        ref_peak_power: 参考目标(RCS=1)的峰值功率，用于校准目标幅度
        target_snr_db: 目标在RD图上的信噪比 (dB)
        noise_variance: 时域复数噪声的方差
        
    Returns:
        sim_target_plus_noise_iq_data: 叠加后的IQ数据
    """
    # 1. 生成时域高斯白噪声 (复数)
    # 噪声功率 P_n = E[|n|^2] = 2 * sigma^2 (如果实部虚部各为 sigma^2)
    # 这里直接控制总方差
    shape = (cfg.number_subcarriers, cfg.number_symbols_per_radar_frame)
    scale = np.sqrt(noise_variance / 2)
    noise_iq_data = scale * (np.random.randn(*shape) + 1j * np.random.randn(*shape))
    
    # 2. 估计RD图上的底噪水平 (Noise Floor)
    noise_rv_map = channel_to_rv_map(noise_iq_data)
    noise_floor = np.median(noise_rv_map)
    
    # 3. 计算目标幅度缩放因子
    desired_avg_target_power = noise_floor * (10 ** (target_snr_db / 10.0))
    # fixed_scale_factor = np.sqrt(desired_avg_target_power / ref_peak_power)

    # 4. 计算目标信号信道相应矩阵 (使用固定缩放因子，保持稳定的平均 SNR)
    sim_target_radar_channel_matrix = generate_radar_channel_matrix(cfg, targets)
    signal_peak_power = np.max(channel_to_rv_map(sim_target_radar_channel_matrix))
    scale_factor = np.sqrt(desired_avg_target_power / signal_peak_power)
    sim_target_radar_channel_matrix *= scale_factor
    
    # 5. 叠加
    sim_target_plus_noise_iq_data = sim_target_radar_channel_matrix + noise_iq_data

    
    return sim_target_plus_noise_iq_data

def ca_cfar_2d(rv_map, guard_cells=(2, 2), training_cells=(5, 5), pfa=1e-6):
    """
    对2D RV图执行CA-CFAR检测。

    Args:
        rv_map: 2D numpy array, 线性功率谱 (非dB)
        guard_cells: (g_r, g_d) 距离和多普勒方向的单侧保护单元数
        training_cells: (t_r, t_d) 距离和多普勒方向的单侧参考单元数
        pfa: 虚警概率 (Probability of False Alarm)
        
    Returns:
        detections: 2D boolean array, True表示检测到目标
        threshold_map: 2D array, 计算出的每个点的阈值
    """
    rows, cols = rv_map.shape
    g_r, g_d = guard_cells
    t_r, t_d = training_cells
    
    # 1. 计算参考单元总数 N
    # 总窗口大小: (2*t_r + 2*g_r + 1) x (2*t_d + 2*g_d + 1)
    # 保护窗口大小: (2*g_r + 1) x (2*g_d + 1)
    full_window_size = (2 * (t_r + g_r) + 1) * (2 * (t_d + g_d) + 1)
    guard_window_size = (2 * g_r + 1) * (2 * g_d + 1)
    N = full_window_size - guard_window_size
    
    # 2. 计算缩放因子 alpha
    # 对于CA-CFAR，alpha = N * (Pfa^(-1/N) - 1)
    alpha = N * (pfa**(-1/N) - 1)
    
    # 3. 使用卷积快速计算参考单元的总和
    # 创建一个卷积核，中心为0 (CUT + Guard)，周围为1 (Training)
    kernel_r = 2 * (t_r + g_r) + 1
    kernel_d = 2 * (t_d + g_d) + 1
    kernel = np.ones((kernel_r, kernel_d))
    
    # 将保护区域和CUT设为0
    guard_start_r = t_r
    guard_end_r = t_r + 2 * g_r + 1
    guard_start_d = t_d
    guard_end_d = t_d + 2 * g_d + 1
    kernel[guard_start_r:guard_end_r, guard_start_d:guard_end_d] = 0
    
    # 使用卷积计算每个点周围参考单元的功率和
    # mode='constant' 意味着边缘补0，这在雷达边缘检测中是可以接受的，或者使用 'wrap' 处理循环卷积
    noise_sum = convolve(rv_map, kernel, mode='constant', cval=0.0)
    
    # 4. 计算噪声平均值和阈值
    noise_level = noise_sum / N
    threshold_map = alpha * noise_level
    
    # 5. 检测
    detections = (rv_map > threshold_map)
    
    return detections, threshold_map


def get_channel_taps_frequency_domain(cfg, targets, symbol_idx):
    taps = np.zeros(cfg.number_subcarriers, dtype=complex)
    time_elapsed = symbol_idx * cfg.pri
    
    for target in targets:
        # 如果是分布式目标，迭代其内部所有散射点
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
        w_range = np.hamming(n_sc)[:, None] # 距离维窗
        w_doppler = np.hamming(n_sym)[None, :] # 速度维窗
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
    带加窗处理的 RV Map 转换。
    Args:
        radar_frame: 原始通道矩阵
        window_type: 'hamming', 'hann', 'blackman' 等
    """
    n_sc, n_sym = radar_frame.shape # [1024, 512]
    
    # 1. 准备窗函数
    if window_type == 'hamming':
        w_range = np.hamming(n_sc)[:, None] # 距离维窗
        w_doppler = np.hamming(n_sym)[None, :] # 速度维窗
    else:
        w_range, w_doppler = 1.0, 1.0
        
    # 2. 在进行 IFFT 之前施加窗函数
    # 距离维处理
    range_matrix = np.fft.ifft(radar_frame * w_range, axis=0)
    
    # 3. 速度维处理 (Doppler)
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
    自适应校准 RV 矩阵，消除自干扰造成的距离偏差。
    
    逻辑：
    1. 投影降维：将二维 RV 矩阵在速度（Doppler）轴方向上取平均值，得到一维的“距离剖面图”。
    2. 特征提取：在距离剖面图中寻找峰值（自干扰线）。
    3. 计算偏移：提取能量最大点对应的索引 k_offset。
    4. 循环位移：使用 numpy.roll 函数将矩阵沿距离轴移动，使 k_offset 回到 0 位置。
    """
    # 1. 投影降维 (Projection)
    range_profile = np.mean(rv_matrix, axis=1)
    
    # 2. 特征提取 & 3. 计算偏移 (Feature Extraction & Calculate Offset)
    # 假设能量最强的点是自干扰造成的“0”距离
    k_offset = np.argmax(range_profile)
    
    print(f"  - Detected Range Bias Offset: {k_offset} bins")
    
    # 4. 循环位移 (Circular Shift)
    # 将 k_offset 移动到 0，相当于向左移动 k_offset
    calibrated_matrix = np.roll(rv_matrix, -k_offset, axis=0)
    
    return calibrated_matrix

def plot_2d_range_doppler(cfg, rd_map: np.ndarray, plot_dir: Path | str,  filename: str, cbar_label='Normalized Power (dB)', title='2D Range-Doppler Map'):
    """绘制2D距离-多普勒图并保存。"""
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

def plot_cn_2d_range_doppler(cfg, rd_map: np.ndarray, plot_dir: Path | str, title : str, filename: str, cbar_label='归一化功率 (dB)'):
    """绘制2D距离-多普勒图并保存。"""
    plot_dir = Path(plot_dir)
    plot_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 6))
    im = ax.imshow(rd_map, aspect='auto', cmap='plasma', origin='lower', 
                    extent=[cfg.velocity_seq[0], cfg.velocity_seq[-1], cfg.ranges_seq[0], cfg.ranges_seq[-1]],vmin=-140, vmax=0)
    fig.colorbar(im, ax=ax, label=cbar_label)
    ax.set_title(title)
    ax.set_xlabel('速度 (m/s)')
    ax.set_ylabel('距离 (m)')
    
    save_path = plot_dir / ("cn_" + filename)
    plt.savefig(save_path, dpi=300)
    # plt.show()
    plt.close(fig)
    print(f"{filename} saved to {plot_dir}")
    
def plot_cfar_results(cfg, rv_map: np.ndarray, detections: np.ndarray, plot_dir: Path | str, title: str, filename: str, targets=None):
    """
    绘制CFAR检测结果，并可选地标记Ground Truth。

    Args:
        cfg: 配置对象
        rv_map: 2D RD谱
        detections: 检测结果布尔矩阵
        title: 标题
        filename: 保存文件名
        targets: (Optional) 目标列表，用于绘制Ground Truth
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    plot_dir = Path(plot_dir)
    # 1. 绘制原始RD图作为背景
    log_rv = nomalize_log_power_map(rv_map)
    im = ax.imshow(log_rv, aspect='auto', cmap='plasma', origin='lower',
                   extent=[cfg.velocity_seq[0], cfg.velocity_seq[-1], cfg.ranges_seq[0], cfg.ranges_seq[-1]],vmax=0,vmin=-140)
    fig.colorbar(im, ax=ax, label='Normalized Power (dB)')
    
    # 2. 绘制 CFAR 检测结果 (修改颜色为 black 黑色)
    det_indices = np.argwhere(detections)
    if len(det_indices) > 0:
        det_ranges = det_indices[:, 0] * cfg.range_bin
        det_velocities = cfg.velocity_seq[det_indices[:, 1]]
        
        # 使用青色 'x' 标记检测点，稍微调小一点 size 以免遮挡太多
        ax.scatter(det_velocities, det_ranges, c='black', marker='x', s=40, label='CFAR Detections', alpha=0.9)

    # 3. 绘制 Ground Truth (红色圆圈)
    if targets is not None:
        gt_velocities = []
        gt_ranges = []
        for target in targets:
            gt_velocities.append(target.velocity)
            gt_ranges.append(target.distance)
        
        # 使用红色圆圈标记 GT，空心圆圈 (facecolors='none')
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
    绘制CFAR检测结果，并可选地标记Ground Truth。

    Args:
        cfg: 配置对象
        rv_map: 2D RD谱
        detections: 检测结果布尔矩阵
        title: 标题
        filename: 保存文件名
        targets: (Optional) 目标列表，用于绘制Ground Truth
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # 1. 绘制原始RD图作为背景
    log_rv = nomalize_log_power_map(rv_map)
    im = ax.imshow(log_rv, aspect='auto', cmap='plasma', origin='lower',
                   extent=[cfg.velocity_seq[0], cfg.velocity_seq[-1], cfg.ranges_seq[0], cfg.ranges_seq[-1]],vmax=0,vmin=-140)
    fig.colorbar(im, ax=ax, label='归一化功率 (dB)')
    
    # 2. 绘制 CFAR 检测结果 (修改颜色为 Cyan 青色)
    det_indices = np.argwhere(detections)
    if len(det_indices) > 0:
        det_ranges = det_indices[:, 0] * cfg.range_bin
        det_velocities = cfg.velocity_seq[det_indices[:, 1]]
        
        # 使用青色 'x' 标记检测点，稍微调小一点 size 以免遮挡太多
        ax.scatter(det_velocities, det_ranges, c='black', marker='x', s=40, label='CFAR 检测结果', alpha=0.9)

    # 3. 绘制 Ground Truth (红色圆圈)
    if targets is not None:
        gt_velocities = []
        gt_ranges = []
        for target in targets:
            gt_velocities.append(target.velocity)
            gt_ranges.append(target.distance)
        
        # 使用红色圆圈标记 GT，空心圆圈 (facecolors='none')
        ax.scatter(gt_velocities, gt_ranges, edgecolors='red', facecolors='none', 
                   marker='o', s=150, linewidths=2, label='真值')

    ax.legend(loc='upper right')
    ax.set_title(title)
    ax.set_xlabel('速度 (m/s)')
    ax.set_ylabel('距离 (m)')
    
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
