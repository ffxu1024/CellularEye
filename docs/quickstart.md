# Get started

Choose the workflow that matches your task:

| I want to… | Start here |
| :--- | :--- |
| Use prepared detection images and labels | [Benchmark](benchmark.md) |
| Render an RD figure from a raw collection | [RD visualization](#rd-visualization) |
| Inspect flight trajectories and collection windows | [Trajectory and collection-window visualization](#trajectory-and-collection-window-visualization) |
| Generate a dataset from my selected real collections | [Real-data generation](#real-data-generation) |

## Installation

```bash
git clone https://github.com/ffxu1024/CellularEye.git
cd CellularEye
conda create -n cellulareye python=3.11
conda activate cellulareye
python -m pip install -r requirements-tested.txt
python -m pip install -e .
```

`requirements-tested.txt` records the dependency versions tested in a clean Python 3.11 environment. The editable installation installs this toolkit from `pyproject.toml`. The toolkit requires Python 3.11 or newer. No GPU is required for these tools.

## RD visualization

The figure script accepts a raw collection's `mmw` directory:

```bash
python src/save_rd_paper_fig.py \
  --bin_dir /path/to/2025_12_09_12_00/mmw \
  --bs_id 23 \
  --beam_id 14 \
  --rx_id 0 \
  --symbol_id 0 \
  --frame_id 0 \
  --output_dir results/rd
```

Select `--beam_id 30` in this figure script to render all 30 beams. This value is a visualization option, not a valid beam index for the binary reader. Frames are selected by their zero-based position in the sorted file list.

See the [visual gallery](index.html#gallery) for selected continuous RD intervals and full-flight collection-window animations.

## Trajectory and collection-window visualization

The `check_bin.py` workflow renders RD sequences and a 3D UAV trajectory with the RF collection segment highlighted. Collections without UAV records can still be used for RD animation.

From the repository root, run:

```bash
python scripts/check_bin.py \
  --collection_path /path/to/2025_12_09_12_00 \
  --modality mmw \
  --bs_id 23 \
  --beam_id 14 \
  --rx_id 0 \
  --symbol_id 0 \
  --trajectory_animation \
  --max_frames 20
```

To reproduce the sunny gallery interval, select the corresponding collection and display window:

```bash
python scripts/check_bin.py \
  --collection_path /path/to/2026_09_05_02_30 \
  --bs_id 23 --beam_id 14 \
  --frame_start 24 --max_frames 27 \
  --box_width_bins 40 --box_height_bins 40 \
  --output_dir results/gallery_bs23
```

Use `--bs_id 22` for the companion receiver. The rainy gallery uses collection `2026_09_18_05_15`, `--frame_start 22`, and `--max_frames 30`. Omit frame limits to render the complete recording.

The workflow writes plots and RD GIFs under `results/plots/`. Use `--trajectory_animation` to save the UAV trajectory GIF and `--max_frames` to limit the preview. Omit the latter to process all frames; this can require substantial memory for long collections. Change the destination with `--output_dir`.

## Real-data generation

The real-data generator uses the position-assisted annotation workflow: associate UAV records with radio timestamps, compute geometric references, refine centers using local echoes, and export RD images and YOLO labels.

Export real-data images and labels with:

```bash
python scripts/generate_real_dataset.py \
  --input_dir /path/to/collection_parent \
  --output_dir datasets/real_uav \
  --bs_id 23 \
  --beam_id 14 \
  --rx_id 0 \
  --symbol_id 0 \
  --width_bin 30 \
  --height_bin 30 \
  --split train \
  --max_frames 20
```

`--input_dir` contains collection directories. All selected collections are exported to `--split` (`train`, `val`, or `test`), without splitting adjacent frames automatically. Use separate collection groups for training, validation, and testing. The output directory gains a `_bs23_beam14_w30h30`-style suffix and contains `dataset.yaml` plus `generation.json` with the invocation, settings, sample origins, and counts. Transmitter BS23 is the default; change it explicitly with `--tx_bs_id` when appropriate. For multi-UAV records, select `--target_id`. Box dimensions are measured in RD bins. Position-assisted boxes are derived detection annotations; their dimensions are configurable.

RF timestamps in the current release use TAI and RTK records use UTC; their alignment uses a 37-second subtraction. The reader retains the existing zero-offset exception for January–May 2026 legacy files; use actual timestamp provenance when handling those older captures. Station geometry and transmitter/receiver roles must also match the selected collection.

For the fixed benchmark, use the released images, labels, and split manifests. Running a configurable generator on arbitrary collections does not reproduce the benchmark automatically.

## Preview generated labels

```bash
python src/visualize_real_dataset.py \
  --input_dir datasets/real_uav_bs23_beam14_w30h30 \
  --output_dir results/labels
```

This saves an image grid and an annotated GIF. Images are paired with labels by split and filename, including datasets with fewer than eight images.
