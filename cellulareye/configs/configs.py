from dataclasses import dataclass, field
import numpy as np
import yaml
from pathlib import Path
from typing import Dict, List

@dataclass
class ISACConfig:
    """Configuration for ISAC Signal."""
    # ---------------- Base parameters ----------------
    c: float = 3e8                   # Speed of light (m/s)
    base_scs: float = 15e3           # Base subcarrier spacing (Hz)
    u: int = 3                       # frequency scaling factor
    fc: float = 25.6e9               # Carrier frequency (Hz)
    number_subcarriers: int = 1024   # Number of subcarriers
    zc_u: int = 25                   # ZC sequence root index
    frame_period: float = 400e-3     # Radar frame period (s)
    number_symbols_per_radar_frame: int = 512 # Number of symbols per radar frame

    pri: float = 8.92e-6 * 2 * 6     # Pulse Repetition Interval (s) symbol duration 8.92us(Tu+Tcp) * 2symbol * 6beam

    # ---------------- Optional configurations (If external parameters are not provided, they will be bound with base parameters in __post_init__) ----------------
    number_cp: int = field(default=None)

    # ---------------- Derived parameters ----------------
    # Using init=False indicates these parameters are not directly passed to the constructor, but calculated
    subcarrier_spacing: float = field(init=False)
    ofdm_symbols_duration: float = field(init=False)
    Ts: float = field(init=False)
    fs: float = field(init=False)
    cpi: float = field(init=False)
    delay_bin: float = field(init=False)
    range_bin: float = field(init=False)
    doppler_bin: float = field(init=False)
    velocity_bin: float = field(init=False)
    unambiguous_range: float = field(init=False)
    unambiguous_velocity: float = field(init=False)
    range_seq: np.ndarray = field(init=False)
    velocity_seq: np.ndarray = field(init=False)

    def __post_init__(self):
        # initialize optional parameters
        if self.number_cp is None:
            self.number_cp = self.number_subcarriers

        self.subcarrier_spacing = self.base_scs * (2 ** self.u)
        self.ofdm_symbols_duration = 1 / self.subcarrier_spacing
        self.Ts = 1 / (self.number_subcarriers * self.subcarrier_spacing)
        self.fs = self.number_subcarriers * self.subcarrier_spacing

        self.cpi = self.number_symbols_per_radar_frame * self.pri

        self.delay_bin = 1 / (self.number_subcarriers * self.subcarrier_spacing)
        self.range_bin = self.c * self.delay_bin / 2
        self.doppler_bin = 1 / self.cpi
        self.velocity_bin = self.doppler_bin * self.c / (2 * self.fc)
        self.unambiguous_range = self.range_bin * self.number_subcarriers
        self.unambiguous_velocity = self.velocity_bin * self.number_symbols_per_radar_frame / 2

        self.range_seq = np.arange(self.number_subcarriers) * self.range_bin
        self.velocity_seq = np.arange(-self.number_symbols_per_radar_frame // 2,
                                      self.number_symbols_per_radar_frame // 2) * self.velocity_bin
        self.print_summary()

    def print_summary(self):
        """Prints a summary of the ISAC signal configuration."""
        print("\n" + "="*30 + " ISAC signal Configuration " + "="*30 + "\n")
        print(f"Carrier frequency: {self.fc / 1e9:.4f} GHz")
        print(f"Bandwidth: {self.number_subcarriers * self.subcarrier_spacing / 1e6:.4f} MHz")
        print(f"OFDM subcarrier spacing: {self.subcarrier_spacing / 1e3:.4f} kHz")
        print(f"Range bin: {self.range_bin:.4f} m")
        print(f"Velocity bin: {self.velocity_bin:.4f} m/s")
        print(f"Unambiguous range: {self.unambiguous_range:.4f} m")
        print(f"Unambiguous velocity: {self.unambiguous_velocity:.4f} m/s")

# ------- Support parameter modification -------
# test_cfg = ISACConfig(fc = 26e9)
# print(f"Range bin with fs=26MHz: {test_cfg.range_bin} m")
# print(f"Velocity bin with fs=26MHz: {test_cfg.velocity_bin} m/s")

@dataclass
class BaseStation:
    """Dataclass holding explicit physical parameters for a single base station."""
    latitude: float
    longitude: float
    altitude: float
    yaw: float
    pitch: float
    roll: float

    # Optional: Keep these properties if you still need to pass them as lists to other functions
    @property
    def gps(self) -> List[float]:
        """Returns [latitude, longitude, altitude]"""
        return [self.latitude, self.longitude, self.altitude]

    @property
    def pose(self) -> List[float]:
        """Returns [yaw, pitch, roll]"""
        return [self.yaw, self.pitch, self.roll]

@dataclass
class ScenarioConfig:
    """Scenario configuration loaded from a YAML file."""
    base_stations: Dict[str, BaseStation]

    def __post_init__(self):
        self.print_summary()

    def print_summary(self):
        """Prints a summary of loaded base stations."""
        print("\n" + "="*30 + " Scenario Configuration " + "="*30 + "\n")
        print(f"Successfully loaded {len(self.base_stations)} base stations: {list(self.base_stations.keys())} and their GPS and pose parameters.")
        # If you want to print details of each base station, you can uncomment the following lines:
        # for bs_id in self.base_stations:
        #     self.print_bs_summary(bs_id)

    @classmethod
    def from_yaml(cls, yaml_name: str = "base_stations.yaml") -> "ScenarioConfig":
        """Factory method to instantiate ScenarioConfig from a YAML file."""
        file_path = Path(__file__).parent / yaml_name

        with open(file_path, 'r', encoding='utf-8') as f:
            raw_data = yaml.safe_load(f)

        # Explicitly unpack the list elements into named attributes
        parsed_stations = {}
        for bs_id, data in raw_data.items():
            parsed_stations[str(bs_id)] = BaseStation(
                latitude=data["gps"][0],
                longitude=data["gps"][1],
                altitude=data["gps"][2],
                yaw=data["pose"][0],
                pitch=data["pose"][1],
                roll=data["pose"][2]
            )
        return cls(base_stations=parsed_stations)


@dataclass
class PlotConfig:
    """Configuration for plotting parameters."""
    figsize: tuple = (6, 5)
    save_dir: str = 'results/plots'
    bs_colors: List[str] = field(default_factory=lambda: ["#167ee6", "#f4ea61", "#f80b26", "#1D7529", "#75e96a", "#010e10", "#9628d6", "#506571"])
    overlap_color: str = '#e63946'
    traj_color: str = '#1f77b4'
    cmap: str = 'jet' # 'viridis', 'plasma', 'inferno', 'magma' are good for radar maps, 'gray' is also commonly used, but 'plasma' has better contrast for our case.
    vmin: float = -40
    vmax: float = 70
    # Average max signal power in 60 dB, average noise floor in -20 dB, minimum value is the added 1e-12 to avoid log(0), or vmin~vmax -40~70 dB without normalization.
