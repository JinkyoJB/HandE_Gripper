# -*- coding: utf-8 -*-
"""파지력 '합' 보정에 딸린 산출물 재생성 — 동기화 CSV, 05 지표 CSV, summary.json."""
import csv, json, os
import numpy as np
from common import *
from sync import series

HERE = os.path.dirname(os.path.abspath(__file__))
DST = OUT
R = json.load(open(os.path.join(HERE, "summary.json")))
FS = json.load(open(os.path.join(HERE, "force_sum.json")))
FR = [64, 128, 192, 255]
SP = [32, 128, 192, 255]


def wcsv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


# ── 1. 동기화 시계열 (파지력 열 포함)
def merged(run):
    d = series(run)
    off = R["offset"][run]
    tc = d["tc"] - off
    lo = max(tc[0], d["tm"][0]); hi = min(tc[-1], d["tm"][-1])
    g = np.arange(lo, hi, 0.01)
    pos = np.interp(g, tc, d["ctrl"]["POS"])
    laser = np.interp(g, d["tm"], d["sm"])
    gm = mm_from_gpo(pos)
    k, b = np.polyfit(gm, laser, 1)
    cols = [np.round(g, 3), np.round(pos, 1),
            np.round(np.interp(g, tc, d["ctrl"]["OBJ"]), 1),
            np.round(np.interp(g, tc, d["ctrl"]["CUR"]), 1),
            np.round(gm, 4), np.round((laser - b) / k, 4),
            np.round((laser - b) / k - gm, 4),
            np.round(np.interp(g, d["tm"], grip_force(d["hdr"], d["a"])), 3)]
    hdr = ["t_meas_s", "gPO", "gOBJ", "gCU", "개구_gPO환산_mm", "개구_레이저_mm",
           "편차_mm", "파지력_N"]
    return hdr, list(zip(*cols))


od = os.path.join(DST, "90_동기화")
for run in ["05", "07", "09"]:
    hdr, rows = merged(run)
    wcsv(os.path.join(od, f"{run}_동기화_시계열.csv"), hdr, rows)
    print(f"90_동기화/{run}_동기화_시계열.csv  {len(rows)}행")

# ── 2. 07 16조합 파지력 (05 절의 대체 데이터)
grid = {tuple(int(x) for x in k.split("_")): v for k, v in FS["grid"].items()}
rows = []
for f in FR:
    for s in SP:
        v = grid[(f, s)]
        rows.append([f, s, round(float(np.mean(v)), 1), round(float(np.std(v)), 2), len(v),
                     round(20 + 165 * f / 255, 1),
                     round(float(np.mean(v)) / (20 + 165 * f / 255), 2)])
wcsv(os.path.join(DST, "05_힘_거동", "05대체_07_파지력.csv"),
     ["rFR", "rSP", "파지력_N", "표준편차_N", "n", "사양식_N", "실측_사양_비"], rows)
print(f"05_힘_거동/05대체_07_파지력.csv  {len(rows)}행")

# ── 3. summary.json
R["07"]["F_peak"] = FS["peak"]
R["force"] = dict(convention="로드셀 2채널의 합 (KS B ISO 18646-3 5.3.3)",
                  coef=FS["coef"], r2=FS["r2"], min=FS["min"], max=FS["max"], peak=FS["peak"],
                  grid={f"rFR{f}_rSP{s}": round(float(np.mean(grid[(f, s)])), 1)
                        for f in FR for s in SP})
for p in (os.path.join(HERE, "summary.json"), os.path.join(DST, "summary.json")):
    json.dump(R, open(p, "w"), ensure_ascii=False, indent=1)
print("summary.json 갱신 —",
      f"F = {FS['coef'][0]:.1f} + {FS['coef'][1]:.4f}·rFR + {FS['coef'][2]:.4f}·rSP, R²={FS['r2']}")

# ── 5. 스크립트 사본 갱신
import shutil
sd = os.path.join(DST, "00_분석스크립트")
for f in ["common.py", "sync.py", "analyze.py", "refine.py", "makesvg.py", "svgchart.py",
          "export.py", "force_from_timing.py", "force_fix.py", "regen_force.py"]:
    shutil.copy(os.path.join(HERE, f), os.path.join(sd, f))
shutil.copy(os.path.join(HERE, "force_sum.json"), os.path.join(sd, "force_sum.json"))
print("00_분석스크립트 사본 갱신")
