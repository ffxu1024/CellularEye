"""Arrange a complete evaluation run for numerical plotting; preserve the archive."""
import argparse
import csv
from pathlib import Path
import shutil

SUBSETS={
 'trajectory':{
  'traj11_go':'real_Traj-1-1-202609_None_Go_sunny_snr15.0_tx23_rx23_beam14_w30h30',
  'traj3_back':'real_Traj-3_None_Back_sunny_snr15.0_tx23_rx23_beam14_w30h30',
  'traj4_go':'real_Traj-4_None_Go_sunny_snr15.0_tx23_rx23_beam14_w30h30'},
 'weather':{
  'rain_traj11':'real_Traj-1-1_None_Back_rainy_snr15.0_tx23_rx23_beam14_w30h30',
  'rain_traj1':'real_Traj-1_None_Back_rainy_snr15.0_tx23_rx23_beam14_w30h30'},
}

def read(p):
 with p.open() as f:return list(csv.DictReader(f))

def write(p,rows):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--evaluation',type=Path,required=True)
 p.add_argument('--rain',type=Path,required=True)
 p.add_argument('--bs22',type=Path,required=True)
 p.add_argument('--conventional',type=Path,required=True)
 p.add_argument('--output',type=Path,required=True)
 a=p.parse_args();out=a.output.resolve()
 if out.exists():raise FileExistsError(f'Existing result directory preserved: {out}')
 for directory in [a.evaluation,a.rain,a.bs22,a.conventional]:
  protocol=directory/'protocol.json'
  if (directory/'SMOKE.json').exists() or (protocol.exists() and '"smoke": true' in protocol.read_text()):
   raise ValueError(f'Small functional-test outputs are not full evaluation data: {directory}')
 for group in ['reference','trajectory','weather','bs','beam','time']:
  for filename in ['per_seed_metrics.csv','per_image_localisation.csv']:
   target=out/'domains'/group/filename;target.parent.mkdir(parents=True,exist_ok=True)
   shutil.copy2(a.evaluation/group/filename,target)
 for category,groups in SUBSETS.items():
  for filename in ['per_seed_metrics.csv','per_image_localisation.csv']:
   rows=[]
   for group,identity in groups.items():
    selected=read(a.evaluation/group/filename)
    for r in selected:r['Group']=identity
    rows.extend(selected)
   write(out/'subsets'/category/filename,rows)
 rows=[]
 for directory,group,domain in [(a.rain,'rain_traj1','Rain1'),(a.bs22,'bs','BS22')]:
  for r in read(directory/group/'per_seed_metrics.csv'):
   n=int(r['Frames']);tp=int(r['TP_conf0.25_iou0.45']);fp=int(r['FP_conf0.25_iou0.45']);fn=int(r['FN_conf0.25_iou0.45'])
   rows.append(dict(domain=domain,method=r['Method'],seed=r['Seed'],map=r['mAP50-95'],fp=fp/n,miss=fn/n,
     mae=r['CentreMeanError_bins_detected'],tp=tp,fp_count=fp,fn=fn,
     predicted_frames=n-int(r['NoPrediction_conf0.25']),frames=n))
 write(out/'background/per_seed_metrics.csv',rows)
 (out/'cfar').mkdir()
 for filename in ['metrics_raw.csv','per_frame_counts.csv']:
  shutil.copy2(a.conventional/filename,out/'cfar'/filename)
 print(f'Prepared plotting inputs: {out}')

if __name__=='__main__':main()
