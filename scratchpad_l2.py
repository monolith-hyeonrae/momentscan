from momentscan.stash import clip_dir, read_headpose
import polars as pl, numpy as np, json, cv2
from pathlib import Path
OUT=Path('output/l2'); clip='test_0'; SID=2
gt=pl.read_parquet(clip_dir(OUT,clip)/'gate_trace.parquet')
hp=read_headpose('output/l2',clip)
h={(r['track_id'],r['frame_idx']):r['yaw'] for r in hp.iter_rows(named=True)}
g={r['frame_idx']:r for r in gt.filter(pl.col('track_id')==SID).iter_rows(named=True)}

man=json.loads((clip_dir(OUT,clip)/'crops'/'manifest.json').read_text())
sub=next(s for s in man['subjects'] if int(s['subject_id'])==SID)
cap=cv2.VideoCapture(str(clip_dir(OUT,clip)/'crops'/sub['file']))
def crop(fi):
    if fi not in sub['frames']: return None
    cap.set(cv2.CAP_PROP_POS_FRAMES, sub['frames'].index(fi)); ok,im=cap.read()
    return cv2.cvtColor(im,cv2.COLOR_BGR2RGB) if ok else None

frames=[4,9,11,13,15,20,46,56,68,76]
rows=[]
sdir=Path('/tmp/claude-1000/-home-hyeonrae-repo-monolith-momentscan/7b36c51c-b81f-4454-b74a-f20a0b1d11c3/scratchpad')
for fi in frames:
    r=g.get(fi)
    mp = round(r['yaw_f'],1) if r['pose_src']=='mp' else None
    sd = round(h.get((SID,fi)),1)
    im=crop(fi)
    if im is not None:
        cv2.imwrite(str(sdir/f'c_{fi}.png'), cv2.cvtColor(im,cv2.COLOR_RGB2BGR))
    rows.append((fi,mp,sd,r['pose_src'],r['reason'],r['side_raw'],r['quarter_ok']))
    print(fi,'MP',mp,'6D',sd,r['pose_src'],r['reason'],'side_raw',r['side_raw'])
cap.release()
