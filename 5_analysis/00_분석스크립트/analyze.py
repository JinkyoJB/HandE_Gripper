"""Hand-E 실험 결과 분석 — 측정장비/제어 로그 동기화 + 런별 지표 산출 + 그림 생성."""
import glob, json, os, datetime as dt
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

from common import *
from sync import series, estimate_offset, onsets

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
os.makedirs(OUT, exist_ok=True)
R = {}          # 결과 요약

C1, C2, C3 = "#2563eb", "#dc2626", "#059669"

# ───────────────────────────────────────────── 0. 시계 오프셋
OFF = {}
for run in ["05", "07", "09"]:
    d = series(run)
    off, sc, _ = estimate_offset(d)
    OFF[run] = off
base = float(np.mean(list(OFF.values())))
d8 = series("08")
off8, sc8, _ = estimate_offset(d8, lo=base - 3, hi=base + 3, step=0.01)
OFF["08"] = off8
R["offset"] = {k: round(v, 2) for k, v in OFF.items()}
R["offset_mean"] = round(base, 2)

# ───────────────────────────────────────────── 02
res02 = []
for f in sorted(glob.glob(os.path.join(CTRL, "02_*", "*_result.csv"))):
    for row in load_result(f):
        res02.append((int(row["gPO_open"]), int(row["gPO_closed"])))
op = np.array([x[0] for x in res02]); cl = np.array([x[1] for x in res02])
iv, hdr, a, t0 = load_clavis(sorted(glob.glob(os.path.join(MEAS, "02_*", "*.csv")))[-1])
L1, L2, _ = clavis_opening(hdr, a)
s02 = -(L1 + L2); s02 -= np.nanmin(s02)
stroke_meas = float(np.nanmax(s02))
R["02"] = dict(n_runs=len(glob.glob(os.path.join(CTRL, "02_*", "*_result.csv"))),
                n_rep=len(res02),
                gPO_open_mean=float(op.mean()), gPO_open_sd=float(op.std()),
                gPO_closed_mean=float(cl.mean()), gPO_closed_sd=float(cl.std()),
                span_count=float(cl.mean() - op.mean()),
                laser_stroke_mm=round(stroke_meas, 3),
                meas_dur_s=round(len(a) * iv, 1))

fig, ax = plt.subplots(1, 2, figsize=(9.5, 3.3), gridspec_kw={"width_ratios": [1, 1.5]})
ax[0].plot(np.arange(1, len(op) + 1), op, "o-", color=C1, label="gPO_open")
ax[0].plot(np.arange(1, len(cl) + 1), cl, "s-", color=C2, label="gPO_closed")
ax[0].set_xlabel("반복 회차 (13런 × 5회)"); ax[0].set_ylabel("gPO [count]")
ax[0].set_ylim(-10, 260); ax[0].legend(fontsize=8); ax[0].set_title("끝점 재현성", fontsize=10)
ax[1].plot(np.arange(len(s02))[::3] * iv, s02[::3], color=C3, lw=0.8)
ax[1].axhline(stroke_meas, ls="--", color="gray", lw=0.8)
ax[1].text(1, stroke_meas - 3.5, f"실측 스트로크 {stroke_meas:.2f} mm", fontsize=8)
ax[1].set_xlabel("측정장비 시간 [s]"); ax[1].set_ylabel("개구 변화량 [mm]")
ax[1].set_title("레이저 변위 — 무부하 전개폐", fontsize=10)
fig.suptitle("02. 무부하 끝점", fontsize=11)
fig.savefig(f"{OUT}/02.svg"); plt.close(fig)

# ───────────────────────────────────────────── 03
rows = load_result(sorted(glob.glob(os.path.join(CTRL, "03_*", "*_result.csv")))[0])
dirn = np.array([r["direction"] for r in rows])
rpr = np.array([float(r["rPR"]) for r in rows])
gpo = np.array([float(r["gPO"]) for r in rows])
mm = np.array([float(r["caliper_mm_mean"]) for r in rows])
B, A = np.polyfit(gpo, mm, 1)
pred = A + B * gpo
resid = mm - pred
ss = 1 - resid.var() / mm.var()
cm = dirn == "closing"; om_ = dirn == "opening"
hyst = {}
for p in sorted(set(rpr[cm])):
    hyst[int(p)] = float(mm[cm & (rpr == p)][0] - mm[om_ & (rpr == p)][0])
R["03"] = dict(A=round(A, 4), B=round(B, 5), R2=round(float(ss), 6),
                resid_max=round(float(np.abs(resid).max()), 4),
                resid_rms=round(float(np.sqrt((resid ** 2).mean())), 4),
                mm_per_count=round(abs(B), 5),
                hyst=hyst, hyst_max=round(max(abs(v) for v in hyst.values()), 3),
                hyst_mean=round(float(np.mean([abs(v) for v in hyst.values()])), 3),
                gpo_eq_rpr=bool(np.all(gpo == rpr)),
                span_mm=round(float(A + B * 3 - (A + B * 249)), 3))

fig, ax = plt.subplots(1, 2, figsize=(9.5, 3.4), gridspec_kw={"width_ratios": [1.4, 1]})
ax[0].plot(gpo[cm], mm[cm], "o", color=C1, label="닫힘 방향")
ax[0].plot(gpo[om_], mm[om_], "s", color=C2, mfc="none", label="열림 방향")
xs = np.linspace(0, 255, 50)
ax[0].plot(xs, A + B * xs, "-", color="gray", lw=1,
           label=f"개구 = {A:.3f} {B:+.4f}·gPO\n$R^2$={ss:.5f}")
ax[0].set_xlabel("gPO [count]"); ax[0].set_ylabel("버니어 실측 개구 [mm]")
ax[0].legend(fontsize=8); ax[0].set_title("count↔mm 보정 커브", fontsize=10)
ks = sorted(hyst); vs = [hyst[k] for k in ks]
ax[1].bar([str(k) for k in ks], vs, color=C3)
ax[1].set_xlabel("rPR [count]"); ax[1].set_ylabel("닫힘 - 열림 [mm]")
ax[1].set_title("방향별 차이(히스테리시스)", fontsize=10)
fig.suptitle("03. 버니어 보정", fontsize=11)
fig.savefig(f"{OUT}/03.svg"); plt.close(fig)

# ───────────────────────────────────────────── 04
rows = load_result(sorted(glob.glob(os.path.join(CTRL, "04_*", "*_result.csv")))[0])
sp = np.array([float(r["rSP"]) for r in rows])
tt = np.array([float(r["move_time_s"]) for r in rows])
span = R["03"]["span_mm"]
lv = sorted(set(sp))
tab04 = []
for v in lv:
    m = sp == v
    tab04.append(dict(rSP=int(v), n=int(m.sum()), t_mean=round(float(tt[m].mean()), 4),
                      t_sd=round(float(tt[m].std()), 4),
                      v_mean=round(float(span / tt[m].mean()), 2),
                      v_sd=round(float(span / tt[m].mean() ** 2 * tt[m].std()), 2)))
R["04"] = dict(rows=tab04, span_mm=span,
                sat_gain=round(tab04[-1]["v_mean"] - tab04[-2]["v_mean"], 2),
                v_min=tab04[0]["v_mean"], v_max=tab04[-1]["v_mean"])

fig, ax = plt.subplots(1, 2, figsize=(9.5, 3.3))
ax[0].errorbar([r["rSP"] for r in tab04], [r["t_mean"] for r in tab04],
               yerr=[r["t_sd"] for r in tab04], fmt="o-", color=C1, capsize=3)
ax[0].set_xlabel("rSP [count]"); ax[0].set_ylabel("전행정 이동시간 [s]")
ax[0].set_title("스텝 이동시간", fontsize=10)
ax[1].errorbar([r["rSP"] for r in tab04], [r["v_mean"] for r in tab04],
               yerr=[r["v_sd"] for r in tab04], fmt="s-", color=C2, capsize=3)
ax[1].axhspan(20, 150, color="gray", alpha=0.12)
ax[1].text(35, 152, "공칭 20~150 mm/s", fontsize=8, color="dimgray")
ax[1].annotate("192 이상 포화", xy=(192, tab04[-2]["v_mean"]), xytext=(120, 40),
               fontsize=8, arrowprops=dict(arrowstyle="->", lw=0.8))
ax[1].set_xlabel("rSP [count]"); ax[1].set_ylabel("평균 개폐 속도 [mm/s]")
ax[1].set_title("rSP ↔ 속도 커브", fontsize=10)
fig.suptitle("04. 속도·스텝응답", fontsize=11)
fig.savefig(f"{OUT}/04.svg"); plt.close(fig)

# ───────────────────────────────────────────── 05 (동기화: 힘)
d = series("05"); off = OFF["05"]
evs = load_events(d["ev"][0])
Fsum = grip_force(d["hdr"], d["a"])     # ISO 18646-3 : 두 로드셀의 합
holds = {}
for t, name in evs:
    if "hold_start" in name:
        lvl = int(name.split("_")[0].split("=")[1]); rep = int(name.split("_")[1][3:])
        holds[(lvl, rep)] = [(t - d["t0"]).total_seconds() - off, None]
    if "hold_end" in name:
        lvl = int(name.split("_")[0].split("=")[1]); rep = int(name.split("_")[1][3:])
        if (lvl, rep) in holds:
            holds[(lvl, rep)][1] = (t - d["t0"]).total_seconds() - off
tab05 = {}
for (lvl, rep), (a0, a1) in sorted(holds.items()):
    if a1 is None: continue
    m = (d["tm"] >= a0 + 1.0) & (d["tm"] <= a1 - 0.5)
    if m.sum() < 50: continue
    tab05.setdefault(lvl, []).append(float(np.mean(Fsum[m])))
res05 = load_result([f for f in d["res"] if "precheck" not in f][0])
gstop = {int(r["rFR"]): int(r["gPO_stop"]) for r in res05}
rows05 = []
for lvl in sorted(tab05):
    v = np.array(tab05[lvl])
    rows05.append(dict(rFR=lvl, n=len(v), F_mean=round(float(v.mean()), 2),
                       F_sd=round(float(v.std()), 2), gPO_stop=gstop.get(lvl),
                       opening_mm=round(float(mm_from_gpo(gstop.get(lvl))), 2)))
spec = {0: 20, 255: 185}
R["05"] = dict(rows=rows05, cur_supported=bool(np.nanmax(d["ctrl"]["CUR"]) > 0),
                gOBJ_all=int(res05[0]["gOBJ"]),
                F_ratio=round(rows05[-1]["F_mean"] / rows05[0]["F_mean"], 2),
                spec_ratio=round(185 / 20, 2),
                n_grasp=sum(r["n"] for r in rows05))

fig, ax = plt.subplots(1, 2, figsize=(10, 3.4), gridspec_kw={"width_ratios": [1.7, 1]})
ax[0].plot(d["tm"][::3], Fsum[::3], color=C2, lw=0.7)
for (lvl, rep), (a0, a1) in sorted(holds.items()):
    if a1 is None: continue
    ax[0].axvspan(a0, a1, color=C1, alpha=0.10)
    if rep == 2:
        ax[0].text((a0 + a1) / 2, Fsum.max() * 1.02, f"rFR={lvl}", ha="center", fontsize=8)
ax[0].set_xlabel("측정장비 시간 [s]  (제어 로그 -%.2f s 정합)" % off)
ax[0].set_ylabel("파지력 [N]"); ax[0].set_title("힘 시계열과 유지구간", fontsize=10)
ax[0].set_xlim(0, min(d["tm"][-1], 180))
x = [r["rFR"] for r in rows05]; y = [r["F_mean"] for r in rows05]
ax[1].errorbar(x, y, yerr=[r["F_sd"] for r in rows05], fmt="o-", color=C2, capsize=3, label="실측")
ax[1].plot([0, 255], [20, 185], "--", color="gray", lw=1, label="Robotiq 사양식")
ax[1].set_xlabel("rFR [count]"); ax[1].set_ylabel("파지력 [N]")
ax[1].legend(fontsize=8); ax[1].set_title("rFR ↔ 파지력", fontsize=10)
fig.suptitle("05. 힘 거동", fontsize=11)
fig.savefig(f"{OUT}/05.svg"); plt.close(fig)

# ───────────────────────────────────────────── 07
rows = load_result(sorted(glob.glob(os.path.join(CTRL, "07_*", "*_result.csv")))[0])
deb = np.array([float(r["debounce_ms"]) for r in rows if r["debounce_ms"]])
gst = np.array([float(r["gPO_stop"]) for r in rows])
obj = np.array([int(r["gOBJ"]) for r in rows])
by_sp = {}
for r in rows:
    if r["debounce_ms"]:
        by_sp.setdefault(int(r["rSP"]), []).append(float(r["debounce_ms"]))
d7 = series("07"); off7 = OFF["07"]
F7 = grip_force(d7["hdr"], d7["a"])
R["07"] = dict(n=len(rows), obj2_rate=float((obj == 2).mean()),
                deb_n=len(deb), deb_mean=round(float(deb.mean()), 1),
                deb_sd=round(float(deb.std()), 1),
                deb_min=round(float(deb.min()), 1), deb_max=round(float(deb.max()), 1),
                gPO_stop_min=int(gst.min()), gPO_stop_max=int(gst.max()),
                opening_mm=round(float(mm_from_gpo(gst.mean())), 2),
                by_sp={k: [round(float(np.mean(v)), 1), round(float(np.std(v)), 1), len(v)]
                       for k, v in sorted(by_sp.items())},
                F_peak=round(float(np.nanmax(F7)), 1))

fig, ax = plt.subplots(1, 2, figsize=(9.8, 3.3), gridspec_kw={"width_ratios": [1, 1.3]})
ax[0].hist(deb, bins=8, color=C1, edgecolor="white")
ax[0].axvline(deb.mean(), color=C2, ls="--", lw=1)
ax[0].text(deb.mean() + 0.4, ax[0].get_ylim()[1] * 0.85,
           f"평균 {deb.mean():.1f} ms", fontsize=8, color=C2)
ax[0].set_xlabel("gPO 정지 → gOBJ=2 지연 [ms]"); ax[0].set_ylabel("빈도")
ax[0].set_title(f"디바운스 분포 (n={len(deb)})", fontsize=10)
ax[1].plot(d7["tm"][::2], F7[::2], color=C2, lw=0.7, label="파지력 [N]")
ax2 = ax[1].twinx()
ax2.plot(d7["tc"] - off7, d7["ctrl"]["POS"], color=C1, lw=0.7, label="gPO")
ax2.set_ylabel("gPO [count]", color=C1)
ax[1].set_xlim(20, 50); ax[1].set_xlabel("측정장비 시간 [s]"); ax[1].set_ylabel("파지력 [N]", color=C2)
ax[1].set_title("동기화 — 힘(측정장비) vs gPO(제어)", fontsize=10)
fig.suptitle("07. 물체감지 타이밍", fontsize=11)
fig.savefig(f"{OUT}/07.svg"); plt.close(fig)

# ───────────────────────────────────────────── 08
rows = load_result(sorted(glob.glob(os.path.join(CTRL, "08_*", "*_result.csv")))[0])
g8 = np.array([int(r["gPO_stop"]) for r in rows]); o8 = np.array([int(r["gOBJ"]) for r in rows])
evs8 = load_events(sorted(glob.glob(os.path.join(CTRL, "08_*", "*_events.csv")))[0])
lat = []
cmd = None
for t, n in evs8:
    if n.endswith("_cmd"): cmd = t
    elif "_obj3" in n and cmd: lat.append((t - cmd).total_seconds() * 1000); cmd = None
R["08"] = dict(n=len(rows), obj3_rate=float((o8 == 3).mean()),
                gPO_stop=sorted(set(int(x) for x in g8)),
                gPO_mode=int(np.bincount(g8).argmax()),
                arrive_ms_mean=round(float(np.mean(lat)), 1),
                arrive_ms_min=round(float(np.min(lat)), 1),
                arrive_ms_max=round(float(np.max(lat)), 1))

# ───────────────────────────────────────────── 09 (동기화 검증)
d9 = series("09"); off9 = OFF["09"]
tc9 = d9["tc"] - off9
gmm = mm_from_gpo(d9["ctrl"]["POS"])
lo = max(tc9[0], d9["tm"][0]); hi = min(tc9[-1], d9["tm"][-1])
g = np.arange(lo, hi, 0.01)
laser = np.interp(g, d9["tm"], d9["sm"])
gm = np.interp(g, tc9, gmm)
k9, b9 = np.polyfit(gm, laser, 1)
laser_mm = (laser - b9) / k9
err = laser_mm - gm
rmse9 = float(np.sqrt((err ** 2).mean()))
# 기울기 1 고정(오프셋만 정합) — 절대 일치도
laser_u = laser - laser.mean() + gm.mean()
err_u = laser_u - gm
# 정지 구간(개구 변화 없음)만
vel = np.abs(np.gradient(gm, 0.01))
stat = vel < 1.0
rmse_stat = float(np.sqrt((err[stat] ** 2).mean()))
rmse_u_stat = float(np.sqrt((err_u[stat] ** 2).mean()))
rows = load_result(sorted(glob.glob(os.path.join(CTRL, "09_*", "*_result.csv")))[0])
rpr9 = np.array([int(r["rPR"]) for r in rows]); fin9 = np.array([int(r["gPO_final"]) for r in rows])
R["09"] = dict(n=len(rows), track_err_max=int(np.abs(fin9 - rpr9).max()),
                obj_all=int(np.bincount([int(r["gOBJ"]) for r in rows]).argmax()),
                slope=round(float(k9), 4), r=round(float(np.corrcoef(gm, laser)[0, 1]), 5),
                rmse_mm=round(rmse9, 3), overlap_s=round(len(g) / 100, 1),
                err_p95=round(float(np.percentile(np.abs(err), 95)), 3),
                rmse_stat_mm=round(rmse_stat, 3), rmse_slope1_stat_mm=round(rmse_u_stat, 3),
                stat_frac=round(float(stat.mean()), 3))

fig, ax = plt.subplots(1, 2, figsize=(10, 3.4), gridspec_kw={"width_ratios": [1.7, 1]})
ax[0].plot(g, gm, color=C1, lw=1.0, label="gPO 환산 개구 (제어)")
ax[0].plot(g, laser_mm, color=C2, lw=0.9, ls="--", label="레이저 실측 개구 (측정장비)")
ax[0].set_xlabel("측정장비 시간 [s]  (제어 로그 -%.2f s 정합)" % off9)
ax[0].set_ylabel("개구 [mm]"); ax[0].legend(fontsize=8)
ax[0].set_title("동기화된 개구 — 미학습 조합 10종", fontsize=10)
ax[1].hist(err, bins=40, color=C3, edgecolor="white")
ax[1].set_xlabel("레이저 - gPO환산 [mm]"); ax[1].set_ylabel("표본 수")
ax[1].set_title(f"편차 — 전체 RMSE {rmse9:.2f} mm / 정지구간 {rmse_stat:.2f} mm", fontsize=9)
fig.suptitle("09. 미학습 조합 — 교차 검증", fontsize=11)
fig.savefig(f"{OUT}/09.svg"); plt.close(fig)

# ───────────────────────────────────────────── 10
rows = load_result(sorted(glob.glob(os.path.join(CTRL, "10_*", "*scenario*_result.csv")))[0])
R["10"] = dict(n=len(rows),
                gPO=[int(r["gPO_grasp"]) for r in rows],
                opening=[float(r["opening_mm"]) for r in rows],
                grasp_ms=[float(r["grasp_time_ms"]) for r in rows],
                drift=[int(r["gPO_drift"]) for r in rows],
                held=[r["all_phases_held"] for r in rows],
                checks=[int(r["n_phase_checks"]) for r in rows],
                cur_peak=[int(r["CUR_peak_close"]) for r in rows])
raw10 = sorted(glob.glob(os.path.join(CTRL, "10_*", "handE_10_20260722_1630.csv")))[0]
c10 = load_ctrl(raw10)
t10 = np.array([(x - c10["t"][0]).total_seconds() for x in c10["t"]])
fig, ax = plt.subplots(figsize=(9.5, 3.2))
ax.plot(t10[::5], c10["POS"][::5], color=C1, lw=0.7, label="gPO")
ax2 = ax.twinx()
ax2.plot(t10[::5], c10["OBJ"][::5], color=C2, lw=0.7, alpha=0.8, label="gOBJ")
ax2.set_ylim(-0.2, 3.6); ax2.set_ylabel("gOBJ", color=C2)
ax.set_xlabel("경과 시간 [s]"); ax.set_ylabel("gPO [count]", color=C1)
ax.set_title("10. 파지 시나리오 — 3회 반복 전 구간", fontsize=11)
fig.savefig(f"{OUT}/10.svg"); plt.close(fig)

print(json.dumps(R, ensure_ascii=False, indent=1))
