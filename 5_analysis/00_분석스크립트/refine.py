"""08·09 동기화 교차검증을 정지구간 기준으로 정밀 산출하고 그림을 재생성."""
import json, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from common import *
from sync import series, estimate_offset

FONT = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"
fm.fontManager.addfont(FONT)
plt.rcParams["font.family"] = fm.FontProperties(fname=FONT).get_name()
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 140
plt.rcParams["savefig.bbox"] = "tight"
plt.rcParams["svg.fonttype"] = "path"
plt.rcParams["axes.grid"] = True
plt.rcParams["grid.alpha"] = 0.3
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fig")
C1, C2, C3 = "#2563eb", "#dc2626", "#059669"

R = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "summary.json")))
SETTLE = 0.30       # 정지 판정 후 제외할 정착 시간 [s]


def crosscheck(run, off):
    d = series(run)
    tc = d["tc"] - off
    gmm = mm_from_gpo(d["ctrl"]["POS"])
    lo = max(tc[0], d["tm"][0]); hi = min(tc[-1], d["tm"][-1])
    g = np.arange(lo, hi, 0.01)
    laser = np.interp(g, d["tm"], d["sm"])
    gm = np.interp(g, tc, gmm)
    k, b = np.polyfit(gm, laser, 1)
    lm = (laser - b) / k                       # 레이저 → mm 환산(스케일 1회 정합)
    vel = np.abs(np.gradient(gm, 0.01))
    stat = vel < 0.5
    idx = np.where(stat)[0]
    segs = np.split(idx, np.where(np.diff(idx) > 1)[0] + 1)
    pts = []
    for s in segs:
        if len(s) < int(SETTLE * 100) + 30:
            continue
        s = s[int(SETTLE * 100):]
        pts.append((float(gm[s].mean()), float(lm[s].mean()), len(s) / 100.0))
    pts = np.array([(a, b_, c) for a, b_, c in pts])
    err = pts[:, 1] - pts[:, 0]
    return dict(d=d, g=g, gm=gm, lm=lm, pts=pts, err=err, k=k,
                stats=dict(n_seg=len(pts), overlap_s=round(len(g) / 100, 1),
                           slope=round(float(k), 4),
                           r=round(float(np.corrcoef(gm, laser)[0, 1]), 5),
                           rmse_mm=round(float(np.sqrt((err ** 2).mean())), 3),
                           bias_mm=round(float(err.mean()), 3),
                           max_abs_mm=round(float(np.abs(err).max()), 3),
                           span_mm=round(float(pts[:, 0].max() - pts[:, 0].min()), 2)))


out = {}
for run in ["08", "09"]:
    off = R["offset"][run]
    c = crosscheck(run, off)
    out[run] = c["stats"]
    out[run]["offset_s"] = off
    print(run, c["stats"])

# ── 09 그림 재생성 (동기화 시계열 + 정지구간 잔차)
c = crosscheck("09", R["offset"]["09"])
fig, ax = plt.subplots(1, 2, figsize=(10, 3.4), gridspec_kw={"width_ratios": [1.75, 1]})
ax[0].plot(c["g"], c["gm"], color=C1, lw=1.1, label="gPO 환산 개구 (제어 노트북)")
ax[0].plot(c["g"], c["lm"], color=C2, lw=0.9, ls="--", label="레이저 실측 개구 (측정장비)")
ax[0].set_xlabel("측정장비 시간 [s]   (제어 로그 -%.2f s 정합)" % R["offset"]["09"])
ax[0].set_ylabel("개구 [mm]"); ax[0].legend(fontsize=8, loc="lower left")
ax[0].set_title("동기화된 개구 시계열 — 미학습 조합 10종 × 2회", fontsize=10)
sc = ax[1].scatter(c["pts"][:, 0], c["err"], c=c["pts"][:, 2], cmap="viridis", s=26)
ax[1].axhline(0, color="gray", lw=0.8)
ax[1].axhspan(-0.5, 0.5, color=C3, alpha=0.12)
ax[1].text(2, 0.53, "합격 기준 ±0.5 mm", fontsize=7.5, color=C3)
ax[1].set_xlabel("개구 [mm]"); ax[1].set_ylabel("레이저 - gPO환산 [mm]")
ax[1].set_title("정지구간 편차  RMSE %.3f mm" % out["09"]["rmse_mm"], fontsize=10)
fig.colorbar(sc, ax=ax[1], label="정지 길이 [s]")
fig.suptitle("09. 미학습 조합 — 두 계통 교차 검증", fontsize=11)
fig.savefig(f"{OUT}/09.svg"); plt.close(fig)

# ── 08 그림 (무부하 대조군 동기화)
c8 = crosscheck("08", R["offset"]["08"])
d8 = c8["d"]
fig, ax = plt.subplots(1, 2, figsize=(10, 3.3), gridspec_kw={"width_ratios": [1.75, 1]})
ax[0].plot(c8["g"], c8["gm"], color=C1, lw=1.1, label="gPO 환산 개구")
ax[0].plot(c8["g"], c8["lm"], color=C2, lw=0.9, ls="--", label="레이저 실측 개구")
ax2 = ax[0].twinx()
ax2.plot(d8["tc"] - R["offset"]["08"], d8["ctrl"]["OBJ"], color=C3, lw=0.8, alpha=0.75)
ax2.set_ylabel("gOBJ", color=C3); ax2.set_ylim(-0.2, 3.6); ax2.grid(False)
ax[0].set_xlabel("측정장비 시간 [s]   (제어 로그 -%.2f s 정합)" % R["offset"]["08"])
ax[0].set_ylabel("개구 [mm]"); ax[0].legend(fontsize=8, loc="center left")
ax[0].set_title("동기화된 개구와 gOBJ — 무부하 폐합", fontsize=10)
res = load_result(sorted(__import__("glob").glob(os.path.join(CTRL, "08_*", "*_result.csv")))[0])
sp = [int(r["rSP"]) for r in res]
ev = load_events(sorted(__import__("glob").glob(os.path.join(CTRL, "08_*", "*_events.csv")))[0])
lat = {}
cmd = None; key = None
for t, n in ev:
    if n.endswith("_cmd"):
        cmd = t; key = int(n.split("rSP")[1].split("_")[0])
    elif "_obj3" in n and cmd:
        lat.setdefault(key, []).append((t - cmd).total_seconds() * 1000); cmd = None
ks = sorted(lat)
ax[1].bar([str(k) for k in ks], [np.mean(lat[k]) for k in ks],
          yerr=[np.std(lat[k]) for k in ks], color=C1, capsize=3)
ax[1].set_xlabel("rSP [count]"); ax[1].set_ylabel("지령 → gOBJ=3 [ms]")
ax[1].set_title("목표 도달 판정 시간", fontsize=10)
fig.suptitle("08. 무부하 대조군", fontsize=11)
fig.savefig(f"{OUT}/08.svg"); plt.close(fig)
out["08"]["arrive_by_rsp"] = {str(k): [round(float(np.mean(lat[k])), 1),
                                        round(float(np.std(lat[k])), 1)] for k in ks}

R["sync"] = out
json.dump(R, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "summary.json"), "w"),
          ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
