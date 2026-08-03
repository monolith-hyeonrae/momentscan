from momentscan.stash import clip_dir, read_headpose
import polars as pl, numpy as np, json, cv2
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

OUT=Path('output/l2'); clip='test_0'; SID=2
gt=pl.read_parquet(clip_dir(OUT,clip)/'gate_trace.parquet')
hp=read_headpose('output/l2',clip)
h={(r['track_id'],r['frame_idx']):r['yaw'] for r in hp.iter_rows(named=True)}
g={r['frame_idx']:r for r in gt.filter(pl.col('track_id')==SID).iter_rows(named=True)}
RCOL={"admit":"#5ac85a","quarter":"#7ed957","side":"#22ddee","reject:identity":"#d65a5a",
      "reject:no_face":"#e6783c","reject:blur":"#828282","reject:exposure":"#d68a2e","no_view":"#5a5a5a"}

man=json.loads((clip_dir(OUT,clip)/'crops'/'manifest.json').read_text())
sub=next(s for s in man['subjects'] if int(s['subject_id'])==SID)
cap=cv2.VideoCapture(str(clip_dir(OUT,clip)/'crops'/sub['file']))
def crop(fi):
    if fi not in sub['frames']: return None
    cap.set(cv2.CAP_PROP_POS_FRAMES, sub['frames'].index(fi)); ok,im=cap.read()
    return cv2.cvtColor(im,cv2.COLOR_BGR2RGB) if ok else None

frames=[4,9,11,13,15,20,46,56,68,76]
N=len(frames)
fig=plt.figure(figsize=(2.2*N, 8.6))
gs=fig.add_gridspec(2,N, height_ratios=[2.4,1.25], hspace=0.18, wspace=0.06)

for i,fi in enumerate(frames):
    r=g[fi]; ax=fig.add_subplot(gs[0,i])
    im=crop(fi)
    if im is not None: ax.imshow(im)
    ax.set_xticks([]); ax.set_yticks([])
    col=RCOL.get(r['reason'],'#999')
    for sp in ax.spines.values(): sp.set_edgecolor(col); sp.set_linewidth(5)
    mp = f"{r['yaw_f']:.0f}" if r['pose_src']=='mp' else "--"
    sd = h.get((SID,fi))
    ax.set_title(f"f{fi}  MP {mp}°  6D {sd:.0f}°\n[{r['reason']}]  src={r['pose_src']}",
                 fontsize=9, color='black')
cap.release()

# bottom: yaw(t) over opening 0..130
axp=fig.add_subplot(gs[1,:])
op=gt.filter((pl.col('track_id')==SID)&(pl.col('frame_idx')<=130)).sort('frame_idx')
fx=op['frame_idx'].to_list()
y6=[h.get((SID,f)) for f in fx]
ymp=[op_r['yaw_f'] if op_r['pose_src']=='mp' else np.nan for op_r in op.iter_rows(named=True)]
axp.plot(fx,y6,'-o',ms=3,color='#1f77b4',label='6D yaw (all frames)')
axp.plot(fx,ymp,'-s',ms=5,color='#d62728',label='MP yaw (mp-fit frames only)')
for lev in (50,15,-15,-50):
    axp.axhline(lev,ls='--',lw=1,color='#888')
axp.text(131,50,'+SIDE 50',va='center',fontsize=8,color='#555')
axp.text(131,15,'+FRONT 15',va='center',fontsize=8,color='#555')
axp.text(131,-50,'-SIDE 50',va='center',fontsize=8,color='#555')
# shade disagreement >15 where both finite
for op_r in op.iter_rows(named=True):
    f=op_r['frame_idx']
    if op_r['pose_src']=='mp':
        d=abs(op_r['yaw_f']-h.get((SID,f)))
        if d>15:
            axp.axvspan(f-0.5,f+0.5,color='orange',alpha=0.25)
# mark mp-fit window and the proof frames where MP<50 but 6D>=50
for op_r in op.iter_rows(named=True):
    f=op_r['frame_idx']
    if op_r['pose_src']=='mp' and abs(op_r['yaw_f'])<50 and abs(h.get((SID,f)))>=50:
        axp.scatter([f],[op_r['yaw_f']],s=160,facecolors='none',edgecolors='black',lw=2,zorder=5)
axp.set_xlabel('frame_idx (opening)'); axp.set_ylabel('yaw (deg, MP-aligned sign)')
axp.set_xlim(-2,138); axp.legend(loc='lower right',fontsize=8)
axp.set_title("test_0 opening yaw(t): MP fits only f8-15 (positive turn), then MP NaN -> 6D sole source (true profile, negative turn). "
              "Black rings = MP<50 while 6D>=50 (under-reported side). Orange = MP/6D disagree >15°",
              fontsize=8)
fig.suptitle("test_0 OPENING side-face: MediaPipe vs 6DRepNet (subject 2)", fontsize=13, y=0.995)
outp=OUT/'test0_opening_mp6d.png'
fig.savefig(outp, dpi=110, bbox_inches='tight')
print('wrote', outp)
