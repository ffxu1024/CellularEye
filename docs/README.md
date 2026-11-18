# CellularEye documentation

[Project website](https://ffxu1024.github.io/CellularEye/) · [GitHub repository](https://github.com/ffxu1024/CellularEye)

- [Get started](quickstart.md) — Read measurements, inspect flights, and export real-data annotations.
- [Download the data](downloads.md) — Choose raw collections or the ready-to-use detection benchmark.
- [Collection catalog](collections.md) — Find public collections by target, weather, trajectory, and direction.
- [Data format](data-format.md) — Collection directories, binary storage, and time alignment.
- [Signal & radar parameters](parameters.md) — Acquisition settings, hardware specifications, and RD coordinates.
- [Detection benchmark](benchmark.md) — Fixed splits, labels, scenario subsets, and reading examples.
- [Usage terms](terms.md) — Source-code licensing, dataset terms, and patent notice.

[Published-paper citation](https://ffxu1024.github.io/CellularEye/#citation) · [BibTeX](CITATION.bib)

The collection catalog is generated from [scripts/real_dataset_metadata.yaml](../scripts/real_dataset_metadata.yaml). After editing the public metadata, run `python scripts/build_collection_catalog.py` to update the catalog. The website deployment also regenerates it from this YAML.
