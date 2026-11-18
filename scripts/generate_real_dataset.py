"""
Real UAV Dataset Generator (YOLO Format)
----------------------------------------
This script reads real ISAC radar .bin files and GPS ground truth data.
It performs DC bias calibration, extracts highly precise trajectory labels
using `precise_rd_labeling`, and exports the frames as images and labels suitable for YOLO training.
"""

import argparse
import yaml
from pathlib import Path
import numpy as np
from tqdm import tqdm
from PIL import Image

# Core physics configurations
from cellulareye.configs.configs import ISACConfig, ScenarioConfig

# Utility functions for ETL and signal processing
from cellulareye.utils.utils import (
    load_bin_file,
    load_gt_data,
    LLA_to_ENU,
    load_iq_channels_from_bin_files,
    channels_to_rv_maps,
    calibrate_rd_maps_batch,
    precise_rd_labeling_closest,
    save_rd_image_for_yolo,
    create_yolo_label
)

def main():
    parser = argparse.ArgumentParser(description="Generate YOLO dataset from real radar data.")
    parser.add_argument('--metadata_path', type=str, default=None,
        help='Public collection metadata YAML supplying base-station coordinates; '
             'Tx/Rx selection remains controlled by --tx_bs_id and --bs_id')
    parser.add_argument("--input_dir", type=str, default="data/gt/sunny/uav/2025_12", help="Root dir containing data collections")
    parser.add_argument("--output_dir", type=str, default="datasets/real_uav", help="Base directory for output dataset")
    parser.add_argument("--bs_id", type=int, default=23, help="Base Station ID")
    parser.add_argument(
        "--tx_bs_id",
        type=int,
        default=23,
        help="Transmitter BS ID for equivalent bistatic geometry; defaults to BS23",
    )
    parser.add_argument("--beam_id", type=int, default=14, help="Radar Beam ID")
    parser.add_argument("--rx_id", type=int, default=0, help="Receiver Antenna ID")
    parser.add_argument("--symbol_id", type=int, default=0, help="OFDM Symbol ID")
    parser.add_argument("--target_type", type=str, default="uav", help="Target modality folder name")
    parser.add_argument("--width_bin", type=int, default=10, help="Label Bounding box width (in velocity bins)")
    parser.add_argument("--height_bin", type=int, default=10, help="Label Bounding box height (in range bins)")
    parser.add_argument(
        "--label_mode",
        choices=["peak_snap", "peak_snap_tracked", "peak_snap_global", "direct_path", "direct_path_blob", "direct_path_blob_global"],
        default="peak_snap",
        help="Label policy: per-frame or collection-stable peak/blob selection",
    )
    parser.add_argument("--direct_path_near_bins", type=int, default=20, help="Direct-path range gate before RTK range")
    parser.add_argument("--direct_path_far_bins", type=int, default=5, help="Direct-path range gate after RTK range")
    parser.add_argument("--direct_path_track_range_bins", type=int, default=3, help="Range gate for re-snapping to the direct-path track")
    parser.add_argument("--direct_path_track_doppler_bins", type=int, default=5, help="Doppler gate for re-snapping to the direct-path track")
    parser.add_argument("--direct_path_max_range_jump_bins", type=int, default=5, help="Maximum RTK-compensated range jump on the direct-path track")
    parser.add_argument("--direct_path_max_doppler_jump_bins", type=int, default=5, help="Maximum RTK-compensated Doppler jump on the direct-path track")
    parser.add_argument("--direct_path_confirmation_frames", type=int, default=3, help="Consecutive frames required before exporting a direct-path label")
    parser.add_argument("--direct_path_min_snr_db", type=float, default=15.0, help="Minimum SNR for direct-path candidates")
    parser.add_argument("--direct_path_fallback_snr_db", type=float, default=12.0, help="Minimum SNR for bridging a confirmed direct-path track")
    parser.add_argument("--direct_path_max_gap_frames", type=int, default=2, help="Maximum short direct-path occlusion before restarting the track")
    parser.add_argument("--direct_path_blob_min_pixels", type=int, default=4, help="Minimum connected bright pixels for a direct-path blob")
    parser.add_argument("--direct_path_blob_min_range_span", type=int, default=2, help="Minimum range-bin span for a direct-path blob")
    parser.add_argument("--direct_path_blob_min_doppler_span", type=int, default=2, help="Minimum Doppler-bin span for a direct-path blob")
    parser.add_argument("--direct_path_global_min_support_fraction", type=float, default=0.5, help="Fraction of collection frames required for a stable blob branch")
    parser.add_argument("--direct_path_global_min_consecutive_frames", type=int, default=4, help="Minimum consecutive detections for a stable blob branch")
    parser.add_argument("--direct_path_global_range_tolerance_bins", type=float, default=2.0, help="Range-residual tolerance when assigning frames to the global blob branch")
    parser.add_argument("--direct_path_global_doppler_tolerance_bins", type=float, default=4.0, help="Maximum Doppler deviation from the global blob trajectory")
    parser.add_argument("--direct_path_global_max_interpolation_gap_frames", type=int, default=3, help="Maximum gap filled from the global blob Doppler trajectory")
    parser.add_argument("--peak_snap_global_min_snr_db", type=float, default=10.0, help="Minimum SNR for peak-snap global blob candidates")
    parser.add_argument("--peak_snap_global_fallback_snr_db", type=float, default=7.0, help="Fallback SNR for peak-snap global blob recovery")
    parser.add_argument("--peak_snap_global_blob_min_pixels", type=int, default=3, help="Minimum connected bright pixels for a peak-snap global blob")
    parser.add_argument("--peak_snap_global_blob_min_range_span", type=int, default=2, help="Minimum range-bin span for a peak-snap global blob")
    parser.add_argument("--peak_snap_global_blob_min_doppler_span", type=int, default=2, help="Minimum Doppler-bin span for a peak-snap global blob")
    parser.add_argument("--peak_snap_track_range_bins", type=int, default=3, help="Range half-width for re-snapping peak-snap labels to observed peaks")
    parser.add_argument("--peak_snap_track_doppler_bins", type=int, default=4, help="Doppler half-width for re-snapping peak-snap labels to observed peaks")
    parser.add_argument('--split', choices=['train', 'val', 'test'], default='train', help='Export entire collections to this split; use separate collection lists for train/val/test')
    parser.add_argument('--max_frames', type=int, default=None, help='Optional per-collection preview limit')
    parser.add_argument('--target_id', default=None, help='Required when a collection contains multiple UAV tracks')
    args = parser.parse_args()
    if args.metadata_path and not Path(args.metadata_path).expanduser().is_file():
        parser.error('--metadata_path must point to an existing YAML file')
    if not Path(args.input_dir).is_dir():
        parser.error('--input_dir must be a directory containing collection directories')
    if args.max_frames is not None and args.max_frames < 1:
        parser.error('--max_frames must be positive')
    if not 0 <= args.beam_id < 30 or args.rx_id not in (0, 1) or args.symbol_id not in (0, 1):
        parser.error('beam must be 0..29; rx and symbol must be 0 or 1')
    if not 0 < args.width_bin <= 512 or not 0 < args.height_bin <= 1024:
        parser.error('box dimensions must fit within the RD matrix')

    # Initialize physical parameters and coordinate references
    cfg = ISACConfig()
    scenario = (ScenarioConfig.from_yaml(Path(args.metadata_path).expanduser().resolve())
                    if args.metadata_path else ScenarioConfig.from_yaml())

    # Prepare YOLO Directories
    dataset_name = f"{Path(args.output_dir).name}_bs{args.bs_id}_beam{args.beam_id}_w{args.width_bin}h{args.height_bin}"
    out_path = Path(args.output_dir).parent / dataset_name
    out_path.mkdir(parents=True, exist_ok=True)

    for split in ["train", "val", "test"]:
        (out_path / "images" / split).mkdir(parents=True, exist_ok=True)
        (out_path / "labels" / split).mkdir(parents=True, exist_ok=True)

    collections = sorted(d for d in Path(args.input_dir).iterdir() if d.is_dir())
    if not collections:
        parser.error("No collection directories found")
    total_samples = {"train": 0, "val": 0, "test": 0}
    manifest = []

    print(f"Found {len(collections)} collections. Starting generation pipeline...")

    for collection_path in tqdm(collections, desc="Processing Data Collections"):

        import json
        record_path = out_path / 'generation.json'
        if record_path.is_file():
            old_samples = json.loads(record_path.read_text()).get('samples', [])
            if any(s['collection'] == collection_path.name and s['split'] != args.split for s in old_samples):
                parser.error(f'{collection_path.name}: collection already exported to another split')
        # 1. Load Data
        bin_files, bin_ts = load_bin_file(collection_path, "mmw", str(args.bs_id))
        if not bin_files:
            continue

        gt_tracks = load_gt_data(collection_path, args.target_type)
        if not gt_tracks:
            continue

        if args.max_frames:
            bin_files, bin_ts = bin_files[:args.max_frames], bin_ts[:args.max_frames]
        if args.target_id is None and len(gt_tracks) > 1:
            parser.error(f'{collection_path.name}: multiple UAV tracks; select --target_id')
        target_id = args.target_id or next(iter(gt_tracks))
        if target_id not in gt_tracks:
            parser.error(f'{collection_path.name}: target_id not found: {target_id}')
        gt_ts, coords, _ = gt_tracks[target_id]
        if len(gt_ts) < 2:
            continue

        # 2. GT Coordinates Alignment
        gt_enu, bs_enu_dict = LLA_to_ENU(scenario, coords)
        bs_enu = bs_enu_dict[str(args.bs_id)]
        tx_bs_enu = None
        if args.tx_bs_id is not None:
            tx_key = str(args.tx_bs_id)
            if tx_key not in bs_enu_dict:
                parser.error(f"--tx_bs_id {args.tx_bs_id} is not defined in the scenario configuration")
            tx_bs_enu = bs_enu_dict[tx_key]

        # 3. Radar Map Formulation & DC Calibration
        iq_channels = load_iq_channels_from_bin_files(bin_files, args.beam_id, args.symbol_id, args.rx_id)
        rd_maps = channels_to_rv_maps(iq_channels, mode="log_power")
        calibrated_maps, _ = calibrate_rd_maps_batch(rd_maps)

        # 4. Extract High-Precision Indices via the selected label policy
        r_idx, d_idx, _, _ = precise_rd_labeling_closest(
            rd_maps=calibrated_maps,
            gt_enu=gt_enu,
            gt_timestamps=gt_ts,
            bin_timestamps=bin_ts,
            bs_enu=bs_enu,
            tx_bs_enu=tx_bs_enu,
            cfg=cfg,
            label_mode=args.label_mode,
            direct_path_near_bins=args.direct_path_near_bins,
            direct_path_far_bins=args.direct_path_far_bins,
            direct_path_track_range_bins=args.direct_path_track_range_bins,
            direct_path_track_doppler_bins=args.direct_path_track_doppler_bins,
            direct_path_max_range_jump_bins=args.direct_path_max_range_jump_bins,
            direct_path_max_doppler_jump_bins=args.direct_path_max_doppler_jump_bins,
            direct_path_confirmation_frames=args.direct_path_confirmation_frames,
            direct_path_min_snr_db=args.direct_path_min_snr_db,
            direct_path_fallback_snr_db=args.direct_path_fallback_snr_db,
            direct_path_max_gap_frames=args.direct_path_max_gap_frames,
            direct_path_blob_min_pixels=args.direct_path_blob_min_pixels,
            direct_path_blob_min_range_span=args.direct_path_blob_min_range_span,
            direct_path_blob_min_doppler_span=args.direct_path_blob_min_doppler_span,
            direct_path_global_min_support_fraction=args.direct_path_global_min_support_fraction,
            direct_path_global_min_consecutive_frames=args.direct_path_global_min_consecutive_frames,
            direct_path_global_range_tolerance_bins=args.direct_path_global_range_tolerance_bins,
            direct_path_global_doppler_tolerance_bins=args.direct_path_global_doppler_tolerance_bins,
            direct_path_global_max_interpolation_gap_frames=args.direct_path_global_max_interpolation_gap_frames,
            peak_snap_global_min_snr_db=args.peak_snap_global_min_snr_db,
            peak_snap_global_fallback_snr_db=args.peak_snap_global_fallback_snr_db,
            peak_snap_global_blob_min_pixels=args.peak_snap_global_blob_min_pixels,
            peak_snap_global_blob_min_range_span=args.peak_snap_global_blob_min_range_span,
            peak_snap_global_blob_min_doppler_span=args.peak_snap_global_blob_min_doppler_span,
            peak_snap_track_range_bins=args.peak_snap_track_range_bins,
            peak_snap_track_doppler_bins=args.peak_snap_track_doppler_bins,
        )

        # 5. Iteratively Split & Save valid frames
        num_frames = len(bin_ts)
        # Keep every collection in one explicit split.

        for i in range(num_frames):
            if np.isnan(r_idx[i]) or np.isnan(d_idx[i]):
                continue

            split = args.split
            frame_name = f"{collection_path.name}_{bin_ts[i].strftime('%Y_%m_%d_%H_%M_%S_%f')}"

            img_file = out_path / "images" / split / f"{frame_name}.png"
            lbl_file = out_path / "labels" / split / f"{frame_name}.txt"

            # Save Image and Label
            save_rd_image_for_yolo(calibrated_maps[i], img_file)

            yolo_box_str = create_yolo_label(r_idx[i], d_idx[i], args.width_bin, args.height_bin, cfg)
            with open(lbl_file, "w") as f:
                f.write(yolo_box_str)

            manifest.append(dict(collection=collection_path.name, source_file=bin_files[i].name, timestamp_utc=bin_ts[i].isoformat(), target_id=target_id, split=split, image=str(img_file.relative_to(out_path)), label=str(lbl_file.relative_to(out_path)), range_bin=float(r_idx[i]), doppler_bin=float(d_idx[i])))
            total_samples[split] += 1

    import json, sys
    record_path = out_path / 'generation.json'
    previous = json.loads(record_path.read_text()) if record_path.is_file() else {}
    previous_samples = previous.get('samples', [])
    current_collections = {sample['collection'] for sample in manifest}
    if any(sample['collection'] in current_collections and sample['split'] != args.split for sample in previous_samples):
        parser.error('A selected collection already belongs to another split in this output dataset')
    merged = {sample['image']: sample for sample in previous_samples}
    merged.update({sample['image']: sample for sample in manifest})
    counts = {split: sum(sample['split'] == split for sample in merged.values()) for split in ['train', 'val', 'test']}
    runs = previous.get('runs', []) + [dict(command=sys.argv, config=vars(args), counts=total_samples, deterministic=True)]
    record_path.write_text(json.dumps(dict(runs=runs, counts=counts, samples=list(merged.values())), indent=2))
    if not manifest:
        parser.error('No valid labels exported; inspect time alignment, collection visibility and label settings')
    # 6. Generate configuration YAML file dynamically
    yolo_yaml = {
        "path": str(out_path.resolve()),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": {0: args.target_type}
    }
    yaml_path = out_path / "dataset.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(yolo_yaml, f, sort_keys=False)

    print(f"\n" + "="*50)
    print(f"Dataset generated cleanly and completely!")
    print(f"Saved at: {str(out_path.resolve())}")
    print(f"Training Samples : {total_samples['train']}")
    print(f"Validation Samples : {total_samples['val']}")
    print(f"Total Artifacts : {sum(total_samples.values())}")
    print("="*50)

if __name__ == "__main__":
    main()
