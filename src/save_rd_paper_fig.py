import numpy as np
import matplotlib.pyplot as plt
import argparse
import os
import re
from pathlib import Path

# ================= Matplotlib Global Settings for Academic Papers =================
# Uncomment the following to enable specific font settings for papers
# plt.rcParams.update({
#     'font.family': 'serif',
#     'font.size': 14,
#     'axes.labelsize': 16,
#     'xtick.labelsize': 14,
#     'ytick.labelsize': 14,
#     'legend.fontsize': 14,
#     'figure.titlesize': 16
# })
# =====================================================================

class Config:
    def __init__(self):
        # OFDM Parameters
        self.c = 3e8  
        self.base_scs = 15e3  
        self.u = 3  
        self.fc = 25.6e9  
        self.subcarrier_spacing = self.base_scs * 2**self.u  
        self.number_subcarriers = 1024 
        self.number_cp = self.number_subcarriers   
        self.ofdm_symbols_duration = 1 / self.subcarrier_spacing  
        self.Ts = 1 / (self.number_subcarriers * self.subcarrier_spacing)  
        self.fs = self.number_subcarriers * self.subcarrier_spacing  
        self.zc_u = 25  

        # Radar frame parameters
        self.frame_period = 400e-3  
        self.number_symbols_per_radar_frame = 512
        self.pri = 8.92e-6 * 2 * 6 
        self.cpi = self.number_symbols_per_radar_frame * self.pri

        # Resolution and unambiguous range/velocity
        self.delay_bin = 1 / (self.number_subcarriers * self.subcarrier_spacing)
        self.range_bin = self.c * self.delay_bin / 2
        self.doppler_bin = 1 / self.cpi
        self.velocity_bin = self.doppler_bin * self.c / (2 * self.fc)

        # Plotting parameters
        self.ranges_seq = np.arange(self.number_subcarriers) * self.range_bin
        self.velocity_seq = np.arange(-self.number_symbols_per_radar_frame // 2, self.number_symbols_per_radar_frame // 2) * self.velocity_bin

cfg = Config()
eps = 1e-12

def int16_to_float(int16_val):
    if int16_val > 32767:
        int16_val -= 65536
    return int16_val / 32767.0

def read_iq_bin_file(filename, beam_id, symbol_id, rx_id):
    data_file = np.fromfile(filename, dtype='>i2')  
    symbols_idx = np.zeros(512, dtype=np.int32)
    group_id = beam_id // 6
    beam_id_ = beam_id % 6
    
    for scan_idx in range(512):
        symbols_idx[scan_idx] = 6*512*2*2*group_id + 6*2*2*scan_idx + 2*2*beam_id_ + 2*symbol_id + rx_id
        
    data_i = np.zeros((512,1024), dtype=np.float32)
    data_q = np.zeros((512,1024), dtype=np.float32)
    for i in range(512):
        base_pos = symbols_idx[i]*1024 * 2
        for j in range(1024):
            data_i[i,j] = int16_to_float(data_file[base_pos+2*j])
            data_q[i,j] = int16_to_float(data_file[base_pos+2*j+1])
            # data_i[i,j] = data_file[base_pos+2*j]
            # data_q[i,j] = data_file[base_pos+2*j+1]
    return data_i + 1j*data_q

def process_bin_file(bin_file, beam_id, symbol_id, rx_id):
    r_wave = read_iq_bin_file(bin_file, beam_id, symbol_id, rx_id)
    r_wave = r_wave.T 
    RV_wave = np.fft.fftshift(np.fft.ifft(r_wave, axis=1), axes=1)
    return RV_wave

def extract_timestamp(path_str):
    """Infer timestamp directory from path， [Translated]  2025_10_18_12_00"""
    parts = Path(path_str).parts
    # Match timestamp folder features like
    pattern = re.compile(r"^20\d{2}_\d{2}_\d{2}")
    for part in parts:
        if pattern.search(part):
            return part
    return "UnknownTime"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="High-res single-frame RV map extraction tool (for paper and open source)")
    
    # 
    parser.add_argument("--bin_dir", required=True, help="root directory for bin files", default="data/public_data/2025_10_18_00_00/mmw")
    parser.add_argument("--bs_id", default="23", type=str, help="Base Station index")
    parser.add_argument("--rx_id", default=0, type=int, help="rx id (0 [Translated] 1)")
    parser.add_argument("--beam_id", default=3, type=int, help="beam id (0-29is main beam, set to 30 to draw all 30 beams at once)")
    parser.add_argument("--symbol_id", default=0, type=int, help="symbol id (0 [Translated] 1)")
    
    # 
    parser.add_argument("--frame_id", default=0, type=int, help="Frame index to process (0-based list index)")
    parser.add_argument("--ext", default="pdf", type=str, choices=["pdf", "svg", "eps", "png"], help="Saved image format, recommend pdf/svg (vector graphics)")
    parser.add_argument("--output_dir", default="results/plots/paper_figs", help="Output directory for high-res images")
    
    args = parser.parse_args()

    # --------------- 1. Validate and extract target file ---------------
    file_dir = os.path.join(args.bin_dir, args.bs_id)
    if not os.path.exists(file_dir):
        raise FileNotFoundError(f"Directory does not exist: {file_dir}")
        
    bin_files = [os.path.join(file_dir, f) for f in os.listdir(file_dir) if f.endswith('.bin')]
    bin_files.sort(key=lambda p: int(os.path.splitext(os.path.basename(p))[0]))
    
    if len(bin_files) == 0:
        raise ValueError(f"No .bin files found in this directory: {file_dir}")
    if args.frame_id >= len(bin_files) or args.frame_id < -len(bin_files):
        raise IndexError(f"Specified frame_id out of range.")

    target_file = bin_files[args.frame_id]
    timestamp_str = extract_timestamp(args.bin_dir)
    print(f"[{timestamp_str}] Extracting frame {args.frame_id} from file: {target_file}")

    # Determine the list of Beams to process
    beams = list(range(30)) if args.beam_id == 30 else [args.beam_id]

    # --------------- 2. Data processing ---------------
    all_rv_matrices = []
    for beam in beams:
        rv_matrix = process_bin_file(target_file, beam, args.symbol_id, args.rx_id)
        all_rv_matrices.append(rv_matrix)
    
    # Convert all to absolute dB
    db_frames = [20 * np.log10(np.abs(rv) + eps) for rv in all_rv_matrices]


    # --------------- 3. Plotting and saving ---------------
    vmin, vmax = -140, 0
    cmap = 'jet'  # Adjust colormap here

    # Define output file path
    os.makedirs(args.output_dir, exist_ok=True)
    beam_name = "ALL30" if args.beam_id == 30 else f"B{args.beam_id}"
    out_filename = f"RV_{timestamp_str}_BS{args.bs_id}_{beam_name}_F{args.frame_id}_RX{args.rx_id}_S{args.symbol_id}.{args.ext}"
    out_filepath = os.path.join(args.output_dir, out_filename)

    if len(beams) == 1:
        # Single beam mode
        fig, ax = plt.subplots(figsize=(6, 5)) 
        img = ax.imshow(db_frames[0], cmap=cmap, aspect='auto', origin='lower',
                        extent=[cfg.velocity_seq[0], cfg.velocity_seq[-1], cfg.ranges_seq[0], cfg.ranges_seq[-1]],
                        vmin=vmin, vmax=vmax)  

        cbar = fig.colorbar(img, ax=ax)
        cbar.set_label('Magnitude (dB)')
        ax.set_xlabel('Velocity (m/s)')
        ax.set_ylabel('Range (m)')
    else:
        # 30 beam grid mode (56)
        n_rows, n_cols = 5, 6
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(n_cols*2.5, n_rows*2.0), constrained_layout=True)
        axes = axes.flatten()
        
        for i, beam in enumerate(beams):
            ax = axes[i]
            img = ax.imshow(db_frames[i], cmap=cmap, aspect='auto', origin='lower',
                            extent=[cfg.velocity_seq[0], cfg.velocity_seq[-1], cfg.ranges_seq[0], cfg.ranges_seq[-1]],
                            vmin=vmin, vmax=vmax)
            ax.set_title(f"Beam {beam}", fontsize=12)
            # Hide inner beam axes to make the plot clean for papers
            ax.set_xticks([])
            ax.set_yticks([])

        # Share a colorbar on the right
        cbar = fig.colorbar(img, ax=axes.tolist(), orientation='vertical', fraction=0.015, pad=0.01)
        cbar.set_label('Magnitude (dB)')

    # Save file (bbox_inches='tight' ensures no border cutoff)
    plt.savefig(out_filepath, format=args.ext, dpi=300, bbox_inches='tight', transparent=False)
    print(f"✅ High-res save complete: {out_filepath}")
    
    plt.close(fig)