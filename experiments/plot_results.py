"""Rebuild detection summaries, numerical panels, and the conventional detector table."""
import argparse
import csv
import json
from pathlib import Path
import statistics as st
import numpy as np

HERE=Path(__file__).resolve().parent
SEEDS={1,101,666,999,2026}


def read(path):
    with path.open() as f:return list(csv.DictReader(f))


def write(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def summaries(rows,**identity):
    output=[]
    for method in dict.fromkeys(r['Method'] for r in rows):
        selected=[r for r in rows if r['Method']==method]
        if {int(r['Seed']) for r in selected}!=SEEDS or len(selected)!=5:
            raise ValueError(f'Expected the five fixed seeds for {identity}/{method}')
        values={k:[] for k in ['map','fp','miss','mae']}
        counts={int(r['Frames']) for r in selected}
        if len(counts)!=1:raise ValueError('Different sample counts across seeds')
        n=counts.pop()
        for r in selected:
            if int(r['TP_conf0.25_iou0.45'])+int(r['FN_conf0.25_iou0.45'])!=n:
                raise ValueError('Box counts do not sum to the single-target frame count')
            values['map'].append(float(r['mAP50-95']))
            values['fp'].append(int(r['FP_conf0.25_iou0.45'])/n)
            values['miss'].append(int(r['FN_conf0.25_iou0.45'])/n)
            if r['CentreMeanError_bins_detected']!='':
                values['mae'].append(float(r['CentreMeanError_bins_detected']))
        for key,v in values.items():
            output.append(dict(**identity,method=method,metric=key,frames=n,
                mean=st.mean(v) if v else None,sample_sd=st.stdev(v) if len(v)>1 else 0. if v else None,
                defined_seeds=len(v)))
    return output


def assert_locked(actual,locked,keys):
    index={tuple(r[k] for k in keys):r for r in actual}
    if len(index)!=len(locked):raise ValueError('Summary coverage differs from archived plots')
    for r in locked:
        x=index[tuple(r[k] for k in keys)]
        for field in ['mean','sample_sd']:
            if not np.isclose(float(x[field]),float(r[field]),rtol=0,atol=1e-12):
                raise ValueError(f'Archived numerical mismatch: {r} versus {x}')
        if int(x['defined_seeds'])!=int(r['defined_seeds']):raise ValueError('Seed count mismatch')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results',type=Path,default=HERE/'results')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();root=a.results.resolve();out=a.output.resolve()
    archived=root==(HERE/'results').resolve()
    if out.exists():raise FileExistsError(f'Existing figures preserved: {out}')
    out.mkdir(parents=True)
    domains=[];subsets=[];background=[]
    for domain in ['Reference','Trajectory','Weather','BS','Beam','Time']:
        domains.extend(summaries(read(root/'domains'/domain.lower()/'per_seed_metrics.csv'),domain=domain))
    for category in ['trajectory','weather']:
        rows=read(root/'subsets'/category/'per_seed_metrics.csv')
        for group in dict.fromkeys(r['Group'] for r in rows):
            subsets.extend(summaries([r for r in rows if r['Group']==group],category=category,group=group))
        subsets.extend(summaries(read(root/'domains/reference/per_seed_metrics.csv'),category=category,group='Reference'))
    raw=read(root/'background/per_seed_metrics.csv')
    for domain in ['Rain1','BS22']:
        for method in ['Real','Pure Statistics','Real background + Statistics']:
            rows=[r for r in raw if r['domain']==domain and r['method']==method]
            if len(rows)!=5 or {int(r['seed']) for r in rows}!=SEEDS:raise ValueError('Background seed mismatch')
            for key in ['map','fp','miss','mae']:
                v=[float(r[key]) for r in rows if r[key] not in ['', 'None']]
                background.append(dict(domain=domain,method=method,metric=key,frames=int(rows[0]['frames']),
                    mean=st.mean(v),sample_sd=st.stdev(v),defined_seeds=len(v)))
    if archived:
        assert_locked(domains,read(root/'domains/plot_data.csv'),['domain','method','metric'])
        assert_locked(subsets,read(root/'subsets/plot_data.csv'),['category','group','method','metric'])
        assert_locked(background,read(root/'background/plot_data.csv'),['domain','method','metric'])
    write(out/'domains.csv',domains);write(out/'subsets.csv',subsets);write(out/'background.csv',background)
    # The table's Weather row uses low-speed rainy Traj-1 Back only.
    from evaluate_cfar import TABLE_GROUPS
    table=[];raw=read(root/'cfar/metrics_raw.csv')
    for scenario,groups in TABLE_GROUPS.items():
        for method in ['CA-CFAR','MTI+CA-CFAR','YOLO-Real']:
            seeds=['1','101','666','999','2026'] if method=='YOLO-Real' else ['']
            values=[]
            for seed in seeds:
                rows=[r for r in raw if r['group'] in groups and r['method']==method and r['seed']==seed and float(r['gate_bins'])==5]
                if len(rows)!=len(groups):raise ValueError('Missing conventional evaluation group')
                tp,fn,fp,frames=[sum(int(r[k]) for r in rows) for k in ['TP','FN','FP','frames']]
                values.append((tp/(tp+fn),fp/frames))
            result=dict(scenario=scenario,method=method,frames=frames)
            for i,key in enumerate(['recall','FP_per_frame']):
                v=[r[i] for r in values];result[key]=st.mean(v);result[key+'_sd']=st.stdev(v) if len(v)>1 else None
            table.append(result)
    if archived:
        locked=read(root/'cfar/summary.csv')
        for x,r in zip(table,locked,strict=True):
            if (x['scenario'],x['method'],x['frames'])!=(r['scenario'],r['method'],int(r['frames'])):raise ValueError('Table coverage mismatch')
            for key in ['recall','FP_per_frame']:
                if not np.isclose(x[key],float(r[key]),rtol=0,atol=1e-12):raise ValueError('Conventional table mismatch')
    write(out/'conventional_detection.csv',table)
    header='| Scenario | CA-CFAR detection | MTI+CFAR detection | YOLO detection | CA-CFAR FP/frame | MTI+CFAR FP/frame | YOLO FP/frame |\n| :--- | ---: | ---: | ---: | ---: | ---: | ---: |\n'
    for scenario in TABLE_GROUPS:
        rows=[r for r in table if r['scenario']==scenario]
        header+='| '+scenario+' | '+' | '.join([f"{r['recall']:.3f}" for r in rows]+[f"{r['FP_per_frame']:.2f}" for r in rows])+' |\n'
    (out/'conventional_detection.md').write_text(header)
    from _plot_panels import render
    render(domains,subsets,background,out)
    (out/'verification.json').write_text(json.dumps(dict(
        status='passed',verified_against_archived_plot_tables=archived,domain_mean_sd_pairs=len(domains),subset_mean_sd_pairs=len(subsets),
        background_mean_sd_pairs=len(background),table_rows=len(table),
        sample_sd='ddof=1 across five fixed training seeds',
        overview_rain_frames=256,background_rain_frames=134,cfar_rain_frames=134),indent=2)+'\n')
    print(f'Rebuilt 128 mean/SD pairs and 18 table rows. Archived table verification: {archived}.',flush=True)


if __name__=='__main__':main()
