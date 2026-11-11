from pathlib import Path
from contextlib import redirect_stdout
from functools import lru_cache
from io import StringIO
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import matplotlib.patches as patches

from cellulareye.configs.configs import ISACConfig


def plot_gt_3d_trajectory(gt_enu, gt_timestamps, overlapping_gt_indices, bs_enu, plt_cfg=None, save_name: str = None):

    print("\n" + "-"*30 + " Plotting 3D Trajectory Figure " + "-"*30 + "\n")
    # Set figure and 3D axis
    fig = plt.figure(figsize=(10,7))
    ax = fig.add_subplot(111, projection='3d')

    # Set distinct colors for base stations, GT trajectory, and overlapping segment
    if plt_cfg:
        bs_colors = plt_cfg.bs_colors
        overlap_color = plt_cfg.overlap_color
        traj_color = plt_cfg.traj_color
    else:
        bs_colors = ['red', 'blue', 'green', 'orange', 'purple']
        overlap_color = 'yellow'
        traj_color = 'gray'

    # Plot base stations
    for bs_id, enu in bs_enu.items():
        ax.scatter(enu[0], enu[1], enu[2], marker='^', label=f'BS{bs_id}', s=120, color=bs_colors[int(bs_id)-21], alpha=0.8, edgecolors='k', linewidths=0.5)

    # Plot GT trajectory for both whole gt and overlapping part with collection time
    ax.plot(gt_enu[:, 0], gt_enu[:, 1], gt_enu[:, 2], label='Complete Trajectory', color=traj_color, alpha=0.5, linewidth=2)
    if overlapping_gt_indices:
        ax.plot(gt_enu[overlapping_gt_indices, 0], gt_enu[overlapping_gt_indices, 1], gt_enu[overlapping_gt_indices, 2], label='BS Collection', color=overlap_color, linewidth=3)

    # Set labels and title with better spacing
    ax.set_xlabel('East (m)', labelpad=10)
    ax.set_ylabel('North (m)', labelpad=10)
    ax.set_zlabel('Up (m)', labelpad=10)
    ax.set_title('GT Trajectory and Base Stations', pad=0, fontsize=14, fontweight='bold')

    # Make the panes transparent
    ax.xaxis.pane.fill = False
    ax.yaxis.pane.fill = False
    ax.zaxis.pane.fill = False
    ax.grid(color='#e0e0e0', linestyle='--', linewidth=0.5)

    ax.legend(loc='center left', bbox_to_anchor=(0.1, 0.5))

    # Set view angle for better visualization
    # ax.view_init(elev=30, azim=45)

    plt.tight_layout()

    timestamps_str = gt_timestamps[0].strftime("%Y%m%d_%H%M")

    save_dir = Path(plt_cfg.save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    name_suffix = f"_{save_name}" if save_name else ""
    save_path = save_dir / f"fig_gt_trajectory_{timestamps_str}{name_suffix}.png"
    print(f"Saving GT trajectory plot in '{save_path}'...")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    # plt.show()


def animate_gt_3d_trajectory(gt_enu, gt_timestamps, overlapping_gt_indices, bs_enu, plt_cfg=None, save_name: str = None):
    print("\n" + "-"*30 + " Plotting 3D Trajectory Animation " + "-"*30 + "\n")
    fig = plt.figure(figsize=(10,7))
    ax = fig.add_subplot(111, projection='3d')

    if plt_cfg:
        bs_colors = plt_cfg.bs_colors
        overlap_color = plt_cfg.overlap_color
        traj_color = plt_cfg.traj_color
    else:
        bs_colors = ['red', 'blue', 'green', 'orange', 'purple']
        overlap_color = 'yellow'
        traj_color = 'gray'

    # Plot base stations
    for bs_id, enu in bs_enu.items():
        ax.scatter(enu[0], enu[1], enu[2], marker='^', label=f'BS{bs_id}', s=100, color=bs_colors[int(bs_id)-21], alpha=0.8, edgecolors='k', linewidths=0.5)

    # [Important] Init empty line objects for trajectory and overlapping segment
    gt_line, = ax.plot([], [], [], label='GT Trajectory', color=traj_color, alpha=0.7, linewidth=2)
    overlap_line, = ax.plot([], [], [], label='BS Collection', color=overlap_color, linewidth=3)
    uav_marker, = ax.plot([], [], [], marker='*', color='blue', markersize=15, linestyle='None', label='UAV')

    # [Important] Set axes limits based on GT trajectory and bs locations for better visualization
    all_x = np.concatenate([gt_enu[:, 0]] + [[enu[0]] for enu in bs_enu.values()])
    all_y = np.concatenate([gt_enu[:, 1]] + [[enu[1]] for enu in bs_enu.values()])
    all_z = np.concatenate([gt_enu[:, 2]] + [[enu[2]] for enu in bs_enu.values()])
    ax.set_xlim(all_x.min() - 10, all_x.max() + 10)
    ax.set_ylim(all_y.min() - 10, all_y.max() + 10)
    ax.set_zlim(all_z.min() - 10, all_z.max() + 10)

    # Set labels and title with better spacing
    ax.set_xlabel('East (m)', labelpad=10)
    ax.set_ylabel('North (m)', labelpad=10)
    ax.set_zlabel('Up (m)', labelpad=10)
    ax.legend(loc='center left', bbox_to_anchor=(0.1, 0.5))

    ax.xaxis.pane.fill = False
    ax.yaxis.pane.fill = False
    ax.zaxis.pane.fill = False
    ax.grid(color='#e0e0e0', linestyle='--', linewidth=0.5)

    def update(frame):

        # Plot trajectory up to current frame
        current_gt_x = gt_enu[:frame, 0]
        current_gt_y = gt_enu[:frame, 1]
        current_gt_z = gt_enu[:frame, 2]
        gt_line.set_data(current_gt_x, current_gt_y)
        gt_line.set_3d_properties(current_gt_z)

        latest_x = [gt_enu[frame, 0]]
        latest_y = [gt_enu[frame, 1]]
        latest_z = [gt_enu[frame, 2]]
        uav_marker.set_data(latest_x, latest_y)
        uav_marker.set_3d_properties(latest_z)

        if overlapping_gt_indices:
            overlap_frames = [i for i in overlapping_gt_indices if i < frame]
            if overlap_frames:
                overlap_x = gt_enu[overlap_frames, 0]
                overlap_y = gt_enu[overlap_frames, 1]
                overlap_z = gt_enu[overlap_frames, 2]
                overlap_line.set_data(overlap_x, overlap_y)
                overlap_line.set_3d_properties(overlap_z)

        ax.set_title(f'GT Trajectory up to {gt_timestamps[frame].strftime("%Y-%m-%d %H:%M:%S")}', pad=20, fontsize=12)

    ani = FuncAnimation(fig, update, frames=len(gt_enu))

    timestamps_str = gt_timestamps[0].strftime("%Y%m%d_%H%M")

    save_dir = Path(plt_cfg.save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    name_suffix = f"_{save_name}" if save_name else ""
    save_path = save_dir / f"ani_gt_trajectory_{timestamps_str}{name_suffix}.gif"
    print(f"Saving GT trajectory animation GIF with {len(gt_enu)} frames in '{save_path}'...")
    ani.save(save_path, writer='pillow', fps=10)

def animate_rd_maps(rd_maps: np.ndarray,
                    bin_timestamps: list,
                    cfg,
                    plt_cfg,
                    args,
                    save_name: str = None,
                    precise_indices: tuple = None,
                    box_dims_bins: tuple = (10, 10)):
    """
    Animate Range-Doppler (RD) maps and optionally overlay Ground Truth bounding boxes.
    Unified function supporting both raw Precise RD indices.
    """
    print("\n" + "-"*30 + " Plotting 3D RD Map Animation " + "-"*30 + "\n")
    target_aspect = cfg.velocity_bin / cfg.range_bin # compared with extent

    num_range_bins, num_doppler_bins = rd_maps[0].shape
    base_width = 8
    dynamic_figsize = (base_width, base_width * (num_range_bins / num_doppler_bins))
    fig, ax = plt.subplots(figsize=dynamic_figsize)

    # Initialize the image with physical coordinate boundaries
    extent = [-cfg.unambiguous_velocity, cfg.unambiguous_velocity, 0, cfg.unambiguous_range]
    im = ax.imshow(rd_maps[0], cmap=plt_cfg.cmap, aspect=target_aspect, origin='lower', extent=extent, vmin=plt_cfg.vmin, vmax=plt_cfg.vmax)

    ax.set_xlabel('Velocity (m/s)')
    ax.set_ylabel('Range (m)')
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label('Relative Power (dB)')

    # =========================================================================
    # Pre-calculate physical bounding boxes for all frames to optimize drawing
    # Format per box: (v_min, r_min, v_width, r_height)
    # =========================================================================
    frame_boxes = [[] for _ in range(len(rd_maps))]

    if precise_indices is not None:
        index_sets = [precise_indices] if isinstance(precise_indices, tuple) else precise_indices
        v_width = box_dims_bins[0] * cfg.velocity_bin
        r_height = box_dims_bins[1] * cfg.range_bin

        for r_indices, d_indices in index_sets:
            for i in range(len(rd_maps)):
                if not np.isnan(r_indices[i]) and not np.isnan(d_indices[i]):
                    # Convert Bin Index to Physical Centers
                    v_center = (d_indices[i] - cfg.number_symbols_per_radar_frame // 2) * cfg.velocity_bin
                    r_center = r_indices[i] * cfg.range_bin

                    # Calculate Bottom-Left corner
                    frame_boxes[i].append((v_center - v_width / 2, r_center - r_height / 2, v_width, r_height))


    # =========================================================================
    # Animation Update Loop
    # =========================================================================
    def update(frame):
        # Update Image Data
        im.set_data(rd_maps[frame])
        ax.set_title(f'RD Map at {bin_timestamps[frame]}')

        # Clear previous boxes
        [p.remove() for p in ax.patches]

        # Draw new bounding boxes
        for (v_min, r_min, w, h) in frame_boxes[frame]:
            rect = patches.Rectangle((v_min, r_min), w, h, linewidth=1.5, edgecolor='red', facecolor='none')
            ax.add_patch(rect)

        return [im] + list(ax.patches)

    anim = FuncAnimation(fig, update, frames=len(rd_maps), blit=True)

    # Save logic
    timestamps_str = bin_timestamps[0].strftime("%Y%m%d_%H%M")
    name_suffix = f"_{save_name}" if save_name else ""

    save_dir = Path(plt_cfg.save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / f"ani_rd_map_bs_{args.bs_id}_beam_{args.beam_id}_{timestamps_str}{name_suffix}.gif"

    print(f"Saving RD map animation GIF with {len(rd_maps)} frames in '{save_path}'...")
    anim.save(str(save_path), writer='pillow', fps=10)


# =========== YOLO Dataset Visualization Functions ==========
def parse_yolo_labels(label_file: Path, img_width: int, img_height: int) -> list:
    """
    Parse a YOLO format label file and convert relative coordinates to absolute pixels.

    Returns:
        List of dictionaries containing bounding box coordinates.
    """
    boxes = []
    if not label_file.exists():
        return boxes

    with open(label_file, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 5:
                continue

            class_id, x_center, y_center, width, height = map(float, parts[:5])

            # Convert to absolute pixel values
            abs_w = width * img_width
            abs_h = height * img_height
            abs_cx = x_center * img_width
            abs_cy = y_center * img_height

            boxes.append({
                "class_id": int(class_id),
                "center_x": abs_cx,
                "center_y": abs_cy,
                "x_min": abs_cx - abs_w / 2,
                "y_min": abs_cy - abs_h / 2,
                "w": abs_w,
                "h": abs_h
            })
    return boxes

def _rd_extent(img_width: int, img_height: int, cfg):
    """Return Range-Doppler image bounds in physical units."""
    if cfg is None:
        return None
    return [
        -img_width * cfg.velocity_bin / 2,
        img_width * cfg.velocity_bin / 2,
        0,
        img_height * cfg.range_bin,
    ]


@lru_cache(maxsize=1)
def get_default_rd_config():
    """Return the standard RD physics once, without CLI-style summary output."""
    with redirect_stdout(StringIO()):
        return ISACConfig()


def _resolve_rd_config(cfg):
    """Use the project's standard RD physics when a caller omits ``cfg``."""
    return cfg if cfg is not None else get_default_rd_config()


def _add_yolo_boxes(ax, boxes: list, img_width: int, img_height: int, cfg):
    """Draw YOLO boxes in image pixels or Range-Doppler physical coordinates."""
    for box in boxes:
        if cfg is None:
            x_min, y_min, width, height = box["x_min"], box["y_min"], box["w"], box["h"]
        else:
            # The saved YOLO PNG is vertically flipped: pixel row zero is the
            # largest range, while Range-Doppler coordinates increase upward.
            x_min = -img_width * cfg.velocity_bin / 2 + box["x_min"] * cfg.velocity_bin
            y_min = (img_height - box["y_min"] - box["h"]) * cfg.range_bin
            width = box["w"] * cfg.velocity_bin
            height = box["h"] * cfg.range_bin
        ax.add_patch(
            patches.Rectangle(
                (x_min, y_min), width, height,
                edgecolor="red", facecolor="none", linewidth=1.5,
            )
        )


def _plot_rd_image(ax, img: np.ndarray, cfg, plt_cfg):
    """Plot a saved 8-bit RD PNG with a dataset-wide, fixed colour scale."""
    img_height, img_width = img.shape[:2]
    # ``save_rd_image_for_yolo`` maps every dataset image to the same 8-bit
    # scale.  Matplotlib otherwise chooses vmin/vmax from each individual
    # image, making an identical noise floor change colour when a frame has a
    # stronger target or clutter peak.  ``plt.imread`` commonly returns PNGs
    # as floats in [0, 1], while other callers may provide uint8 arrays.
    image_vmax = 255.0 if np.issubdtype(img.dtype, np.integer) or np.nanmax(img) > 1.0 else 1.0
    kwargs = {
        "cmap": plt_cfg.cmap if plt_cfg else "jet",
        "vmin": 0.0,
        "vmax": image_vmax,
    }
    if cfg is not None:
        # Match ``animate_rd_maps`` / check_bin.py: one range bin and one
        # Doppler bin retain the same on-screen size despite different units.
        kwargs.update(
            origin="upper",
            extent=_rd_extent(img_width, img_height, cfg),
            aspect=cfg.velocity_bin / cfg.range_bin,
        )
    ax.imshow(img, **kwargs)


def _set_rd_axis_labels(ax, cfg, fontsize=None):
    """Use physical-unit labels only when a physical configuration is supplied."""
    if cfg is None:
        ax.set_xlabel("Velocity index (Doppler)", fontsize=fontsize)
        ax.set_ylabel("Range index", fontsize=fontsize)
    else:
        ax.set_xlabel("Velocity (m/s)", fontsize=fontsize)
        ax.set_ylabel("Range (m)", fontsize=fontsize)


def verify_yolo_dataset_grid(
    image_files: list,
    label_files: list,
    save_path: Path,
    num_samples: int = 8,
    plt_cfg=None,
    cfg=None,
):
    """
    Plot a randomized or sequential grid of images with overlaid YOLO labels for quick verification.
    """
    cfg = _resolve_rd_config(cfg)
    nrows = 2
    ncols = num_samples // nrows if num_samples % nrows == 0 else (num_samples // nrows) + 1

    fig, axs = plt.subplots(nrows, ncols, figsize=(20, 10))
    axs = axs.flatten() if isinstance(axs, np.ndarray) else [axs]

    for i in range(min(num_samples, len(image_files))):
        img = plt.imread(image_files[i])
        img_height, img_width = img.shape[:2]

        _plot_rd_image(axs[i], img, cfg, plt_cfg)

        boxes = parse_yolo_labels(label_files[i], img_width, img_height)
        _add_yolo_boxes(axs[i], boxes, img_width, img_height, cfg)

        axs[i].set_title(f"Sample: {image_files[i].name}", fontsize=10)
        _set_rd_axis_labels(axs[i], cfg, fontsize=8)
        axs[i].tick_params(labelsize=7)

    for unused in axs[min(num_samples, len(image_files)):]:
        unused.set_visible(False)
    plt.suptitle("YOLO Dataset Label Verification", fontsize=16)
    plt.tight_layout()
    plt.savefig(save_path)
    plt.close(fig)

def animate_yolo_frames(image_files: list, label_files: list, save_path: Path,
                        fps: int = 10, show_labels: bool = True, clear_history: bool = True,
                        plt_cfg=None, cfg=None):
    """
    Create a full-frame GIF animation from a sequence of images and YOLO labels.
    """
    cfg = _resolve_rd_config(cfg)
    fig, ax = plt.subplots(figsize=(10, 10))

    def update(i):
        if clear_history:
            ax.clear()

        img = plt.imread(image_files[i])
        _plot_rd_image(ax, img, cfg, plt_cfg)

        if show_labels:
            img_height, img_width = img.shape[:2]
            boxes = parse_yolo_labels(label_files[i], img_width, img_height)
            _add_yolo_boxes(ax, boxes, img_width, img_height, cfg)

        ax.set_title(f"Frame: {image_files[i].name}")
        _set_rd_axis_labels(ax, cfg)

    anim = FuncAnimation(fig, update, frames=len(image_files), repeat=False)
    anim.save(save_path, writer='pillow', fps=fps)
    plt.close(fig)

def animate_yolo_target_patch(image_files: list, label_files: list, save_path: Path,
                              patch_size: int = 128, fps: int = 10, save_frames_dir: Path = None,
                              plt_cfg=None, cfg=None):
    """
    Create a GIF animation zoomed into the target's local patch, based on the YOLO label center.
    Optionally saves individual frame PNGs to `save_frames_dir`.
    """
    cfg = _resolve_rd_config(cfg)
    if save_frames_dir:
        save_frames_dir.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(6, 6))

    def update(i):
        ax.clear()
        img = plt.imread(image_files[i])
        _plot_rd_image(ax, img, cfg, plt_cfg)

        img_height, img_width = img.shape[:2]
        center_x, center_y = img_width / 2, img_height / 2

        boxes = parse_yolo_labels(label_files[i], img_width, img_height)
        if boxes:
            # Anchor zoom to the first target in the frame
            center_x, center_y = boxes[0]["center_x"], boxes[0]["center_y"]

            _add_yolo_boxes(ax, boxes, img_width, img_height, cfg)

        if cfg is None:
            # Apply crop (zoom) via pixel-coordinate axis limits.
            ax.set_xlim(center_x - patch_size / 2, center_x + patch_size / 2)
            ax.set_ylim(center_y + patch_size / 2, center_y - patch_size / 2)
        else:
            velocity_center = (center_x - img_width / 2) * cfg.velocity_bin
            range_center = (img_height - center_y) * cfg.range_bin
            ax.set_xlim(
                velocity_center - patch_size * cfg.velocity_bin / 2,
                velocity_center + patch_size * cfg.velocity_bin / 2,
            )
            ax.set_ylim(
                range_center - patch_size * cfg.range_bin / 2,
                range_center + patch_size * cfg.range_bin / 2,
            )

        ax.set_title(f"Patch view of {image_files[i].name}")
        _set_rd_axis_labels(ax, cfg)
        fig.tight_layout()

        if save_frames_dir:
            fig.savefig(save_frames_dir / f"patch_{image_files[i].name}")

    anim = FuncAnimation(fig, update, frames=len(image_files), repeat=False)
    anim.save(save_path, writer='pillow', fps=fps)
    plt.close(fig)
