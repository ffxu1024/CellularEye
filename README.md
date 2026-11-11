<div align="center">

# CellularEye

### ISAC in Practice: The CellularEye Dataset

Real-world cellular sensing data for noncooperative UAV research

[![Guide](https://img.shields.io/badge/docs-quick_start-1f77b4?style=flat-square)](#quick-start)
[![PML](https://img.shields.io/badge/data-PML_portal-2ca02c?style=flat-square)](http://pmldatanet.com.cn/dataapp/multimodal)
[![ScienceDB](https://img.shields.io/badge/ScienceDB-under_review-ff7f0e?style=flat-square)](#downloads)

[PML Data Portal](http://pmldatanet.com.cn/dataapp/multimodal) · [ScienceDB](https://doi.org/10.57760/sciencedb.018bv) · [Gallery](#visual-gallery) · [Testbed](#testbed) · [Parameters](#mmwave-signal-and-radar-parameters) · [Benchmark](#benchmark) · [Quick Start](#quick-start) · [Issues](https://github.com/ffxu1024/CellularEye/issues)

</div>

<p align="center">
  <img src="assets/img/multi-modal-en.png" alt="CellularEye multimodal acquisition platform" width="880">
</p>

**CellularEye** is a real-world dataset acquired using OFDM reference signals on experimental base stations for noncooperative UAV sensing. It combines complex-valued channel measurements with UAV flight records, RGB/infrared video, and weather observations across receiving sites, beams, trajectories, acquisition periods, and sunny/rainy conditions.

This repository focuses on **reading measurements, visualizing range–Doppler (RD) maps and flight trajectories, and constructing annotated real-data detection datasets**.

> **Data availability.** ScienceDB Version 1 is under review; its assigned DOI and CSTR are not yet registered. The real detection benchmark is available from [GitHub Releases](https://github.com/ffxu1024/CellularEye/releases/tag/benchmark-v1.0).

## At a Glance

| Resource | Contents |
| :--- | :--- |
| Channel measurements | 25.6 GHz mmWave measurements; 30 scanned beams; two receive channels and two OFDM symbols per beam visit |
| Associated records | UAV positions and motion, RGB/IR video, and meteorological observations; availability varies by collection |
| Collection scenarios | Multiple flight geometries and Go/Back segments, receiving stations, beams, periods, and weather conditions |
| Real detection benchmark | 224 train / 71 validation / 1,141 test images with YOLO annotations |
| Toolkit | Binary reading, RD visualization, flight/collection-window visualization, and position-assisted annotation |

The acquisition platform and each downloadable release may cover different resources. Consult the selected release's file list for its actual contents.

## Visual Gallery

The measured RD clips show continuous UAV-visible intervals over the **full range and velocity axes**. Red display windows follow **coarse RTK geometry**, with a fixed size of 40 × 40 RD bins. Each clip retains every frame within its stated interval; these are selected intervals from longer recordings.

### Same collection, two receiving stations

**Sunny · Traj-1-1 Back · collection `2026_09_05_02_30` · Beam14 · Rx channel 0 · OFDM symbol 0**

Both clips show frames **24–50** (zero-based): **27 consecutive frames** from the same 52-frame acquisition.

| BS23 / Beam14 | BS22 / Beam14 |
| :---: | :---: |
| ![Sunny BS23 Beam14 continuous UAV echo sequence](assets/gifs/sunny_bs23_beam14_rd.gif) | ![Sunny BS22 Beam14 continuous UAV echo sequence](assets/gifs/sunny_bs22_beam14_rd.gif) |

The BS22 sequence also shows the structured interference at that receiving site. Open the [BS23 GIF](assets/gifs/sunny_bs23_beam14_rd.gif) or [BS22 GIF](assets/gifs/sunny_bs22_beam14_rd.gif) for full-resolution viewing.

### Rainy UAV sensing

**Rainy · Traj-1 Back · collection `2026_09_18_05_15` · BS23 / Beam14 · Rx channel 0 · OFDM symbol 0**

Frames **22–51**: **30 consecutive frames** from a 52-frame acquisition.

<p align="center">
  <img src="assets/gifs/rainy_bs23_beam14_rd.gif" alt="Rainy BS23 Beam14 continuous UAV echo sequence" width="560">
</p>

[Open the rainy RD GIF](assets/gifs/rainy_bs23_beam14_rd.gif).

### Flight trajectory and RF collection window

The RTK flight animations show base-station positions, the moving UAV, and the **BS Collection** segment that overlaps RF acquisition. Each animation includes the full recorded flight.

| Sunny · Traj-1-1 Go | Rainy · Traj-1 Back |
| :---: | :---: |
| Collection `2026_09_03_02_00` · 97 flight samples | Collection `2026_09_18_05_15` · 102 flight samples |
| ![Sunny Go flight and RF collection window](assets/gifs/sunny_uav_collection_window.gif) | ![Rainy Back flight and RF collection window](assets/gifs/rainy_uav_collection_window.gif) |

Playback is accelerated. Acquisition timestamps, collection IDs, displayed frame intervals, and file checksums are provided in [the gallery manifest](docs/gallery_manifest.json). RD frames and flight records have different sampling rates. The 40-bin display windows in this gallery are separate from the benchmark's 30-bin detection labels.

## Testbed

CellularEye is collected on a **228 m × 70 m outdoor testbed** at Purple Mountain Laboratories. Four base-station sites (BS21–BS24), RGB/IR optics, a weather station, and automated UAV facilities provide associated RF, visual, environmental, and flight records.

<p align="center">
  <img src="assets/img/testbed.png" alt="CellularEye testbed: four base-station sites, UAV docks, RGB/IR optics, weather station, and acquisition infrastructure" width="1100">
</p>

<p align="center"><em>Testbed layout and acquisition equipment at Purple Mountain Laboratories.</em></p>

| BS23: 30 beam steering directions | Four-site antenna orientations |
| :---: | :---: |
| ![Thirty beam steering directions at BS23 over the testbed](assets/img/bs23-30-beams.png) | ![Panel-normal directions of BS21, BS22, BS23, and BS24 over the testbed](assets/img/four-site-orientations.png) |

The left panel shows the 30 beam steering directions at BS23; the right panel shows the antenna panel-normal directions at BS21–BS24. The cones illustrate beam geometry rather than measured coverage boundaries. Open the [30-beam view](assets/img/bs23-30-beams.png) or [four-site view](assets/img/four-site-orientations.png) for a larger image.

BS23 provides mmWave illumination, with separate transmit and receive AAUs supporting simultaneous illumination and echo acquisition. The current archived mmWave measurements are organized under receiving sites BS22 and BS23; the four-site deployment shown above describes the platform. Available records vary by collection. Sub-6 GHz measurements are reserved for a subsequent release.

## mmWave Signal and Radar Parameters

### Signal and acquisition settings

| Parameter | Value | Description |
| :--- | :--- | :--- |
| Carrier frequency | 25.6 GHz | Released mmWave measurement configuration |
| Waveform | OFDM reference signal | CSI is obtained using a Zadoff–Chu reference sequence |
| Subcarrier spacing | 120 kHz | NR numerology μ = 3 |
| Subcarriers / complex samples per symbol and channel | 1,024 | Frequency / range dimension |
| Effective sensing bandwidth | 122.88 MHz | 1,024 × 120 kHz |
| Useful OFDM symbol duration | 8.3333 μs | Excludes cyclic prefix |
| CP-inclusive OFDM symbol duration | Approximately 8.92 μs | Manufacturer-provided timing used for processing |
| Beam directions | 30 | Five groups of six beams; zero-based beam IDs 0–29 |
| OFDM symbols per beam visit | 2 | Symbol IDs 0–1 |
| Receive channels | 2 | Channel IDs 0–1 |
| Slow-time observations per beam and symbol | 512 | Repeated visits within one beam group |
| Nominal sweep interval | 400 ms | Use individual file timestamps for temporal alignment |
| Stored complex sample | Interleaved I/Q; signed 16-bit big-endian per component | 4 bytes per complex sample |
| Complete 30-beam sweep | 251,658,240 bytes (240 MiB) | One complete `.bin` file |

<details>
<summary><strong>AAU hardware specifications</strong></summary>

| Parameter | Specification |
| :--- | :--- |
| Operating band | 26 GHz band |
| Configurable hardware bandwidth | 100–200 MHz |
| EIRP | 48 dBm |
| Planar array | 4 × 4 |
| Polarization channels | Horizontal and vertical |
| Upward-facing panel tilt | Nominally 45° |

The configurable hardware bandwidth is a device capability; the effective sensing bandwidth of the released configuration above is 122.88 MHz.

</details>

### Derived RD coordinates and theoretical limits

| Parameter | Value | Relation / interpretation |
| :--- | :--- | :--- |
| Same-beam / same-symbol PRI | 107.04 μs | 6 beams × 2 symbols × 8.92 μs |
| Per-beam CPI | 54.80448 ms | 512 × PRI |
| Range-bin spacing / theoretical resolution | 1.2207 m | c / (2 × bandwidth) |
| Radial-velocity-bin spacing / theoretical resolution | 0.1069 m/s | c / (2 × carrier frequency × CPI) |
| Theoretical unambiguous range | 1,250 m | c / (2 × subcarrier spacing) |
| Centered unambiguous velocity interval | Approximately [−27.37, +27.37) m/s | Limits ±c / (4 × carrier frequency × PRI) |
| RD matrix | 1,024 range bins × 512 velocity bins | Before image resizing or cropping |
| Range coordinate | n × 1.2207 m | n = 0, …, 1,023; use unrounded bin spacing in code |
| Velocity coordinate | (m − 256) × 0.1069 m/s | m = 0, …, 511; use unrounded bin spacing in code |

These values use c = 3 × 10⁸ m/s and the nominal timing above. PRI is the revisit interval for a fixed beam and symbol position; it is different from the 400 ms sweep interval. Theoretical unambiguous range is not an experimentally established detection range. Coordinates use the toolkit's half-path convention: with separate transmitter and receiver sites, range is half the total Tx–target–Rx path and velocity is its time derivative.

## Downloads

| Resource | Location | Availability |
| :--- | :--- | :--- |
| Dataset homepage | [PML multimodal data portal](http://pmldatanet.com.cn/dataapp/multimodal) | Dataset information and access instructions |
| Archival dataset, Version 1 | [ScienceDB DOI](https://doi.org/10.57760/sciencedb.018bv) · [CSTR](https://cstr.cn/31253.11.sciencedb.018bv) | **Under review; identifiers not yet registered** |
| Real detection benchmark v1.0 | [Download archive](https://github.com/ffxu1024/CellularEye/releases/download/benchmark-v1.0/CellularEye-real-benchmark-v1.0.tar.gz) · [Release notes](https://github.com/ffxu1024/CellularEye/releases/tag/benchmark-v1.0) | 1,436 images and labels · approximately 586 MB |

For detection experiments, download the prepared real benchmark. To inspect channel measurements or construct your own dataset, download the required raw collections through the dataset portal. Raw recordings and processed benchmark images are separate downloads.

### Raw collection structure

```text
<dataset_root>/
└── 2025_12_09_12_00/
    ├── mmw/
    │   ├── 22/
    │   │   └── *.bin
    │   └── 23/
    │       └── *.bin
    ├── camera/           # RGB / infrared video
    ├── meteorological/  # Weather observations
    └── uav/             # Timestamped UAV flight records
```

The directories present depend on the collection. A collection identifier groups associated records; individual files retain their own timestamps.

### Binary measurements

<p align="center">
  <img src="assets/img/bin-layout.png" alt="Binary storage order: five beam groups, 512 scans per group, six beams per scan, two OFDM symbols, two receive channels, and interleaved big-endian I/Q samples" width="1100">
</p>

<p align="center"><em>Storage hierarchy of one complete .bin sweep, from beam groups to individual I/Q bytes. Indices are zero-based.</em></p>

One complete `.bin` file contains a 30-beam sweep: five groups of six beams, 512 repeated scans per group, two OFDM symbols per beam visit, two receive channels, and 1,024 complex samples per symbol/channel. I and Q are interleaved signed 16-bit big-endian integers. The complete sweep occupies 251,658,240 bytes (240 MiB).

The stored samples are a range-domain representation of CSI after acquisition-side FFT processing. The reader transforms the selected samples into a frequency–slow-time channel matrix; RD processing provides range and radial-velocity coordinates. Beam indices are `0–29`; symbol and receive-channel indices are `0–1`.

## Quick Start

Choose the workflow that matches your task:

| I want to… | Start here |
| :--- | :--- |
| Use prepared detection images and labels | [Benchmark](#benchmark) |
| Render an RD figure from a raw collection | [RD visualization](#rd-visualization) |
| Inspect flight trajectories and collection windows | [Trajectory and collection-window visualization](#trajectory-and-collection-window-visualization) |
| Generate a dataset from my selected real collections | [Real-data generation](#real-data-generation) |

### Installation

```bash
git clone https://github.com/ffxu1024/CellularEye.git
cd CellularEye
conda create -n cellulareye python=3.11
conda activate cellulareye
python -m pip install -r requirements-tested.txt
python -m pip install -e .
```

`requirements-tested.txt` records the dependency versions tested in a clean Python 3.11 environment. The editable installation installs this toolkit from `pyproject.toml`. The toolkit requires Python 3.11 or newer. No GPU is required for these tools.

### RD visualization

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

See the [visual gallery](#visual-gallery) for complete measured RD sequences and flight/collection-window animations.

### Trajectory and collection-window visualization

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

### Real-data generation

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

### Preview generated labels

```bash
python src/visualize_real_dataset.py \
  --input_dir datasets/real_uav_bs23_beam14_w30h30 \
  --output_dir results/labels
```

This saves an image grid and an annotated GIF. Images are paired with labels by split and filename, including datasets with fewer than eight images.

## Benchmark

[**Download the real detection benchmark v1.0**](https://github.com/ffxu1024/CellularEye/releases/tag/benchmark-v1.0)

The `.tar.gz` package contains measured RD images and YOLO annotations: **224 training, 71 validation, and 1,141 test samples**. It includes fixed split lists, scenario metadata, and named test subsets. The package requires no raw `.bin` files.

### Download and extract

Run from the repository root:

```bash
mkdir -p datasets
cd datasets
curl -fL --retry 3 -o CellularEye-real-benchmark-v1.0.tar.gz https://github.com/ffxu1024/CellularEye/releases/download/benchmark-v1.0/CellularEye-real-benchmark-v1.0.tar.gz
tar -xzf CellularEye-real-benchmark-v1.0.tar.gz
cd ..
python scripts/prepare_benchmark.py --root datasets/CellularEye-real-benchmark-v1.0
```

The setup command creates `configs/all.yaml` and one YAML plus image list per test subset. Runtime paths are resolved to the extracted dataset's location. Re-run this command after moving the dataset.

### Package structure

```text
CellularEye-real-benchmark-v1.0/
├── images/{train,val,test}/
├── labels/{train,val,test}/
├── splits/                  # Fixed splits and test subsets
├── metadata/                # Per-sample sources and processing settings
├── configs/                 # Runtime detector configs after setup
├── dataset.yaml
└── README.md
```

### Read images and labels

```python
from pathlib import Path
import numpy as np
from PIL import Image

root = Path("datasets/CellularEye-real-benchmark-v1.0")
image_path = root / (root / "splits/reference.txt").read_text().splitlines()[0]
label_path = root / "labels/test" / image_path.with_suffix(".txt").name
image = np.asarray(Image.open(image_path))
boxes = np.loadtxt(label_path, ndmin=2)
print(image.shape, boxes)  # (1024, 512), class/x_center/y_center/width/height
```

Images are 8-bit grayscale PNGs with velocity on the horizontal axis and increasing range upward. Labels use normalized image coordinates: `0 x_center y_center width height`. Box widths and heights are 30 RD bins. Training, validation, and test use disjoint collection IDs; the original image and label bytes are preserved.

| Test subset | Flight / condition | Images |
| :--- | :--- | ---: |
| `reference` | Sunny Traj-1-1 Back, BS23/B14 | 66 |
| `trajectory_traj11_go` | Sunny Traj-1-1 Go | 117 |
| `trajectory_traj3_back` | Sunny Traj-3 Back | 425 |
| `trajectory_traj4_go` | Sunny Traj-4 Go | 54 |
| `weather_traj11_back` | Rainy Traj-1-1 Back | 122 |
| `weather_traj1_back` | Rainy Traj-1 Back | 134 |
| `station_bs22` | Sunny Traj-1-1 Back, BS22/B14 | 58 |
| `beam13` | Sunny Traj-1-1 Back, BS23/B13 | 63 |
| `time_2025_traj11_go` | Sunny 2025-12 Traj-1-1 Go | 102 |

Unspecified receivers and beams are BS23/B14. The acquisition-period subset also differs in flight direction from the reference. See the archive README for full annotation and processing conventions.

## Usage Terms

The source code retains the repository's existing [MIT License](LICENSE).

**Patent Notice:** The underlying algorithms and data processing methods may be subject to pending or granted patents owned by the relevant rights holders. The MIT license granted herein applies strictly to the source code and does not convey any express or implied licenses under such patents. For commercial use of the patented methods, please contact the appropriate rights holder or technology transfer office.

The real detection benchmark is distributed under CC BY-NC 4.0. For each dataset download, follow the usage terms stated on its distribution page; the code license does not replace dataset terms.

## Support

For toolkit questions, please [open an issue](https://github.com/ffxu1024/CellularEye/issues) with the toolkit version, command, collection identifier, and relevant error output. For dataset access, consult the [PML data portal](http://pmldatanet.com.cn/dataapp/multimodal).
