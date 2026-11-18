# Collection catalog

This catalog lists the **116 collections in the public raw-data archive release**: 85 UAV-target collections and 31 target-free background collections.

[Browse and filter the catalog](https://ffxu1024.github.io/CellularEye/collections.html) · [YAML metadata](../scripts/real_dataset_metadata.yaml) · [CSV](collections.csv) · [JSON](collections.json)

The YAML file in this repository describes the released collections. Download the recordings from [ScienceDB](https://doi.org/10.57760/sciencedb.018bv).

## Reading the catalog

Target labels describe the collection type. They do not assert that a UAV echo is detectable in every frame. A background collection has no assigned UAV flight trajectory. “Not specified” means the metadata do not establish that field. Tx and Rx identify the configured transmitter and receivers; the files present can vary by collection.

The display groups `Traj-1-1-2025` and `Traj-1-1-202609` under the same geometric trajectory, `Traj-1-1`. The original recording trajectory ID is retained in the JSON and CSV. `Go → Back` denotes a collection containing both flight directions. Collection identifiers are not presented as UTC measurement timestamps; use file timestamps for alignment.

## Collections

| Collection ID | Target | Weather | Trajectory | Direction | Airport | Tx | Rx (configured) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 2025_12_05_00_00 | Target-free background | Sunny | — | — | Not specified | BS23 | BS23, BS22 |
| 2025_12_05_12_00 | UAV target | Sunny | Traj-1-1 | Go | AirportB | BS23 | BS23, BS22 |
| 2025_12_06_00_00 | Target-free background | Sunny | — | — | Not specified | BS23 | BS23, BS22 |
| 2025_12_06_12_00 | UAV target | Sunny | Traj-1-1 | Go | AirportB | BS23 | BS23, BS22 |
| 2025_12_06_18_00 | Target-free background | Sunny | — | — | Not specified | BS23 | BS23, BS22 |
| 2025_12_07_06_00 | Target-free background | Sunny | — | — | Not specified | BS23 | BS23, BS22 |
| 2025_12_07_12_00 | UAV target | Sunny | Traj-1-1 | Go | AirportB | BS23 | BS23, BS22 |
| 2025_12_08_00_00 | Target-free background | Sunny | — | — | Not specified | BS23 | BS23, BS22 |
| 2025_12_08_12_00 | UAV target | Sunny | Traj-1-1 | Go | AirportB | BS23 | BS23, BS22 |
| 2025_12_09_00_00 | Target-free background | Sunny | — | — | Not specified | BS23 | BS23, BS22 |
| 2025_12_09_12_00 | UAV target | Sunny | Traj-1-1 | Go | AirportB | BS23 | BS23, BS22 |
| 2025_12_09_18_00 | Target-free background | Sunny | — | — | Not specified | BS23 | BS23, BS22 |
| 2025_12_10_06_00 | Target-free background | Sunny | — | — | Not specified | BS23 | BS23, BS22 |
| 2025_12_10_12_00 | UAV target | Sunny | Traj-1-1 | Go | AirportB | BS23 | BS23, BS22 |
| 2026_09_02_01_00 | UAV target | Sunny | Traj-1-1 | Back | AirportB | BS23 | BS23, BS22 |
| 2026_09_02_02_00 | UAV target | Sunny | Traj-1-1 | Back | AirportB | BS23 | BS23, BS22 |
| 2026_09_02_03_00 | UAV target | Sunny | Traj-1-1 | Back | AirportB | BS23 | BS23, BS22 |
| 2026_09_02_04_00 | UAV target | Sunny | Traj-1-1 | Back | AirportB | BS23 | BS23, BS22 |
| 2026_09_02_05_00 | UAV target | Sunny | Traj-1-1 | Back | AirportB | BS23 | BS23, BS22 |
| 2026_09_02_12_00 | UAV target | Sunny | Traj-1-1 | Go | AirportB | BS23 | BS23, BS22 |
| 2026_09_02_15_00 | UAV target | Sunny | Traj-1-1 | Go | AirportB | BS23 | BS23, BS22 |
| 2026_09_02_16_00 | UAV target | Sunny | Traj-1-1 | Go | AirportB | BS23 | BS23, BS22 |
| 2026_09_02_17_00 | UAV target | Sunny | Traj-1-1 | Go | AirportB | BS23 | BS23, BS22 |
| 2026_09_02_19_00 | UAV target | Sunny | Traj-1-1 | Go | AirportB | BS23 | BS23, BS22 |
| 2026_09_02_22_00 | UAV target | Sunny | Traj-1-1 | Go | AirportB | BS23 | BS23, BS22 |
| 2026_09_03_00_00 | Target-free background | Sunny | — | — | Not specified | BS23 | BS23, BS22 |
| 2026_09_03_01_00 | UAV target | Sunny | Traj-1-1 | Go | AirportB | BS23 | BS23, BS22 |
| 2026_09_03_02_00 | UAV target | Sunny | Traj-1-1 | Go | AirportB | BS23 | BS23, BS22 |
| 2026_09_03_03_00 | UAV target | Sunny | Traj-1-1 | Go | AirportB | BS23 | BS23, BS22 |
| 2026_09_03_05_00 | UAV target | Sunny | Traj-1-1 | Go | AirportB | BS23 | BS23, BS22 |
| 2026_09_03_06_00 | Target-free background | Sunny | — | — | Not specified | BS23 | BS23, BS22 |
| 2026_09_03_08_00 | UAV target | Sunny | Traj-1-1 | Go | AirportB | BS23 | BS23, BS22 |
| 2026_09_05_00_00 | Target-free background | Sunny | — | — | Not specified | BS23 | BS23, BS22 |
| 2026_09_05_01_30 | UAV target | Sunny | Traj-1-1 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_05_02_30 | UAV target | Sunny | Traj-1-1 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_05_03_30 | UAV target | Sunny | Traj-1-1 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_05_04_30 | UAV target | Sunny | Traj-1-1 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_05_05_30 | UAV target | Sunny | Traj-1-1 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_05_06_00 | Target-free background | Sunny | — | — | Not specified | BS23 | BS23, BS22 |
| 2026_09_05_07_30 | UAV target | Sunny | Traj-1-1 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_05_08_30 | UAV target | Sunny | Traj-1-1 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_05_09_30 | UAV target | Sunny | Traj-1-1 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_05_10_30 | UAV target | Sunny | Traj-1-1 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_05_14_30 | UAV target | Sunny | Traj-3 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_05_15_30 | UAV target | Sunny | Traj-3 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_05_17_30 | UAV target | Sunny | Traj-3 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_05_18_00 | Target-free background | Sunny | — | — | Not specified | BS23 | BS23, BS22 |
| 2026_09_05_19_30 | UAV target | Sunny | Traj-3 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_05_20_30 | UAV target | Sunny | Traj-3 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_05_21_30 | UAV target | Sunny | Traj-3 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_05_22_30 | UAV target | Sunny | Traj-3 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_05_23_30 | UAV target | Sunny | Traj-3 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_06_00_00 | Target-free background | Sunny | — | — | Not specified | BS23 | BS23, BS22 |
| 2026_09_06_01_30 | UAV target | Sunny | Traj-3 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_06_02_30 | UAV target | Sunny | Traj-3 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_06_03_30 | UAV target | Sunny | Traj-3 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_06_04_30 | UAV target | Sunny | Traj-3 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_06_05_30 | UAV target | Sunny | Traj-3 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_06_06_00 | Target-free background | Sunny | — | — | Not specified | BS23 | BS23, BS22 |
| 2026_09_06_07_30 | UAV target | Sunny | Traj-3 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_06_08_30 | UAV target | Sunny | Traj-3 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_06_10_30 | UAV target | Sunny | Traj-3 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_06_11_30 | UAV target | Sunny | Traj-3 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_06_14_30 | UAV target | Sunny | Traj-4 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_06_15_30 | UAV target | Sunny | Traj-4 | Go → Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_06_16_30 | UAV target | Sunny | Traj-4 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_06_17_30 | UAV target | Sunny | Traj-4 | Go → Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_06_18_00 | Target-free background | Sunny | — | — | Not specified | BS23 | BS23, BS22 |
| 2026_09_06_19_30 | UAV target | Sunny | Traj-4 | Go → Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_06_22_30 | UAV target | Sunny | Traj-4 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_06_23_30 | UAV target | Sunny | Traj-4 | Go → Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_07_00_00 | Target-free background | Sunny | — | — | Not specified | BS23 | BS23, BS22 |
| 2026_09_07_01_30 | UAV target | Sunny | Traj-4 | Go | AirportC | BS23 | BS23, BS22 |
| 2026_09_07_02_30 | UAV target | Sunny | Traj-4 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_07_03_30 | UAV target | Sunny | Traj-4 | Go | AirportC | BS23 | BS23, BS22 |
| 2026_09_07_04_30 | UAV target | Sunny | Traj-4 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_07_05_30 | UAV target | Sunny | Traj-4 | Go | AirportC | BS23 | BS23, BS22 |
| 2026_09_07_06_00 | Target-free background | Sunny | — | — | Not specified | BS23 | BS23, BS22 |
| 2026_09_07_07_30 | UAV target | Sunny | Traj-4 | Go | AirportC | BS23 | BS23, BS22 |
| 2026_09_07_08_30 | UAV target | Sunny | Traj-4 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_07_09_30 | UAV target | Sunny | Traj-4 | Go | AirportC | BS23 | BS23, BS22 |
| 2026_09_07_10_30 | UAV target | Sunny | Traj-4 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_07_11_30 | UAV target | Sunny | Traj-4 | Go | AirportC | BS23 | BS23, BS22 |
| 2026_09_07_13_30 | UAV target | Sunny | Traj-4 | Go → Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_07_14_30 | UAV target | Sunny | Traj-4 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_07_15_30 | UAV target | Sunny | Traj-4 | Go → Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_07_16_30 | UAV target | Sunny | Traj-4 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_07_17_30 | UAV target | Sunny | Traj-4 | Go → Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_07_18_00 | Target-free background | Sunny | — | — | Not specified | BS23 | BS23, BS22 |
| 2026_09_07_19_30 | UAV target | Sunny | Traj-4 | Go → Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_07_21_30 | UAV target | Sunny | Traj-4 | Go → Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_17_15_12 | UAV target | Rainy | Traj-1-1 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_17_15_30 | UAV target | Rainy | Traj-1-1 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_17_15_45 | UAV target | Rainy | Traj-1-1 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_17_16_15 | UAV target | Rainy | Traj-1-1 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_17_16_30 | UAV target | Rainy | Traj-1-1 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_17_18_00 | Target-free background | Rainy | — | — | Not specified | BS23 | BS23, BS22 |
| 2026_09_17_19_00 | Target-free background | Rainy | — | — | Not specified | BS23 | BS23, BS22 |
| 2026_09_17_22_04 | UAV target | Rainy | Traj-1-1 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_17_22_54 | UAV target | Rainy | Traj-1 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_17_23_36 | UAV target | Rainy | Traj-1 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_18_01_00 | Target-free background | Rainy | — | — | Not specified | BS23 | BS23, BS22 |
| 2026_09_18_02_00 | Target-free background | Rainy | — | — | Not specified | BS23 | BS23, BS22 |
| 2026_09_18_02_15 | UAV target | Rainy | Traj-1 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_18_04_00 | Target-free background | Rainy | — | — | Not specified | BS23 | BS23, BS22 |
| 2026_09_18_05_15 | UAV target | Rainy | Traj-1 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_18_05_30 | UAV target | Rainy | Traj-1 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_18_06_00 | Target-free background | Rainy | — | — | Not specified | BS23 | BS23, BS22 |
| 2026_09_18_06_15 | UAV target | Rainy | Traj-1 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_18_06_30 | UAV target | Rainy | Traj-1 | Back | AirportC | BS23 | BS23, BS22 |
| 2026_09_18_07_00 | Target-free background | Rainy | — | — | Not specified | BS23 | BS23, BS22 |
| 2026_09_19_01_00 | Target-free background | Sunny | — | — | Not specified | BS23 | BS23, BS22 |
| 2026_09_19_03_00 | Target-free background | Sunny | — | — | Not specified | BS23 | BS23, BS22 |
| 2026_09_19_05_00 | Target-free background | Sunny | — | — | Not specified | BS23 | BS23, BS22 |
| 2026_09_19_07_00 | Target-free background | Sunny | — | — | Not specified | BS23 | BS23, BS22 |
| 2026_09_19_09_00 | Target-free background | Sunny | — | — | Not specified | BS23 | BS23, BS22 |
