"""Preview real RD images with matching YOLO labels."""
import argparse
from pathlib import Path
from cellulareye.utils.plot import verify_yolo_dataset_grid, animate_yolo_frames


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input_dir', required=True)
    p.add_argument('--output_dir', default='results/label_verification')
    p.add_argument('--collection_name', default='')
    a = p.parse_args()
    root = Path(a.input_dir)
    files = sorted((root/'images').rglob(f'{a.collection_name}*.png'))
    if not files:
        p.error('No matching PNG images found under input_dir/images')
    labels = [root/'labels'/im.relative_to(root/'images').with_suffix('.txt') for im in files]
    missing = [str(f) for f in labels if not f.is_file()]
    if missing:
        p.error(f'Missing matching label: {missing[0]}')
    out = Path(a.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = a.collection_name or 'dataset'
    verify_yolo_dataset_grid(files, labels, out/f'{stem}_grid.png', num_samples=min(8,len(files)))
    animate_yolo_frames(files, labels, out/f'{stem}_traj.gif')


if __name__ == '__main__':
    main()
