# Download the data

## Raw measurements — ScienceDB

[Open the published ScienceDB dataset](https://doi.org/10.57760/sciencedb.018bv)

ScienceDB is the primary distribution point for the released CellularEye collections. Use the dataset record to select and download raw measurements and associated records. The release contains approximately **2.68 TB before compression**; the size of individual downloads depends on the selected archive.

DOI: [10.57760/sciencedb.018bv](https://doi.org/10.57760/sciencedb.018bv) · [CSTR: 31253.11.sciencedb.018bv](https://cstr.cn/31253.11.sciencedb.018bv)

## Ready-to-use detection benchmark

[Download benchmark v1.0](https://github.com/ffxu1024/CellularEye/releases/tag/benchmark-v1.0)

The approximately 586 MB archive contains measured RD images, YOLO labels, fixed splits, and scenario metadata. It has **224 training, 71 validation, and 1,141 test images** and requires no raw binary recordings. See the [benchmark guide](benchmark.md) for extraction and reading commands.

## Auxiliary portal — PML

The [PML multimodal data portal](http://pmldatanet.com.cn/dataapp/multimodal) provides an additional dataset information and access entry point. ScienceDB is the main source for this release.

## Choosing a download

| Task | Download | Next step |
| :--- | :--- | :--- |
| Work with complex channel measurements | ScienceDB collections | [Data format](data-format.md) |
| Visualize RD maps or UAV flights | ScienceDB collections with the required associated records | [Get started](quickstart.md) |
| Read detection images and labels | GitHub benchmark archive | [Benchmark](benchmark.md) |

Record availability varies by collection. The four-site layout describes the platform; the current archived mmWave measurement folders use receiving-site IDs BS22 and BS23. Sub-6 GHz measurements are reserved for a subsequent release. Follow the usage terms on the selected distribution page.

## Collection metadata

Use the [collection catalog](collections.md) to find the public collections by UAV target or target-free background, weather, trajectory, and Go/Back direction. The [YAML metadata](../scripts/real_dataset_metadata.yaml) are maintained in the GitHub repository, separately from the raw measurement archives on ScienceDB.
