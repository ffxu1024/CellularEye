"""Evaluate fixed validation-selected checkpoints on measured RD image sets."""
import argparse
import csv
import json
import os
import shlex
from pathlib import Path
import sys
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SEEDS = [1, 101, 666, 999, 2026]
GROUPS = {
 'reference': ['reference'],
 'trajectory': ['trajectory_traj11_go', 'trajectory_traj3_back', 'trajectory_traj4_go'],
 'weather': ['weather_traj11_back', 'weather_traj1_back'],
 'bs': ['station_bs22'], 'beam': ['beam13'], 'time': ['time_2025_traj11_go'],
 'traj11_go': ['trajectory_traj11_go'], 'traj3_back': ['trajectory_traj3_back'],
 'traj4_go': ['trajectory_traj4_go'], 'rain_traj11': ['weather_traj11_back'],
 'rain_traj1': ['weather_traj1_back'],
}
METHODS = {'real': 'Real', 'sim_awgn': 'Pure Statistics',
           'sim_bg_bs22': 'Real background + Statistics', 'sim_bg_rain': 'Real background + Statistics'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--benchmark-root', type=Path, required=True)
    p.add_argument('--runs-root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--groups', nargs='+', choices=list(GROUPS), default=list(GROUPS))
    p.add_argument('--methods', nargs='+', choices=list(METHODS), default=['real', 'sim_awgn'])
    p.add_argument('--seeds', nargs='+', type=int, default=SEEDS)
    p.add_argument('--device', default='0')
    p.add_argument('--smoke', action='store_true', help='Evaluate two frames per group; writes SMOKE.json.')
    a = p.parse_args()
    command=shlex.join(sys.argv)
    import torch
    import ultralytics
    import _yolo_metrics
    torch.set_num_threads(2)
    if ultralytics.__version__ != '8.4.121':
        raise RuntimeError('Use ultralytics==8.4.121 for this evaluator.')
    out, benchmark, runs = a.output.resolve(), a.benchmark_root.resolve(), a.runs_root.resolve()
    if out.exists():
        raise FileExistsError(f'Existing output preserved: {out}')
    samples = json.loads((HERE/'configs/test_samples.json').read_text())
    rows = []
    for method in a.methods:
        for seed in a.seeds:
            run = runs/f'{method}_seed-{seed}'
            if not (run/'weights/best.pt').is_file():
                raise FileNotFoundError(run/'weights/best.pt')
            rows.append(dict(Method=METHODS[method], Seed=seed, Run=os.path.relpath(run, ROOT), Weights='best'))
    if len(set(r['Method'] for r in rows)) != len(a.methods):
        raise ValueError('Evaluate BS22 and rainy measured-background models in separate commands.')
    out.mkdir(parents=True)
    checkpoints = out/'checkpoints.csv'
    with checkpoints.open('w', newline='') as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    # The historical validator consumes directories. Only links to the selected
    # benchmark files are staged; no resize or re-encoding is performed.
    for group in a.groups:
        selected = [r for r in samples if r['subset'] in GROUPS[group]]
        if a.smoke:
            selected = selected[:2]
        stage = out/'inputs'/group
        for r in selected:
            for key in ['image', 'label']:
                source = benchmark/r[key]
                if not source.is_file():
                    raise FileNotFoundError(source)
                folder = 'images' if key == 'image' else 'labels'
                target = stage/folder/'test'/source.name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(source)
        config = out/f'{group}.yaml'
        directory = os.path.relpath(stage/'images/test', ROOT)
        config.write_text(yaml.safe_dump(dict(path='.', train=directory, val=directory, test=directory, names={0:'uav'})))
        sys.argv = ['_yolo_metrics.py', '--results', str(checkpoints), '--test-yaml', str(config),
                    '--output-dir', str(out/group), '--groups', 'all', '--device', a.device]
        _yolo_metrics.main()
    (out/('SMOKE.json' if a.smoke else 'evaluation.json')).write_text(json.dumps(dict(
        command=command, output=str(out), benchmark_root=str(benchmark), runs_root=str(runs),
        smoke=a.smoke, methods=a.methods, seeds=a.seeds, groups=a.groups,
        ultralytics=ultralytics.__version__, torch=torch.__version__,
        confidence=.25, box_matching_iou=.45, nms_iou=.7, candidate_limit=300,
        inference_imgsz=[1024,512], checkpoint_selection='best validation checkpoint; fixed across test groups'),indent=2)+'\n')


if __name__ == '__main__':
    main()
