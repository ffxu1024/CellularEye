"""Train YOLO26n on the four fixed CellularEye detection sources."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import sys
import yaml

HERE = Path(__file__).resolve().parent
METHODS = ('real', 'sim_awgn', 'sim_bg_bs22', 'sim_bg_rain')
SEEDS = (1, 101, 666, 999, 2026)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--methods', nargs='+', choices=METHODS, default=list(METHODS))
    p.add_argument('--seeds', nargs='+', type=int, default=list(SEEDS))
    p.add_argument('--initial-weights', default='yolo26n.pt')
    p.add_argument('--device', default='0')
    p.add_argument('--workers', type=int, default=0)
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--smoke', action='store_true', help='Two train/two val images, one epoch at 128 pixels. Separate output; no benchmark claim.')
    a = p.parse_args()
    import torch
    import ultralytics
    from ultralytics import YOLO
    torch.set_num_threads(2)
    if ultralytics.__version__ != '8.4.121':
        raise RuntimeError('Use ultralytics==8.4.121 to match the archived evaluator and training settings.')
    root, output = a.data_root.resolve(), a.output.resolve()
    for method in a.methods:
        cfg = yaml.safe_load((HERE/'configs'/f'{method}.yaml').read_text())
        splits = {}
        for split, count in [('train', 224), ('val', 71)]:
            directory = root/method/'images'/split
            images = sorted(directory.glob('*.png'))
            if len(images) != count:
                raise ValueError(f'{method}/{split}: expected {count} PNGs, found {len(images)}')
            for image in images:
                label = root/method/'labels'/split/(image.stem+'.txt')
                if not label.is_file():
                    raise FileNotFoundError(label)
            splits[split] = images
        for seed in a.seeds:
            target = output/f'{method}_seed-{seed}'
            if target.exists():
                raise FileExistsError(f'Existing output preserved: {target}')
            options = dict(cfg['training'])
            options.update(device=a.device, workers=a.workers, seed=seed,
                           project=str(output), name=target.name, exist_ok=False)
            if a.smoke:
                options.update(epochs=1, imgsz=128, batch=2, workers=0, amp=False,
                               plots=False, mosaic=0., close_mosaic=0)
            print(json.dumps(dict(method=method, seed=seed, smoke=a.smoke,
                                  train=len(splits['train']), val=len(splits['val']),
                                  output=str(target)), indent=2), flush=True)
            if a.dry_run:
                continue
            runtime = output/'data'
            runtime.mkdir(parents=True, exist_ok=True)
            data = {'path': str(root/method), 'train': 'images/train',
                    'val': 'images/val', 'names': {0: 'uav'}}
            if a.smoke:
                for split in splits:
                    text = runtime/f'{method}_{split}_smoke.txt'
                    text.write_text('\n'.join(str(i) for i in splits[split][:2])+'\n')
                    data[split] = str(text)
            dataset = runtime/f'{method}{"_smoke" if a.smoke else ""}.yaml'
            dataset.write_text(yaml.safe_dump(data, sort_keys=False))
            options['data'] = str(dataset)
            YOLO(a.initial_weights).train(**options)
            weights = Path(a.initial_weights)
            record = dict(command=shlex.join(sys.argv), method=method, seed=seed,
                          smoke=a.smoke, config=str(dataset), output=str(target),
                          ultralytics=ultralytics.__version__, torch=torch.__version__,
                          initial_weights=str(weights), options=options)
            if weights.is_file():
                record['initial_weights_sha256'] = hashlib.sha256(weights.read_bytes()).hexdigest()
            (target/'run_record.json').write_text(json.dumps(record, indent=2)+'\n')


if __name__ == '__main__':
    main()
