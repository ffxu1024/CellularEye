# Detection benchmark

[**Download the real detection benchmark v1.0**](https://github.com/ffxu1024/CellularEye/releases/tag/benchmark-v1.0)

The `.tar.gz` package contains measured RD images and YOLO annotations: **224 training, 71 validation, and 1,141 test samples**. It includes fixed split lists, scenario metadata, and named test subsets. The package requires no raw `.bin` files.

## Download and extract

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

## Package structure

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

## Read images and labels

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

## Dataset license

The benchmark images, annotations, and metadata are licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). See [Usage terms](terms.md) for attribution.
