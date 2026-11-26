# Detection experiments

Train YOLO26n on fixed RD-image sources, evaluate the resulting models on measured scenarios, compare conventional detectors on complex measurements, and rebuild numerical figures from archived results. The tools are in [`experiments/`](https://github.com/ffxu1024/CellularEye/tree/main/experiments).

## Environment

Run commands from the repository root. The tested setup uses Linux, Python 3.11, Ultralytics 8.4.121, PyTorch 2.13.0, and torchvision 0.28.0. Full training and GPU evaluation used an RTX 4090; the small training and evaluation examples also run on CPU.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r experiments/requirements.txt
```

The CUDA build used for the archived runs is PyTorch 2.13.0+cu130. Install the matching PyTorch build for your driver before the requirements file when using a GPU. See the [PyTorch installation guide](https://pytorch.org/get-started/locally/). The scripts load `yolo26n.pt` through Ultralytics, which downloads the upstream initialization if absent. An already downloaded initialization can be supplied with `--initial-weights /path/to/yolo26n.pt`.

## Download the image data

The [real benchmark](benchmark.html) supplies 224 measured training images, 71 measured validation images, and 1,141 held-out test images. The separate [detection training package](https://github.com/ffxu1024/CellularEye/releases/tag/detection-v1.0) supplies the four fixed training/validation sources below. Its measured source is identical to the benchmark training/validation images; it includes no test images. Existing benchmark downloads remain valid.

```bash
mkdir -p datasets
curl -fL --retry 3 -o datasets/CellularEye-real-benchmark-v1.0.tar.gz https://github.com/ffxu1024/CellularEye/releases/download/benchmark-v1.0/CellularEye-real-benchmark-v1.0.tar.gz
tar -xzf datasets/CellularEye-real-benchmark-v1.0.tar.gz -C datasets
curl -fL --retry 3 -o datasets/CellularEye-detection-training-v1.0.tar.gz https://github.com/ffxu1024/CellularEye/releases/download/detection-v1.0/CellularEye-detection-training-v1.0.tar.gz
tar -xzf datasets/CellularEye-detection-training-v1.0.tar.gz -C datasets
```

| Source ID | Contents | Train | Validation |
| :--- | :--- | ---: | ---: |
| `real` | Measured sunny Traj-1-1 Back, BS23/Beam14 | 224 | 71 |
| `sim_awgn` | Simulated Traj-1-1 Back echoes with AWGN, BS23 geometry | 224 | 71 |
| `sim_bg_bs22` | Simulated Traj-1-1 Back echoes with measured sunny BS22/Beam14 backgrounds | 224 | 71 |
| `sim_bg_rain` | Simulated Traj-1 Back echoes with measured rainy BS23/Beam14 backgrounds | 224 | 71 |

Each source contains `images/train`, `images/val`, `labels/train`, and `labels/val`. Images are the original 8-bit grayscale PNGs, 512 pixels wide and 1,024 pixels high. Annotations are class-0 YOLO boxes with widths and heights of 30 RD bins. `samples.json` lists package membership and original file identities. These are fixed, already generated training inputs; echo generation and background mixing are outside these tools.

## Check the training workflow

Validate all four fixed budgets without starting training:

```bash
python experiments/train_yolo.py --data-root datasets/CellularEye-detection-training-v1.0 --output runs/detection --dry-run
```

Run a separate small test using two training and two validation images per source, one epoch, and 128-pixel training inputs:

```bash
python experiments/train_yolo.py --data-root datasets/CellularEye-detection-training-v1.0 --output runs/detection-smoke --seeds 1 --device cpu --smoke
```

This verifies loading, optimization, validation, and checkpoint writing. Its outputs are not benchmark results. Use a new output directory for each command; existing runs are preserved.

## Train the fixed sources

The default configuration uses 300 epochs, batch size 16, deterministic training, no early stopping, and seeds **1, 101, 666, 999, 2026**. Training and validation membership remain fixed across seeds. Ultralytics selects `weights/best.pt` using validation fitness; test images are not used for selection. Hyperparameters and augmentation settings are recorded in `experiments/configs/{source}.yaml`.

```bash
mkdir -p logs
tmux new-session -s cellulareye-detection
python experiments/train_yolo.py --data-root datasets/CellularEye-detection-training-v1.0 --output runs/detection --device 0 > logs/detection-training.log 2>&1
```

Detach with Ctrl-B then D. Select a source with `--methods real`, or a seed with `--seeds 1`. Each run writes `args.yaml`, `results.csv`, `weights/best.pt`, `weights/last.pt`, and `run_record.json` under `runs/detection/{source}_seed-{seed}/`. The archived 20 training histories are in `experiments/results/training/`; checkpoint identities are in `experiments/configs/checkpoints.json`.

The saved historical `imgsz` setting is `[1024, 512]`. Ultralytics 8.4.121 resolves this to **1024** for training and validation. The scripts retain this behavior; `predict` accepts the rectangular size for the point-detector comparison. Changing library versions or preprocessing can change the results.

## Evaluate YOLO across measured scenarios

Use the validation-selected checkpoints produced by training. The same five `real` and five `sim_awgn` checkpoints are evaluated on every measured scenario, without scenario-specific retraining or test-based checkpoint selection.

```bash
python experiments/evaluate_yolo.py --benchmark-root datasets/CellularEye-real-benchmark-v1.0 --runs-root runs/detection --output results/detection-evaluation --device 0
```

| Evaluation group | Samples | Definition |
| :--- | ---: | :--- |
| `reference` | 66 | Sunny Traj-1-1 Back, BS23/Beam14 |
| `trajectory` | 596 | Traj-1-1 Go (117), Traj-3 Back (425), Traj-4 Go (54); reference excluded |
| `weather` | 256 | Rainy Traj-1-1 Back (122) and Traj-1 Back (134), pooled |
| `bs` | 58 | Sunny Traj-1-1 Back, BS22/Beam14 |
| `beam` | 63 | Sunny Traj-1-1 Back, BS23/Beam13 |
| `time` | 102 | 2025-12 Traj-1-1 Go, BS23/Beam14 |

The default command also evaluates the trajectory and weather subsets separately as `traj11_go`, `traj3_back`, `traj4_go`, `rain_traj11`, and `rain_traj1`. Each AP is computed on that complete evaluation group, not by averaging subset APs. The six pooled groups partition the 1,141 held-out images; the detailed groups overlap those pooled groups.

Outputs include `per_seed_metrics.csv`, `per_image_localisation.csv`, and `summary.csv` for each evaluation group. mAP50-95 uses the native Ultralytics AP implementation on the 0–1 scale. FP and FN counts use confidence **0.25** and box matching IoU **0.45**. Miss rate is FN/frames; FP/frame is FP/frames. Center error is the Euclidean RD-bin distance from the annotated center to the nearest predicted center, averaged over frames with predictions. It includes predictions that fail the box-IoU match, so it must be read together with miss rate. Undefined center-error seeds are excluded from that metric's mean/SD, with their count recorded.

Use `--groups reference --seeds 1 --smoke --device cpu` with a new output folder for a two-frame evaluation test. `SMOKE.json` marks these partial outputs.

## Evaluate measured-background training sources

The rainy comparison uses **Traj-1 Back, 134 frames**. The BS22 comparison uses **58 frames**. These are separate from the 256-frame pooled weather result above.

```bash
python experiments/evaluate_yolo.py --benchmark-root datasets/CellularEye-real-benchmark-v1.0 --runs-root runs/detection --output results/background-rain --groups rain_traj1 --methods real sim_awgn sim_bg_rain --device 0
python experiments/evaluate_yolo.py --benchmark-root datasets/CellularEye-real-benchmark-v1.0 --runs-root runs/detection --output results/background-bs22 --groups bs --methods real sim_awgn sim_bg_bs22 --device 0
```

Each background source is used only for its specified target scenario. The Real and Sim + AWGN comparisons retain the same fixed reference checkpoints.

## Run CFAR on complex measurements

Download the required raw collections from [ScienceDB](https://doi.org/10.57760/sciencedb.018bv) and extract them under a common raw root. `experiments/configs/test_samples.json` maps each benchmark image to `collection/mmw/receiver/filename.bin`, the beam, and the range alignment used for the stored image. Supply the folder containing the collection directories as `--raw-root`.

CFAR uses complex measurements, not inverse-quantized PNGs. The classical stage reads OFDM symbol 0 and receive channel 0, reconstructs the image from the complex samples, and checks its alignment against the corresponding benchmark PNG before detection.

```bash
python experiments/evaluate_cfar.py --stage classical --benchmark-root datasets/CellularEye-real-benchmark-v1.0 --raw-root /path/to/extracted-collections --output results/conventional
python experiments/evaluate_cfar.py --stage yolo --benchmark-root datasets/CellularEye-real-benchmark-v1.0 --runs-root runs/detection --output results/conventional --device 0
python experiments/evaluate_cfar.py --stage report --benchmark-root datasets/CellularEye-real-benchmark-v1.0 --output results/conventional
```

CA-CFAR uses guard half-width 2 bins, a reference band of 5 bins, and nominal cell false-alarm probability **1e-6**. Borders use their actual number of valid reference cells. MTI applies the two-pulse difference `[1, -1]/sqrt(2)` within each frame, then zero-pads the 511 differences to the original 512-bin Doppler grid. Both variants extract 7×7 local maxima and retain at most 300 candidates per frame. The CFAR score threshold is 0.5, corresponding to the nominal threshold. This nominal cell probability is not an observed object-level false-alarm probability.

The YOLO point comparison uses confidence 0.25, NMS IoU 0.7, and at most 300 candidates. Predictions are matched one-to-one to annotations within **5 bins** on the original RD grid. Point coordinates are `d = x * 512 - 0.5` and `r = (1 - y) * 1024 - 0.5`. This point rule differs from the box-IoU rule above; the table's detection rate is not interchangeable with 1−miss rate from the box metrics.

The archived YOLO point evaluation used GPU inference with batch size 8. CA-CFAR and MTI+CFAR use the original NumPy/SciPy implementation.

The conventional-detector table uses 1,019 target-present images: reference 66, trajectory 596, low-speed rainy Traj-1 Back 134, BS22 58, Beam13 63, and time 102. The other rainy subset is retained in the full image benchmark but is not added to this table. `metrics_raw.csv` and `per_frame_counts.csv` contain grouped and per-frame counts. Add `--smoke` to all three commands, with a separate output directory, to process two frames per component scenario. Existing prediction files are not overwritten.

## Rebuild numerical figures and tables

No model or GPU is needed to rebuild the archived numerical results:

```bash
python experiments/plot_results.py --output results/detection-figures
```

The command recomputes means and sample standard deviations from the archived per-seed CSVs, checks them against the locked plotting tables, and exports PDF, SVG, and PNG panels. It also rebuilds the conventional detector table from raw TP/FP/FN counts. Undefined center errors retain their recorded seed count; error bars use sample SD across training seeds, not standard errors.

| Output | Archived inputs | Coverage |
| :--- | :--- | :--- |
| `reference/` | `experiments/results/domains/reference/` | Real vs Sim + AWGN, 66 frames |
| `scenarios/overall/` | `experiments/results/domains/` | Six pooled scenario groups; Rain = 256 frames |
| `scenarios/trajectory/`, `scenarios/weather/` | `experiments/results/subsets/` plus the reference | Individual trajectory and weather subsets |
| `scenarios/bs/`, `scenarios/beam/`, `scenarios/time/` | Corresponding domain results plus the reference | Per-scenario comparisons |
| `background/` | `experiments/results/background/` | Rainy Traj-1 Back 134; BS22 58; three training sources |
| `conventional_detection.csv`, `conventional_detection.md` | `experiments/results/cfar/metrics_raw.csv` | Six scenarios; five-seed YOLO means; pooled counts before rates |

`verification.json` records numerical reconstruction checks. Archived results remain unchanged when running new evaluations. The evaluation outputs can be inspected alongside the matching archived per-seed and per-frame CSVs; do not replace archived values with a new run without comparing the protocol, membership, checkpoint identities, and numeric outputs.

To plot your completed evaluations using the same layouts, arrange their outputs and pass that directory explicitly:

```bash
python experiments/prepare_results.py --evaluation results/detection-evaluation --rain results/background-rain --bs22 results/background-bs22 --conventional results/conventional --output results/new-plot-inputs
python experiments/plot_results.py --results results/new-plot-inputs --output results/new-detection-figures
```

This produces new figures separately from the archived results. The default plotting command checks numerical agreement with the archived plot tables; an explicit `--results` directory plots the supplied evaluation results and records that distinction in its verification file.

## Licenses

Released training inputs, measured benchmark images, annotations, and result data are [CC BY 4.0](terms.html). CellularEye scripts are MIT. Ultralytics, PyTorch, and initialization weights retain their upstream licenses; see [Ultralytics licensing](https://www.ultralytics.com/license).
