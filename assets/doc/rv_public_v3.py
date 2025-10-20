import numpy as np
import matplotlib.pyplot as plt
import argparse
import os
from pathlib import Path
from tqdm import tqdm
from matplotlib.animation import FuncAnimation
from matplotlib.animation import PillowWriter
from matplotlib.colors import Normalize
from matplotlib import cm

# ==== 系统参数 ====
c = 3e8  # 光速
fc = 26e9  # 载频
lambda_v = c / fc
scs = 120e3 # 子载波间隔120kHz
T_frame = 400e-3 # 扫描周期400ms 
M = 512 # 一帧对于某一个波束的 扫描次数 也是 符号数
beam_group = 5
T_sym = T_frame / beam_group / M # 一帧中相同波束内的符号扫描间隔 (采样间隔 0.15625ms)
N = 1024 # FFT点数

range_idx = np.arange(N)            # 0,1,2,...,1023
dr = c / (2 * N * scs)
ranges_idx = range_idx * dr               # 米, shape (1024,)

velocity_idx = np.fft.fftfreq(M, d=T_sym)  # 速度轴, shape (512,)
velocity_idx = np.fft.fftshift(velocity_idx)  # 中心化
dv = lambda_v / 2
velocity_idx = velocity_idx * dv

# range_min_m, range_max_m = 0.0, 300.0    # Range of interest - 距离区间（米） 
# vel_min_m_s, vel_max_m_s = -10.0, 10.0     # Range of interest - 速度区间（m/s）

range_min_m, range_max_m = None, None    # Range of interest - 距离区间（米）
vel_min_m_s, vel_max_m_s = None, None     # Range of interest - 速度区间（m/s）

eps = 1e-12 # 避免log过小


def int16_to_float(int16_val):
    if int16_val > 32767:
        int16_val -= 65536
    return int16_val / 32767.0

def read_iq_bin_file(filename, beam_id, symbol_id, rx_id): # 读取IQ数据文件
    data_file = np.fromfile(filename, dtype='>i2')  # 读取为 int16
    symbols_idx = np.zeros(512, dtype=np.int32)
    # 对beam_id取模，得到波束组号
    group_id = beam_id // 6
    # 对beam_id / 5 取余，得到组内索引;命名与beam_id区分
    beam_id_ = beam_id % 6
    for scan_idx in range(512):
        # symbols_idx[scan_idx] = 2*512*30*rx_id +  2*512*beam_id + 2*scan_idx + symbol_id
        symbols_idx[scan_idx] = 6*512*2*2*group_id + 6*2*2*scan_idx + 2*2*beam_id_ + 2*symbol_id + rx_id
    data_i = np.zeros((512,1024), dtype=np.float32)
    data_q = np.zeros((512,1024), dtype=np.float32)
    for i in range(512):
        base_pos = symbols_idx[i]*1024 * 2
        for j in range(1024):
            data_i[i,j] = int16_to_float(data_file[base_pos+2*j])
            data_q[i,j] = int16_to_float(data_file[base_pos+2*j+1])
    return data_i + 1j*data_q

def process_bin_file(bin_file, beam_id, symbol_id, rx_id):
    """处理单个bin文件，提取指定beam和symbol的复数数据"""
    r_wave = read_iq_bin_file(bin_file, beam_id, symbol_id, rx_id)
    RV_wave = np.fft.fftshift(np.fft.fft(r_wave, axis=0), axes=0)
    # 转置
    RV_wave = RV_wave.T  # shape (1024, 512)
    return RV_wave

def get_bin_files(bin_dir):
    """获取指定目录下的所有bin文件"""
    bin_files = []
    for root, dirs, files in os.walk(bin_dir):
        for filename in files:
            if filename.endswith(".bin"):
                bin_files.append(os.path.join(root, filename))
    return bin_files



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RV图生成工具（支持智能目录生成）")
    
    # 基本参数
    parser.add_argument("--bin_dir", required=True, help="bin文件目录（将自动提取目录结构）", default="/Volumes/T9/raw_data/public/0809_180314/mmw")
    parser.add_argument("--output_dir", default="results/plots/rv_plots", help="输出目录")
    parser.add_argument("--bs_id", default="23", type=str, help="基站索引，用于目录结构")
    
    # 单个组合参数
    parser.add_argument("--rx_id", default=0, type=int, help="rx id (0或1)", choices=[0, 1])
    parser.add_argument("--beam_id", default=0, type=int, help="beam id (0-29)画单个子图；30 画 30 个子图")
    parser.add_argument("--symbol_id", default=0, type=int, help="symbol id (0或1)", choices=[0, 1])
    
    # 自动模式开关
    parser.add_argument("--auto", action="store_true", help="启用自动遍历所有组合模式")
    
    args = parser.parse_args()

    # ======== 获取bin文件列表 =========
    file_dir = os.path.join(args.bin_dir, args.bs_id)
    bin_files = [os.path.join(file_dir, f) for f in os.listdir(file_dir)]
    bin_files.sort(key=lambda p: int(os.path.splitext(os.path.basename(p))[0]))
    # print(f"bin_files: {bin_files}")

    # determine beam list
    if args.beam_id == 30:
        beams = list(range(30))
    else:
        beams = [args.beam_id]

    # ======== 用 ROI 索引 (共享) =========
    r_start, r_end = 0, ranges_idx.size
    if range_min_m is not None and range_max_m is not None:
        r_start = np.searchsorted(ranges_idx, range_min_m, side='left')
        r_end = np.searchsorted(ranges_idx, range_max_m, side='right')

    v_start, v_end = 0, velocity_idx.size
    if vel_min_m_s is not None and vel_max_m_s is not None:
        v_start = np.searchsorted(velocity_idx, vel_min_m_s, side='left')
        v_end = np.searchsorted(velocity_idx, vel_max_m_s, side='right')

    # =============================== Visualize =============================       

    if len(beams) == 1: # 单个beam的RV动画
        all_rv_matrices = [process_bin_file(f, args.beam_id, args.symbol_id, args.rx_id) for f in tqdm(bin_files, 
                                                                                                   desc=f"Processing_rx{args.rx_id}_symbol{args.symbol_id}_beam{args.beam_id}")]

    # Normalize to dB and relative
        # 求每帧的 dB（或自然对数），并取全局最大值
        db_frames = [20 * np.log10(np.abs(rv) + eps) for rv in all_rv_matrices]
        global_max = max(db.max() for db in db_frames)
        db_rel_frames = [db - global_max for db in db_frames]   # 最大值为 0，其他为 <= 0


        fig, ax = plt.subplots(figsize=(10, 6))
        # img = ax.imshow(10*np.log10(np.abs(all_rv_matrices[0])), cmap='plasma', aspect='auto')
        db0 = db_rel_frames[0][v_start:v_end, r_start:r_end]
        img = ax.imshow(20*np.log10(np.abs(all_rv_matrices[0]) + 1e-12),
                    cmap='plasma', aspect='auto', origin='lower',
                    extent=[ velocity_idx[v_start], velocity_idx[v_end-1], ranges_idx[r_start], ranges_idx[r_end-1]],
                    )   # origin='lower' [0,0]位置元素对应左下角； vmin=vmin, vmax=vmax；norm=norm。extent index替换为0，-1即可显示最大值。
        cbar = fig.colorbar(img, ax=ax, label='Magnitude (dB)')
        base_title = f'RV_rx{args.rx_id}_symbol{args.symbol_id}_beam{args.beam_id}'
        ax.set_title(base_title)
        ax.set_xlabel('Velocity (m/s)')
        ax.set_ylabel('Range (m)')
        def update(frame):
            # img.set_array(10*np.log10(np.abs(all_rv_matrices[frame])))
            img.set_data(db_rel_frames[frame][v_start:v_end, r_start:r_end])
            ax.set_title(f"{base_title} - Frame {frame+1}/{len(all_rv_matrices)}")
            return img
        
        # 新文件名格式：G{group}_RX{rx}_B{beam}_S{symbol}.gif
        gif_name = f"rx{args.rx_id}_symbol{args.symbol_id}_beam{args.beam_id}.gif"
        # 目录结构：output_dir / (bin_dir的最后两级) / bs_id / gif_name
        bin_tail_parts = Path(args.bin_dir).parts[-2:]
        bin_tail = os.path.join(*bin_tail_parts) if bin_tail_parts else ""
        output_dir = os.path.join(args.output_dir, bin_tail, args.bs_id)
        os.makedirs(output_dir, exist_ok=True)
        gif_path = os.path.join(output_dir, gif_name)
        print(f"Saving GIF to {gif_path}")
        ani = FuncAnimation(fig, update, frames=len(all_rv_matrices), interval=100, blit=False)
        ani.save(gif_path, writer=PillowWriter(fps=10))
        plt.close(fig)

    else:  # 多 beam：5 行 6 列，共 30 个子图，所有 beam 使用相同的 color scale（global_max）
        all_db_rel_per_beam = []
        print("Processing all beams ...")
        # beams = beams[:2]
        for beam in tqdm(beams, desc="beams"):
            all_rv = [process_bin_file(f, beam, args.symbol_id, args.rx_id) for f in bin_files]
            db_frames = [20 * np.log10(np.abs(rv) + eps) for rv in all_rv]
            all_db_rel_per_beam.append(db_frames)
        # 计算全局最大
        global_max = max(db.max() for beam_db in all_db_rel_per_beam for db in beam_db)
        # 转为相对并裁剪
        all_db_rel_per_beam = [[db - global_max for db in beam_db] for beam_db in all_db_rel_per_beam]
        print("overall max:", max(db.max() for beam_db in all_db_rel_per_beam for db in beam_db))

        # Normalize 到 [0,1]
        global_max = max(db.max() for beam_db in all_db_rel_per_beam for db in beam_db)  # <= 0
        global_min = min(db.min() for beam_db in all_db_rel_per_beam for db in beam_db)  # <= 0
        norm = Normalize(vmin=global_min, vmax=global_max)   # vmax=0 保证最大为 0

        n_rows, n_cols = 5, 6
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(n_cols*3.0, n_rows*2.5), constrained_layout=True)
        axes = axes.flatten()
        imgs = []
        titles = []
        for i, beam in enumerate(beams):
            ax = axes[i]
            db0 = all_db_rel_per_beam[i][0][v_start:v_end, r_start:r_end]
            img = ax.imshow(db0, cmap='plasma', aspect='auto', origin='lower',
                            extent=[velocity_idx[v_start], velocity_idx[v_end-1], ranges_idx[r_start], ranges_idx[r_end-1]]) # norm=norm是归一化的用的

            ax.set_title(f"Beam {beam}")
            ax.set_xticks([]); ax.set_yticks([])
            imgs.append(img)
            titles.append(ax)
        # 其余子图隐藏
        for j in range(len(beams), n_rows*n_cols):
            fig.delaxes(axes[j])

    # set colorbar 
        # 共享 colorbar（放在右边）
        cbar = fig.colorbar(imgs[0], ax=axes.tolist(), orientation='vertical', fraction=0.02, pad=0.01)
        cbar.set_label('Relative Magnitude (dB, max=0)')
    
        def update_all(frame):
            for i in range(len(beams)):
                imgs[i].set_data(all_db_rel_per_beam[i][frame][v_start:v_end, r_start:r_end])
                titles[i].set_title(f"Beam {beams[i]} - F{frame+1}/{len(bin_files)}")
            return imgs
    
        gif_name = f"rx{args.rx_id}_symbol{args.symbol_id}_beams_all.gif"
        bin_tail_parts = Path(args.bin_dir).parts[-2:]
        bin_tail = os.path.join(*bin_tail_parts) if bin_tail_parts else ""
        output_dir = os.path.join(args.output_dir, bin_tail, args.bs_id)
        os.makedirs(output_dir, exist_ok=True)
        gif_path = os.path.join(output_dir, gif_name)
        ani = FuncAnimation(fig, update_all, frames=len(bin_files), interval=100, blit=False)
        print(f"Saving GIF to {gif_path}")
        ani.save(gif_path, writer=PillowWriter(fps=10))
        plt.close(fig)


        
    
    