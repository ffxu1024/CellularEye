<div align="center">

# CellularEye

### A Real-World Base-Station Dataset for Integrated Sensing and Communication

[![Project website](https://img.shields.io/badge/website-CellularEye-145a71)](https://ffxu1024.github.io/CellularEye/)
[![Documentation](https://img.shields.io/badge/docs-get_started-2b6e65)](https://ffxu1024.github.io/CellularEye/quickstart.html)
[![Dataset](https://img.shields.io/badge/data-ScienceDB-2865a8)](https://doi.org/10.57760/sciencedb.018bv)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776ab)](pyproject.toml)
[![License](https://img.shields.io/badge/code-MIT-8a7043)](LICENSE)

[Project Website](https://ffxu1024.github.io/CellularEye/) · [Documentation](https://ffxu1024.github.io/CellularEye/quickstart.html) · [Dataset](https://doi.org/10.57760/sciencedb.018bv) · [Benchmark](https://github.com/ffxu1024/CellularEye/releases/tag/benchmark-v1.0) · [Issues](https://github.com/ffxu1024/CellularEye/issues)

<img src="assets/img/multi-modal-en.png" alt="CellularEye measurement platform and data modalities" width="900">

</div>

**CellularEye** provides real-world base-station measurements for integrated sensing and communication (ISAC) research. Collected on an outdoor testbed at Purple Mountain Laboratories, it includes complex channel measurements, UAV flight records, RGB/infrared video, and weather observations across multiple sensing conditions. Record availability varies by collection.

This repository provides tools for reading binary measurements, visualizing range–Doppler (RD) maps and UAV flights, and generating position-assisted real-data annotations. Visit the **[project website](https://ffxu1024.github.io/CellularEye/)** for scenario GIFs, flight animations, testbed geometry, and dataset details.

## Data

| Resource | Access |
| :--- | :--- |
| **Raw dataset — primary source** | [Published on ScienceDB](https://doi.org/10.57760/sciencedb.018bv) · approximately 2.68 TB before compression |
| **Real detection benchmark** | [GitHub Release v1.0](https://github.com/ffxu1024/CellularEye/releases/tag/benchmark-v1.0) · approximately 586 MB · 224 train / 71 validation / 1,141 test images |
| Auxiliary portal | [PML multimodal data portal](http://pmldatanet.com.cn/dataapp/multimodal) |

The benchmark contains RD images and YOLO labels and requires no raw `.bin` files. See the [download guide](https://ffxu1024.github.io/CellularEye/downloads.html) for the available resources.

## Installation

```bash
git clone https://github.com/ffxu1024/CellularEye.git
cd CellularEye
conda create -n cellulareye python=3.11
conda activate cellulareye
python -m pip install -r requirements-tested.txt
python -m pip install -e .
```

Python 3.11 or newer is required. No GPU is required for these tools.

## Quick start

After downloading a raw collection from ScienceDB:

```bash
python scripts/check_bin.py \
  --collection_path /path/to/collection \
  --bs_id 23 --beam_id 14 --max_frames 20
```

For complete commands and data conventions, use the documentation:

- [RD visualization, flight animations, and real-data generation](https://ffxu1024.github.io/CellularEye/quickstart.html)
- [Binary format and timestamp alignment](https://ffxu1024.github.io/CellularEye/data-format.html)
- [Signal and radar parameters](https://ffxu1024.github.io/CellularEye/parameters.html)
- [Benchmark download and reading](https://ffxu1024.github.io/CellularEye/benchmark.html)

The guides are also available [inside this repository](docs/README.md).

## License & support

Source code: [MIT](LICENSE). Real detection benchmark: **CC BY-NC 4.0**. Follow the terms on each dataset’s distribution page. The existing patent notice and full usage terms are retained in [Usage terms](docs/terms.md).

For questions and reproducible bug reports, [open an issue](https://github.com/ffxu1024/CellularEye/issues).
