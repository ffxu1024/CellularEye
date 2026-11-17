# Signal & radar parameters

## Signal and acquisition settings

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

## Derived RD coordinates and theoretical limits

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
