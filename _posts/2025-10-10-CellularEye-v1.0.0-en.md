---
layout: post
title: CellularEye Dataset v1.0.0
subtitle: A Large-Scale, Evolving Multi-modal Dataset for Environmental Perception Based on Commercial Cellular Networks
tags: [Dataset, ISAC, Wireless-Communications]
comments: true
mathjax: true
---

## Introduction

{: .box-success}
Welcome to the official homepage of the CellularEye dataset.  
**CellularEye** is a pioneering large-scale multi-modal dataset designed for cutting-edge environmental perception research. Its core feature is the use of **commercial communication equipment (BBU, AAU)** to collect real-world cellular network IQ data, synchronized with high-resolution visible-light video, infrared video, and weather data. Our goal is to bridge the gap between communication and sensing, providing robust, real-world data support for researchers exploring the future of **Integrated Sensing and Communication (ISAC)**.

![Multi-modal]({{ '/assets/img/multi-modal-en.png' | relative_url }})

![RV Map Example]({{ '/assets/img/rv-map.gif' | relative_url }})


## Key Features

{: .box-note}
**Commercial Cellular Signals**: Data originates from operational, commercial cellular network equipment, not simulations or lab-grade signals, offering high research value.  
**Rich Multi-modal Data**: Includes tightly synchronized IQ data streams, visible-light video, infrared video, and detailed meteorological metrics.  
**Diverse Scenarios**: Covers a wide range of real-world scenarios, including different times of day, weather conditions, and target activities.  
**Evolving Dataset**: CellularEye is a "living" dataset. We are committed to continuous updates, releasing more scenarios and richer annotations in the future.  


## Dataset Description & Usage

This dataset is collected by a cell-free distributed base station system, comprising eCPRI interface millimeter-wave (mmWave) and Sub-6GHz IQ data, infrared video, visible-light video, and corresponding meteorological data. We aim to provide high-quality, real-world multi-modal data for the ISAC field, especially for tasks like environmental perception, object detection, and tracking.  
To capture diverse environmental characteristics, we perform synchronized data collection at four key time points daily: 00:00, 06:00, 12:00, and 18:00.

### Dataset Structure

All data is archived by collection sequence (i.e., the start time of the collection task). In the dataset's root directory, you will find the following folder structure:
```
<dataset_root>/
└── 2025_09_27_00_00/  # 采集序列ID (格式: YYYY_MM_DD_HH_MM)
    ├── camera/
    │   ├── camera_2025-09-27-00_01_01.mp4
    │   ├── ir_2025-09-27-00_01_01.mp4
    │   └── ...
    ├── meteorological/
    │   ├── 2025-09-27-00-01-01.txt
    │   └── ...
    └── mmw/
        ├── 21/
        │   ├── 2025_09_27_00_01_01_280.bin
        │   └── ...
        ├── 22/
        ├── 23/
        └── 24/
└── 2025_09_27_06_00/
    └── ...
```
#### mmWave IQ Data Illustration
Each .bin file represents one sensing frame. The data arrangement within the .bin file is shown in the figure below.
![mmw-scan-intro]({{ '/assets/img/mmw-scan-intro.png' | relative_url }})

#### System Parameters Illustration
The system's sensing parameters are shown in the figure below.
![system-parameters]({{ '/assets/img/parameter.png' | relative_url }})

## Collection Scenario

**Purple Mountain Laboratories (PML) 6G Veriﬁcation Center, Outdoor Field**

![scenario-pml]({{ '/assets/img/scenario-pml-en.png' | relative_url }})

## Quick Start & Download

For your convenience, we provide a **[Python Script]({{'assets/doc/rv_public_v3.py' | relative_url }})** to help you easily read and visualize the data. 
You can run the script as follows:

```
python rv_public_v3.py --bin_dir /public_data/2025_10_19_18_00/mmw --bs_id 22 --beam_id 30
```

{: .box-note}
**Download Data**: We recommend downloading the dataset via the following links. To ensure the reproducibility of your research, please explicitly state the dataset version you used in your paper.

{: .box-note}
| Version | Release Date | Description | Download Link |
| :--- | :--- | :--- | :--- |
| **v1.0** | October 2025 | First public release. Includes IQ, infrared, visible-light, and meteorological data from different times of the day. | [PML Real-world Wireless Network Data Platform](http://pmldatanet.com.cn/) |

<details markdown="1">
<summary>Click here!</summary>
Here you can see an **expandable** section
</details>



