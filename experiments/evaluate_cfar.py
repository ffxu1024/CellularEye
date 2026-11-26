"""Raw-complex CA-CFAR and two-pulse MTI+CA-CFAR with point matching."""
import argparse
import csv
import hashlib
import json
import shlex
from pathlib import Path
import sys
import numpy as np
from PIL import Image
from scipy.ndimage import maximum_filter, uniform_filter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from cellulareye.utils.utils import load_iq_channel_from_bin_file, channel_to_rv_map
from _point_metrics import evaluate_points

SEEDS = [1, 101, 666, 999, 2026]
TABLE_GROUPS = {
    'Ref.': ['Reference'],
    'Traj.': ['Traj-1-1-202609_Go', 'Traj-3_Back', 'Traj-4_Go'],
    'Weather': ['Rainy_Traj-1_Back'], 'BS': ['BS22'],
    'Beam': ['Beam13'], 'Time': ['Period2025'],
}


def cfar_ratio(power, guard=(2, 2), reference=(5, 5), pfa=1e-6):
    """Finite-window CA-CFAR, using actual reference-cell counts at borders."""
    power = np.asarray(power, dtype=np.float64)
    if power.ndim != 2 or not np.isfinite(power).all() or np.any(power < 0):
        raise ValueError('Expected finite nonnegative RD power')
    outer = tuple(2*(g+t)+1 for g,t in zip(guard, reference))
    inner = tuple(2*g+1 for g in guard)
    def reference_sum(array):
        return (uniform_filter(array, size=outer, mode='constant', cval=0.)*np.prod(outer)
                - uniform_filter(array, size=inner, mode='constant', cval=0.)*np.prod(inner))
    count = np.rint(reference_sum(np.ones_like(power)))
    noise = np.maximum(reference_sum(power)/count, np.finfo(np.float64).tiny)
    alpha = count*np.expm1(-np.log(pfa)/count)
    return power/(noise*alpha)


def mti_rd(channel):
    iq = np.fft.ifft(channel, axis=0)
    valid = np.diff(iq, axis=1)/np.sqrt(2.)
    return np.fft.fftshift(np.fft.ifft(valid, n=512, axis=1), axes=1)


def peaks(power):
    ratio = cfar_ratio(power)
    score = ratio/(1+ratio)
    candidates = np.flatnonzero((score == maximum_filter(score, size=7, mode='constant')) & (score >= .001))
    if len(candidates) > 300:
        candidates = candidates[np.argpartition(score.ravel()[candidates], -300)[-300:]]
    candidates = sorted(candidates, key=lambda i: (-score.ravel()[i], i))
    return [[int(i % 512), int(i // 512), float(score.ravel()[i])] for i in candidates]


def write_csv(path, rows):
    with path.open('w', newline='') as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage', choices=['classical', 'yolo', 'report'], required=True)
    p.add_argument('--benchmark-root', type=Path, required=True)
    p.add_argument('--raw-root', type=Path, help='Extracted raw collection root; required for classical stage.')
    p.add_argument('--runs-root', type=Path, help='Folder containing real_seed-N/weights/best.pt; required for yolo.')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--seeds', type=int, nargs='+', default=SEEDS)
    p.add_argument('--device', default='0')
    p.add_argument('--smoke', action='store_true', help='First two samples per scenario group; no full-table claim.')
    a=p.parse_args()
    out=a.output.resolve();out.mkdir(parents=True, exist_ok=True)
    benchmark=a.benchmark_root.resolve()
    all_records=json.loads((HERE/'configs/test_samples.json').read_text())
    groups={g for values in TABLE_GROUPS.values() for g in values}
    records=[r for r in all_records if r['group'] in groups]
    if a.smoke:
        records=[r for group in sorted(groups) for r in [x for x in records if x['group']==group][:2]]
    protocol=dict(smoke=a.smoke, frames=len(records), images=[r['image'] for r in records],
        guard_halfwidth=2, reference_bandwidth=5, nominal_cell_pfa=1e-6,
        candidate_limit=300, local_maximum_window=7, point_gate_bins=5,
        classical_score_threshold=.5, yolo_confidence=.25, nms_iou=.7,
        input='complex samples for CFAR; original grayscale PNG for YOLO',
        weather='Traj-1 Back, 134 frames in the full table')
    protocol_path=out/'protocol.json'
    if protocol_path.exists() and json.loads(protocol_path.read_text()) != protocol:
        raise ValueError('Output protocol differs; use a new output folder.')
    protocol_path.write_text(json.dumps(protocol,indent=2)+'\n')
    import importlib.metadata
    (out/f'command_{a.stage}.json').write_text(json.dumps(dict(command=shlex.join(sys.argv),
        stage=a.stage,output=str(out),benchmark_root=str(benchmark),device=a.device,seeds=a.seeds,
        versions={name:importlib.metadata.version(name) for name in ['numpy','scipy','pillow','ultralytics','torch']}
    ),indent=2)+'\n')
    if a.stage=='classical':
        if a.raw_root is None:
            p.error('--raw-root is required for classical')
        with (out/'classical_predictions.jsonl').open('x') as stream:
            for i,r in enumerate(records):
                raw=a.raw_root.resolve()/r['raw_file']
                image=benchmark/r['image']
                if hashlib.sha256(image.read_bytes()).hexdigest()!=r['image_sha256']:
                    raise ValueError(f'Unexpected benchmark image: {image}')
                channel=load_iq_channel_from_bin_file(raw,r['beam'],r['symbol'],r['rx_channel'])
                rd=channel_to_rv_map(channel)
                encoded=((10*np.log10(np.abs(rd)**2+1e-12)+40)/110*255).clip(0,255).astype('uint8')
                if not np.array_equal(np.roll(encoded,r['range_roll'],axis=0),np.flipud(np.asarray(Image.open(image)))):
                    raise ValueError(f'Complex signal does not reconstruct the benchmark PNG: {raw}')
                for method, power in [('CA-CFAR',np.abs(rd)**2), ('MTI+CA-CFAR',np.abs(mti_rd(channel))**2)]:
                    stream.write(json.dumps(dict(method=method,seed=None,image=r['image'],
                        points=peaks(np.roll(power,r['range_roll'],axis=0))))+'\n')
                if i%50==0:print(f'Classical: {i+1}/{len(records)}',flush=True)
    elif a.stage=='yolo':
        if a.runs_root is None:
            p.error('--runs-root is required for yolo')
        import torch
        import ultralytics
        from ultralytics import YOLO
        torch.set_num_threads(2)
        if ultralytics.__version__!='8.4.121':
            raise RuntimeError('Use ultralytics==8.4.121 for this evaluator.')
        source=out/'sources.txt'
        source.write_text('\n'.join(str(benchmark/r['image']) for r in records)+'\n')
        for seed in a.seeds:
            checkpoint=a.runs_root.resolve()/f'real_seed-{seed}/weights/best.pt'
            with (out/f'yolo_seed{seed}_predictions.jsonl').open('x') as stream:
                predictions=YOLO(str(checkpoint)).predict(source=str(source),imgsz=(1024,512),
                    batch=1 if a.device=='cpu' else 8,device=a.device,rect=True,
                    conf=.001,iou=.7,max_det=300,verbose=False,save=False,stream=True)
                lookup={(benchmark/r['image']).resolve():r for r in records}
                seen=set()
                for pred in predictions:
                    image=Path(pred.path).resolve()
                    if image not in lookup or image in seen:
                        raise ValueError('Unexpected or duplicate prediction image')
                    r=lookup[image];seen.add(image)
                    boxes=pred.boxes.xyxy.cpu().numpy();scores=pred.boxes.conf.cpu().numpy()
                    points=[[(float(b[0])+float(b[2]))/2-.5,1024-(float(b[1])+float(b[3]))/2-.5,float(s)] for b,s in zip(boxes,scores)]
                    stream.write(json.dumps(dict(method='YOLO-Real',seed=seed,image=r['image'],points=points))+'\n')
                if len(seen)!=len(records):raise ValueError('Incomplete predictions')
    else:
        predictions={('CA-CFAR',''):{},('MTI+CA-CFAR',''):{}}
        for r in map(json.loads,(out/'classical_predictions.jsonl').read_text().splitlines()):
            predictions[(r['method'],'')][r['image']]=r['points']
        for seed in a.seeds:
            predictions[('YOLO-Real',str(seed))]={r['image']:r['points'] for r in map(json.loads,(out/f'yolo_seed{seed}_predictions.jsonl').read_text().splitlines())}
        metrics=[];per_frame=[]
        for (method,seed),pred in predictions.items():
            threshold=.25 if method=='YOLO-Real' else .5
            for group in sorted(groups):
                truth={r['image']:r['points'] for r in records if r['group']==group}
                result=evaluate_points(truth,{k:pred[k] for k in truth},gate=5.,threshold=threshold)
                metrics.append(dict(method=method,seed=seed,group=group,**result))
                for image,points in truth.items():
                    result=evaluate_points({image:points},{image:pred[image]},gate=5.,threshold=threshold)
                    per_frame.append(dict(method=method,seed=seed,group=group,image=image,
                        TP=result['TP'],FP=result['FP'],FN=result['FN']))
        write_csv(out/'metrics_raw.csv',metrics)
        write_csv(out/'per_frame_counts.csv',per_frame)
        print(f'Wrote {len(metrics)} grouped rows and {len(per_frame)} frame counts.')


if __name__=='__main__':main()
