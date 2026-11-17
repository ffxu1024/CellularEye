# Data format

## Raw collection structure

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

## Binary measurements

<p align="center">
  <img src="../assets/img/bin-layout.png" alt="Binary storage order: five beam groups, 512 scans per group, six beams per scan, two OFDM symbols, two receive channels, and interleaved big-endian I/Q samples" width="1100">
</p>

<p align="center"><em>Storage hierarchy of one complete .bin sweep, from beam groups to individual I/Q bytes. Indices are zero-based.</em></p>

One complete `.bin` file contains a 30-beam sweep: five groups of six beams, 512 repeated scans per group, two OFDM symbols per beam visit, two receive channels, and 1,024 complex samples per symbol/channel. I and Q are interleaved signed 16-bit big-endian integers. The complete sweep occupies 251,658,240 bytes (240 MiB).

The stored samples are a range-domain representation of CSI after acquisition-side FFT processing. The reader transforms the selected samples into a frequency–slow-time channel matrix; RD processing provides range and radial-velocity coordinates. Beam indices are `0–29`; symbol and receive-channel indices are `0–1`.

## Timestamp alignment

RF filenames use TAI and UAV RTK records use UTC. The toolkit subtracts 37 seconds for the current release and retains its legacy zero-offset exception for January–May 2026 files. Use the actual timestamp provenance for those older captures.
