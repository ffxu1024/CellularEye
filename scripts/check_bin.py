"""Visualize measured RD frames and UAV flight/collection windows."""
import argparse
from pathlib import Path
import matplotlib.pyplot as plt
from cellulareye.configs.configs import ISACConfig, PlotConfig, ScenarioConfig
from cellulareye.utils.utils import (load_bin_file, load_gt_data, LLA_to_ENU,
    load_iq_channels_from_bin_files, channels_to_rv_maps,
    calibrate_rd_maps_batch, check_collection_and_gt_overlap, coarse_rd_labeling)
from cellulareye.utils.plot import (animate_rd_maps, plot_gt_3d_trajectory,
    animate_gt_3d_trajectory)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--metadata_path', type=str, default=None,
        help='Public collection metadata YAML supplying base-station coordinates; '
             'Tx/Rx selection remains controlled by --tx_bs_id and --bs_id')
    p.add_argument('--collection_path', required=True)
    p.add_argument('--modality', choices=['mmw'], default='mmw')
    p.add_argument('--bs_id', type=int, choices=[21, 22, 23, 24], default=23)
    p.add_argument('--tx_bs_id', type=int, choices=[21, 22, 23, 24], default=23)
    p.add_argument('--beam_id', type=int, choices=range(30), default=14)
    p.add_argument('--rx_id', type=int, choices=[0, 1], default=0)
    p.add_argument('--symbol_id', type=int, choices=[0, 1], default=0)
    p.add_argument('--target_type', choices=['uav'], default='uav')
    p.add_argument('--output_dir', default='results/plots')
    p.add_argument('--max_frames', type=int, default=None)
    p.add_argument('--frame_start', type=int, default=0,
                   help='Zero-based first frame in the sorted recording list')
    p.add_argument('--box_width_bins', type=int, default=30)
    p.add_argument('--box_height_bins', type=int, default=30)
    p.add_argument('--trajectory_animation', action='store_true')
    a = p.parse_args()
    if a.metadata_path and not Path(a.metadata_path).expanduser().is_file():
        p.error('--metadata_path must point to an existing YAML file')
    if a.max_frames is not None and a.max_frames < 1:
        p.error('--max_frames must be positive')
    if a.frame_start < 0:
        p.error('--frame_start must be non-negative')
    if not 0 < a.box_width_bins <= 512 or not 0 < a.box_height_bins <= 1024:
        p.error('Box dimensions must fit within the RD map')
    files, times = load_bin_file(a.collection_path, a.modality, str(a.bs_id))
    if not files:
        p.error('No .bin files found for the selected collection and receiver')
    if a.frame_start >= len(files):
        p.error('--frame_start is outside the selected recording')
    files, times = files[a.frame_start:], times[a.frame_start:]
    if a.max_frames:
        files, times = files[:a.max_frames], times[:a.max_frames]
    cfg = ISACConfig()
    pcfg = PlotConfig(save_dir=a.output_dir)
    rd, _ = calibrate_rd_maps_batch(channels_to_rv_maps(
        load_iq_channels_from_bin_files(files, a.beam_id, a.symbol_id, a.rx_id)))
    tracks = load_gt_data(a.collection_path, a.target_type)
    centers = []
    if tracks:
        scenario = (ScenarioConfig.from_yaml(Path(a.metadata_path).expanduser().resolve())
                    if a.metadata_path else ScenarioConfig.from_yaml())
        for target, (gt_times, coords, _) in tracks.items():
            enu, stations = LLA_to_ENU(scenario, coords)
            overlap = check_collection_and_gt_overlap(times, gt_times)
            plot_gt_3d_trajectory(enu, gt_times, overlap, stations, pcfg, target)
            if a.trajectory_animation:
                animate_gt_3d_trajectory(enu, gt_times, overlap, stations, pcfg, target)
            if len(gt_times) >= 2:
                centers.append(coarse_rd_labeling(enu, gt_times, times,
                    stations[str(a.bs_id)], cfg, stations[str(a.tx_bs_id)]))
    animate_rd_maps(rd, times, cfg, pcfg, a, save_name='geometric_reference',
        precise_indices=centers,
        box_dims_bins=(a.box_width_bins, a.box_height_bins))
    plt.close('all')


if __name__ == '__main__':
    main()
