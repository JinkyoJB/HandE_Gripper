# -*- coding: utf-8 -*-
"""02 그래프에 활성화 루틴 주석 추가 + 04 속도를 레이저 실측 기준으로 정정."""
import csv, glob, json, os
import numpy as np
from common import *
from sync import series
from svgchart import Chart, decimate

HERE = os.path.dirname(os.path.abspath(__file__))
DST = OUT
R = json.load(open(os.path.join(HERE, "summary.json")))
BLUE, RED, GREEN, GRAY, ORANGE = "#2563eb", "#dc2626", "#059669", "#94a3b8", "#ea580c"
span = R["03"]["span_mm"]

# ─────────────────────────────── 02 : 활성화 루틴 표시
iv, hdr, a, t0 = load_clavis(sorted(glob.glob(os.path.join(MEAS, "02_*", "*.csv")))[-1])
L1, L2, _ = clavis_opening(hdr, a)
s = -(L1 + L2); s -= np.nanmin(s); t = np.arange(len(a)) * iv
m = (t >= 12.4) & (t <= 43)                    # 활성화(rACT) 루틴 구간 8~12.4 s 제외
x, y = decimate(t[m], s[m], 320)
st = R["02"]["laser_stroke_mm"]
c = Chart("02 · 무부하 개폐 5회 — 레이저 실측 개구", "측정장비 시간 [s]", "개구 [mm]",
          (12.4, 43), (-4, 60), note="활성화(rACT) 루틴 구간(8~12.4 s) 제외")
c.hline(R["02"]["laser_open_mm"], GRAY)
c.hline(R["02"]["laser_closed_mm"], GRAY)
c.line(x, y, GREEN, 1.6)
c.text(13.0, 56.5, f'개방 {R["02"]["laser_open_mm"]:.2f} mm', color="#475569")
c.text(13.0, 4.5, f'폐합 {R["02"]["laser_closed_mm"]:.2f} mm', color="#475569")
c.text(26.5, 31, f'스트로크 {st:.2f} ± {R["02"]["laser_stroke_sd_mm"]:.3f} mm  (gPO 3 ↔ 249)',
       anchor="middle", color="#047857")
open(os.path.join(HERE, "svg/02.svg"), "w", encoding="utf-8").write(c.render())

# ─────────────────────────────── 04 : 레이저 실측 이동시간
def laser_motion(run, thr=3.0, min_amp=40):
    d = series(run)
    ss = d["sm"].copy(); ss -= np.nanmin(ss); tt = d["tm"]
    v = np.abs(np.gradient(ss, tt)); idx = np.where(v > thr)[0]
    segs = np.split(idx, np.where(np.diff(idx) > 1)[0] + 1)
    out = []
    for g in segs:
        if len(g) < 8:
            continue
        if abs(ss[g[-1]] - ss[g[0]]) < min_amp:
            continue
        out.append((tt[g[0]], tt[g[-1]] - tt[g[0]]))
    return d, out

d8, out8 = laser_motion("08")
off8 = R["offset"]["08"]
ev = load_events(sorted(glob.glob(os.path.join(CTRL, "08_*", "*_events.csv")))[0])
cmds = [((e[0] - d8["t0"]).total_seconds() - off8, e[1]) for e in ev if e[1].endswith("_cmd")]
meas = {}
for tc, name in cmds:
    rsp = int(name.split("rSP")[1].split("_")[0])
    cand = [o for o in out8 if 0 <= o[0] - tc < 1.2]
    if cand:
        meas.setdefault(rsp, []).append(cand[0][1])

script = {r["rSP"]: r["t_mean"] for r in R["04"]["rows"]}
rows = []
for rsp in sorted(script):
    if rsp in meas:
        tl = float(np.mean(meas[rsp]))
        rows.append(dict(rSP=rsp, t_script=script[rsp], t_laser=round(tl, 3),
                         v_script=round(span / script[rsp], 1), v_laser=round(span / tl, 1),
                         overhead=round(script[rsp] - tl, 3), n=len(meas[rsp]), src="레이저 실측"))
    else:
        rows.append(dict(rSP=rsp, t_script=script[rsp], t_laser=None,
                         v_script=round(span / script[rsp], 1), v_laser=None,
                         overhead=None, n=0, src="—"))
oh = float(np.mean([r["overhead"] for r in rows if r["overhead"]]))
for r in rows:                                    # rSP=64 는 오버헤드 평균으로 추정
    if r["t_laser"] is None:
        r["t_laser"] = round(r["t_script"] - oh, 3)
        r["v_laser"] = round(span / r["t_laser"], 1)
        r["src"] = f"추정(오버헤드 {oh:.3f}s)"

R["04"]["laser"] = dict(rows=rows, overhead_mean=round(oh, 3),
                         v_max_laser=max(r["v_laser"] for r in rows),
                         saturated=False)
json.dump(R, open(os.path.join(HERE, "summary.json"), "w"), ensure_ascii=False, indent=1)
json.dump(R, open(os.path.join(DST, "summary.json"), "w"), ensure_ascii=False, indent=1)

c = Chart("04 · rSP ↔ 개폐 속도 (측정 방식 비교)", "rSP [count]", "속도 [mm/s]",
          (0, 270), (0, 175), note=f"스크립트 측정에는 고정 오버헤드 약 {oh:.2f} s 포함")
c.band(20, 150, GRAY, 0.16)          # 라벨은 겹침 방지를 위해 우하단에 별도 배치
xs = [r["rSP"] for r in rows]
c.line(xs, [r["v_laser"] for r in rows], GREEN, 1.9, label="레이저 실측 (실제 손가락 이동)")
c.scatter(xs, [r["v_laser"] for r in rows], GREEN)
c.line(xs, [r["v_script"] for r in rows], RED, 1.6, dash="5 4", label="스크립트 측정 (지령~gOBJ 전환)")
c.scatter(xs, [r["v_script"] for r in rows], RED, fill=False)
for r in rows:
    c.text(r["rSP"], r["v_laser"] + 8, f'{r["v_laser"]:.0f}', anchor="middle", color="#047857")
c.text(266, 23.5, "공칭 20~150 mm/s", anchor="end", color="#64748b")
open(os.path.join(HERE, "svg/04.svg"), "w", encoding="utf-8").write(c.render())

# CSV 갱신
with open(os.path.join(DST, "04_속도_스텝응답", "04_속도커브.csv"), "w",
          newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["rSP", "스크립트_이동시간_s", "레이저_실이동시간_s", "오버헤드_s",
                "스크립트기준_속도_mm_s", "레이저기준_속도_mm_s", "출처"])
    for r in rows:
        w.writerow([r["rSP"], r["t_script"], r["t_laser"], r["overhead"],
                    r["v_script"], r["v_laser"], r["src"]])

for r in rows:
    print(f'rSP={r["rSP"]:3d}  스크립트 {r["t_script"]:.3f}s({r["v_script"]:5.1f})  '
          f'레이저 {r["t_laser"]:.3f}s({r["v_laser"]:5.1f})  {r["src"]}')
print("오버헤드 평균", round(oh, 3), "s")
