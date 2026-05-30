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
from concurrent.futures import ProcessPoolExecutor
import functools

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
                # [z, y, x] -> ENU; x is zero when pointing to the east.
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

cfg = Config()


eps = 1e-12  # Avoid taking the log of values that are too small.

cfg = Config()

# print(cfg.velocity_seq )
# print(velocity_idx)
# compare cfg.velocity_seq & velocity_idx

def int16_to_float(int16_val):
    if int16_val > 32767:
        int16_val -= 65536
    return int16_val / 32767.0

def read_iq_bin_file(filename, beam_id, symbol_id, rx_id):  # Read the IQ data file.
    data_file = np.fromfile(filename, dtype='>i2')  # Read as int16.
    symbols_idx = np.zeros(512, dtype=np.int32)
    # Take beam_id modulo 6 to obtain the beam group index.
    group_id = beam_id // 6
    # Take the remainder of beam_id modulo 6 to get the intra-group index; keep it distinct from beam_id.
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
    """Process a single bin file and extract the complex data for the given beam and symbol."""
    r_wave = read_iq_bin_file(bin_file, beam_id, symbol_id, rx_id)
    r_wave = r_wave.T 
    RV_wave = np.fft.fftshift(np.fft.ifft(r_wave, axis=1), axes=1)
    # Transpose; resulting shape: (1024, 512)
    return RV_wave

def get_bin_files(bin_dir):
    """Get all bin files under the specified directory."""
    bin_files = []
    for root, dirs, files in os.walk(bin_dir):
        for filename in files:
            if filename.endswith(".bin"):
                bin_files.append(os.path.join(root, filename))
    return bin_files

# ============ Parallel processing helpers ============
def _process_single_file_wrapper(args):
    """Parallel wrapper for single-beam mode."""
    f, beam_id, symbol_id, rx_id = args
    return process_bin_file(f, beam_id, symbol_id, rx_id)

def _process_beam_sequence_wrapper(args):
    """Parallel wrapper for multi-beam mode: process all files for one beam and compute dB."""
    beam_id, bin_files, symbol_id, rx_id, epsilon = args
    
    # Process all files for this beam.
    rv_list = [process_bin_file(f, beam_id, symbol_id, rx_id) for f in bin_files]
    
    # Compute dB directly in the worker process to reduce main-process compute and transfer overhead.
    # Note: this computes absolute dB; normalization should be done in the main process after
    # collecting the maximum value across all beams.
    db_frames = [20 * np.log10(np.abs(rv) + epsilon) for rv in rv_list]
    
    return db_frames
# ========================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RV map generation tool (parallel-accelerated version)")
    
    # Basic parameters
    parser.add_argument("--bin_dir", required=True, help="Directory containing bin files (the directory structure will be inferred automatically)", default="data/public_data/2025_10_18_00_00/mmw")
    parser.add_argument("--output_dir", default="results/plots/rv_plots", help="Output directory")
    parser.add_argument("--bs_id", default="23", type=str, help="Base-station index used for the directory structure")
    
    # Single-combination parameters
    parser.add_argument("--rx_id", default=0, type=int, help="RX ID (0 or 1)", choices=[0, 1])
    parser.add_argument("--beam_id", default=0, type=int, help="Beam ID (0-29) renders a single subplot; 30 renders 30 subplots")
    parser.add_argument("--symbol_id", default=0, type=int, help="Symbol ID (0 or 1)", choices=[0, 1])
    
    # Automatic mode switch
    parser.add_argument("--auto", action="store_true", help="Enable automatic traversal of all combinations")
    
    # Parallel parameters
    parser.add_argument("--workers", type=int, default=None, help="Number of worker processes; defaults to the number of CPU cores")

    args = parser.parse_args()

    # ======== Get the list of bin files =========
    file_dir = os.path.join(args.bin_dir, args.bs_id)
    bin_files = [os.path.join(file_dir, f) for f in os.listdir(file_dir)]
    bin_files.sort(key=lambda p: int(os.path.splitext(os.path.basename(p))[0]))
    # print(f"bin_files: {bin_files}")

    # determine beam list
    if args.beam_id == 30:
        beams = list(range(30))
    else:
        beams = [args.beam_id]


    # =============================== Visualize =============================       

    if len(beams) == 1: # RV animation for a single beam.
        print(f"Processing single beam {args.beam_id} with parallel execution...")
        
        # Prepare task arguments.
        tasks = [(f, args.beam_id, args.symbol_id, args.rx_id) for f in bin_files]
        
        # Execute in parallel.
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            all_rv_matrices = list(tqdm(
                executor.map(_process_single_file_wrapper, tasks), 
                total=len(tasks),
                desc=f"Processing_rx{args.rx_id}_symbol{args.symbol_id}_beam{args.beam_id}"
            ))

        # Normalize to dB and relative
        # Compute the dB for each frame (or natural log) and take the global maximum.
        db_frames = [20 * np.log10(np.abs(rv) + eps) for rv in all_rv_matrices]
        global_max = max(db.max() for db in db_frames)
        db_rel_frames = [db - global_max for db in db_frames]   # The maximum is 0; the rest are <= 0.


        fig, ax = plt.subplots(figsize=(10, 20))
        # img = ax.imshow(10*np.log10(np.abs(all_rv_matrices[0])), cmap='plasma', aspect='auto')
        db0 = db_rel_frames[0]
        # db0 = db_rel_frames[0]
        img = ax.imshow(db0,
                    cmap='plasma', aspect='auto', origin='lower',
                    extent=[cfg.velocity_seq[0], cfg.velocity_seq[-1], cfg.ranges_seq[0], cfg.ranges_seq[-1]],vmin=-140, vmax=0)  
        cbar = fig.colorbar(img, ax=ax, label='Magnitude (dB)')
        base_title = f'RV_rx{args.rx_id}_symbol{args.symbol_id}_beam{args.beam_id}'
        ax.set_title(base_title)
        ax.set_xlabel('Velocity (m/s)')
        ax.set_ylabel('Range (m)')
        def update(frame):
            # img.set_array(10*np.log10(np.abs(all_rv_matrices[frame])))
            img.set_data(db_rel_frames[frame])
            ax.set_title(f"{base_title} - Frame {frame+1}/{len(all_rv_matrices)}")
            return img
        
        # New filename format: G{group}_RX{rx}_B{beam}_S{symbol}.gif
        gif_name = f"rx{args.rx_id}_symbol{args.symbol_id}_beam{args.beam_id}.gif"
        # Directory structure: output_dir / (last two levels of bin_dir) / bs_id / gif_name
        bin_tail_parts = Path(args.bin_dir).parts[-2:]
        bin_tail = os.path.join(*bin_tail_parts) if bin_tail_parts else ""
        output_dir = os.path.join(args.output_dir, bin_tail, args.bs_id)
        os.makedirs(output_dir, exist_ok=True)
        gif_path = os.path.join(output_dir, gif_name)
        print(f"Saving GIF to {gif_path}")
        ani = FuncAnimation(fig, update, frames=len(all_rv_matrices), interval=100, blit=False)
        ani.save(gif_path, writer=PillowWriter(fps=10))
        plt.close(fig)

    else:  # Multi-beam: 5 rows x 6 columns, 30 subplots total.
        print("Processing all beams in parallel ...")
        
        # Prepare tasks: each task handles all files for one beam.
        tasks = [(beam, bin_files, args.symbol_id, args.rx_id, eps) for beam in beams]
        
        all_db_rel_per_beam = []
        
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            # map returns results in the same order as tasks, so the order matches beam 0, 1, 2...
            results = list(tqdm(
                executor.map(_process_beam_sequence_wrapper, tasks),
                total=len(tasks),
                desc="Beams Parallel Processing"
            ))
            all_db_rel_per_beam = results

        # Compute the global maximum.
        global_max = max(db.max() for beam_db in all_db_rel_per_beam for db in beam_db)
        # Convert to relative values and clip.
        all_db_rel_per_beam = [[db - global_max for db in beam_db] for beam_db in all_db_rel_per_beam]
        print("overall max:", max(db.max() for beam_db in all_db_rel_per_beam for db in beam_db))

        # Normalize to [0, 1].
        global_max = max(db.max() for beam_db in all_db_rel_per_beam for db in beam_db)  # <= 0
        global_min = min(db.min() for beam_db in all_db_rel_per_beam for db in beam_db)  # <= 0
        norm = Normalize(vmin=global_min, vmax=global_max)   # vmax=0 ensures the maximum is 0.

        n_rows, n_cols = 5, 6
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(n_cols*3.0, n_rows*2.5), constrained_layout=True)
        axes = axes.flatten()
        imgs = []
        titles = []
        for i, beam in enumerate(beams):
            ax = axes[i]
            # db0 = all_db_rel_per_beam[i][0][v_start:v_end, r_start:r_end]
            db0 = all_db_rel_per_beam[i][0]
            img = ax.imshow(db0, cmap='plasma', aspect='auto', origin='lower',
                            extent=[cfg.velocity_seq[0], cfg.velocity_seq[-1], cfg.ranges_seq[0], cfg.ranges_seq[-1]]
                            , vmin=-140, vmax=0)  # norm=norm is used for normalization.

            ax.set_title(f"Beam {beam}")
            ax.set_xticks([]); ax.set_yticks([])
            imgs.append(img)
            titles.append(ax)
        # Hide the remaining subplots.
        for j in range(len(beams), n_rows*n_cols):
            fig.delaxes(axes[j])

    # set colorbar 
        # Shared colorbar (placed on the right).
        cbar = fig.colorbar(imgs[0], ax=axes.tolist(), orientation='vertical', fraction=0.02, pad=0.01)
        cbar.set_label('Relative Magnitude (dB, max=0)')
    
        def update_all(frame):
            for i in range(len(beams)):
                imgs[i].set_data(all_db_rel_per_beam[i][frame])
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