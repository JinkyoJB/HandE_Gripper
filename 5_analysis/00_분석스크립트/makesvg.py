"""런별 경량 SVG 그래프 생성."""
import glob, json, os
import numpy as np
from common import *
from sync import series, estimate_offset
from svgchart import Chart, decimate, simplify

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "svg"); os.makedirs(OUT, exist_ok=True)
R = json.load(open(os.path.join(HERE, "summary.json")))
BLUE, RED, GREEN, GRAY = "#2563eb", "#dc2626", "#059669", "#94a3b8"


def save(name, svg):
    p = os.path.join(OUT, name)
    open(p, "w", encoding="utf-8").write(svg)
    print(f"{name:10s} {os.path.getsize(p)/1024:6.1f} KiB")


# ── R02 : 레이저 전개폐 궤적
iv, hdr, a, t0 = load_clavis(sorted(glob.glob(os.path.join(MEAS, "R02*", "*.csv")))[-1])
L1, L2, _ = clavis_opening(hdr, a)
s = -(L1 + L2); s -= np.nanmin(s)
t = np.arange(len(a)) * iv
m = (t >= 30) & (t <= 100)
x, y = simplify(t[m], s[m], 0.35)
c = Chart("R02 · 무부하 전개폐 — 레이저 실측 개구", "측정장비 시간 [s]", "개구 변화량 [mm]",
          (30, 100), (-3, 58), note="Clavis SV · 100 Hz")
c.hline(R["R02"]["laser_stroke_mm"], GRAY)
c.line(x, y, GREEN, 1.3)
c.text(32, 54, f'실측 스트로크 {R["R02"]["laser_stroke_mm"]:.2f} mm  (gPO 3↔249)', color="#475569")
save("R02.svg", c.render())

# ── R03 : 보정 커브 + 히스테리시스
rows = load_result(sorted(glob.glob(os.path.join(CTRL, "R03*", "*_result.csv")))[0])
dirn = np.array([r["direction"] for r in rows])
gpo = np.array([float(r["gPO"]) for r in rows])
mm = np.array([float(r["caliper_mm_mean"]) for r in rows])
A, B = R["R03"]["A"], R["R03"]["B"]
c = Chart("R03 · count↔mm 보정 커브 (버니어 실측 14점)", "gPO [count]", "개구 [mm]",
          (0, 260), (0, 56), note=f'개구 = {A:.3f} {B:+.5f}·gPO   R²={R["R03"]["R2"]:.5f}')
c.line([0, 260], [A, A + B * 260], GRAY, 1.4, dash="5 4", label="회귀 직선")
c.scatter(gpo[dirn == "closing"], mm[dirn == "closing"], BLUE, label="닫힘 방향")
c.scatter(gpo[dirn == "opening"], mm[dirn == "opening"], RED, fill=False, label="열림 방향")
c.text(150, 50, f'잔차 RMS {R["R03"]["resid_rms"]:.3f} mm · 최대 {R["R03"]["resid_max"]:.3f} mm', color="#475569")
save("R03.svg", c.render())

hy = R["R03"]["hyst"]
ks = sorted(hy, key=int)
c = Chart("R03 · 방향별 차이 (히스테리시스)", "rPR [count]", "닫힘 - 열림 [mm]",
          (0, 1), (-0.2, 0.22), note=f'평균 |차이| {R["R03"]["hyst_mean"]:.3f} mm')
c.hline(0, "#475569", dash=None)
c.bars(ks, [hy[k] for k in ks], BLUE, fmt="{:+.2f}")
save("R03b.svg", c.render(xcat=True, yticks=np.arange(-0.2, 0.21, 0.1)))

# ── R04 : rSP ↔ 속도
rows04 = R["R04"]["rows"]
xs = [r["rSP"] for r in rows04]; vs = [r["v_mean"] for r in rows04]
c = Chart("R04 · rSP ↔ 평균 개폐 속도", "rSP [count]", "속도 [mm/s]",
          (0, 270), (0, 175), note="전행정 53.24 mm ÷ 이동시간, 각 6회 평균")
c.band(20, 150, GRAY, 0.16, "공칭 20~150 mm/s")
c.line(xs, vs, RED, 1.8)
c.scatter(xs, vs, RED)
for r in rows04:
    c.text(r["rSP"], r["v_mean"] + 8, f'{r["v_mean"]:.1f}', anchor="middle", color="#475569")
c.text(150, 22, "rSP 192 이상 포화 (증가 0.1 mm/s)", color="#475569")
save("R04.svg", c.render())

# ── R05 : 동기화된 힘 시계열
d = series("R05"); off = R["offset"]["R05"]
F = grip_force(d["hdr"], d["a"])
F -= np.median(F[:300])
evs = load_events(d["ev"][0])
holds = {}
for tt, n in evs:
    if "hold_start" in n or "hold_end" in n:
        lv = int(n.split("_")[0].split("=")[1]); rp = int(n.split("_")[1][3:])
        holds.setdefault((lv, rp), {})["s" if "start" in n else "e"] = (tt - d["t0"]).total_seconds() - off
m = (d["tm"] >= 10) & (d["tm"] <= 180)
x, y = simplify(d["tm"][m], F[m], 0.8)
c = Chart("R05 · 동기화된 파지력 시계열 (측정장비) + 유지구간 (제어 로그)",
          "측정장비 시간 [s]", "파지력 [N]", (10, 180), (-5, 92),
          note=f"제어 로그 시각 -{off:.2f} s 정합")
for (lv, rp), v in holds.items():
    if "e" in v:
        c.vband(v["s"], v["e"], BLUE, 0.13)
for lv in [0, 64, 128, 192, 255]:
    ss = [v["s"] for (l, r_), v in holds.items() if l == lv and "e" in v]
    if ss:
        c.text(min(ss) + 12, 88, f"rFR={lv}", anchor="middle", color="#1d4ed8")
c.line(x, y, RED, 1.2)
save("R05.svg", c.render())

# ── R05b : rFR ↔ 파지력
rr = R["R05"]["rows"]
c = Chart("R05 · rFR ↔ 실측 파지력", "rFR [count]", "파지력 [N]", (0, 270), (0, 200),
          note="로드셀 2채널 평균 · 각 3회 10초 유지")
c.line([0, 255], [20, 185], GRAY, 1.4, dash="5 4", label="Robotiq 사양식 20~185 N")
c.line([r["rFR"] for r in rr], [r["F_mean"] for r in rr], RED, 1.8, label="실측")
c.scatter([r["rFR"] for r in rr], [r["F_mean"] for r in rr], RED)
for r in rr:
    c.text(r["rFR"], r["F_mean"] - 14, f'{r["F_mean"]:.0f}', anchor="middle", color="#475569")
save("R05b.svg", c.render())

# ── R07 : 디바운스 산포
rows = load_result(sorted(glob.glob(os.path.join(CTRL, "R07*", "*_result.csv")))[0])
pts = [(int(r["rSP"]), float(r["debounce_ms"])) for r in rows if r["debounce_ms"]]
c = Chart("R07 · gPO 정지 → gOBJ=2 전환 지연 (디바운스)", "rSP [count]", "지연 [ms]",
          (0, 290), (225, 250), note=f'n={len(pts)} · 평균 {R["R07"]["deb_mean"]:.1f} ms (σ {R["R07"]["deb_sd"]:.1f})')
c.hline(R["R07"]["deb_mean"], RED)
jit = {}
for sp, v in pts:
    k = jit.get(sp, 0); jit[sp] = k + 1
    c.scatter([sp + (k - 1) * 7], [v], BLUE, r=3.6)
c.text(10, 248, f'평균 {R["R07"]["deb_mean"]:.1f} ms', color=RED)
save("R07.svg", c.render(yticks=np.arange(225, 251, 5)))

# ── R08 : 도달 판정 시간
ab = R["sync"]["R08"]["arrive_by_rsp"]
ks = sorted(ab, key=int)
c = Chart("R08 · 무부하 폐합 — 지령에서 gOBJ=3 까지", "rSP [count]", "시간 [ms]",
          (0, 1), (0, 2000), note="각 2회 · 물체 없음 판정")
c.bars(ks, [ab[k][0] for k in ks], BLUE, err=[ab[k][1] for k in ks])
save("R08.svg", c.render(xcat=True, yticks=np.arange(0, 2001, 500)))

# ── R09 : 동기화 오버레이
d9 = series("R09"); off9 = R["offset"]["R09"]
tc = d9["tc"] - off9
gmm = mm_from_gpo(d9["ctrl"]["POS"])
lo = max(tc[0], d9["tm"][0]); hi = min(tc[-1], d9["tm"][-1])
g = np.arange(lo, hi, 0.01)
laser = np.interp(g, d9["tm"], d9["sm"]); gm = np.interp(g, tc, gmm)
k9, b9 = np.polyfit(gm, laser, 1); lm = (laser - b9) / k9
lm_s = np.convolve(lm, np.ones(9)/9, mode="same")
x1, y1 = simplify(g, gm, 0.35); x2, y2 = decimate(g[4:-4], lm_s[4:-4], 300)
c = Chart("R09 · 동기화된 개구 — 제어 로그 vs 측정장비", "측정장비 시간 [s]", "개구 [mm]",
          (lo, hi), (-3, 60), note=f"제어 로그 시각 -{off9:.2f} s 정합")
c.line(x1, y1, BLUE, 1.5, label="gPO 환산 개구 (제어)")
c.line(x2, y2, RED, 1.2, dash="4 3", label="레이저 실측 개구 (측정장비)")
save("R09.svg", c.render())

# ── R09b : 정지구간 잔차
from refine import crosscheck  # noqa: E402
cc = crosscheck("R09", off9)
c = Chart("R09 · 정지구간 개구 편차", "개구 [mm]", "레이저 - gPO환산 [mm]",
          (-3, 58), (-0.8, 0.8),
          note=f'RMSE {R["sync"]["R09"]["rmse_mm"]:.3f} mm · 최대 {R["sync"]["R09"]["max_abs_mm"]:.3f} mm · n={R["sync"]["R09"]["n_seg"]}')
c.band(-0.5, 0.5, GREEN, 0.12, "합격 기준 ±0.5 mm")
c.hline(0, "#475569", dash=None)
c.scatter(cc["pts"][:, 0], cc["err"], BLUE, r=3.4)
save("R09b.svg", c.render(yticks=np.arange(-0.8, 0.81, 0.4)))

# ── R10 : 시나리오 타임라인
c10 = load_ctrl(sorted(glob.glob(os.path.join(CTRL, "R10*", "handE_R10_20260722_1630.csv")))[0])
t10 = np.array([(x - c10["t"][0]).total_seconds() for x in c10["t"]])
x, y = simplify(t10, c10["POS"], 1.5)
xo, yo = simplify(t10, c10["OBJ"], 0.5)
c = Chart("R10 · 파지 시나리오 3회 — gPO 와 gOBJ", "경과 시간 [s]", "gPO [count] / gOBJ×60",
          (0, t10[-1]), (-10, 270), note="상승 30 mm → 2시·10시 이동 → joint6 ±90°")
c.line(x, y, BLUE, 1.2, label="gPO")
c.line(xo, yo * 60, GREEN, 1.0, label="gOBJ × 60  (2=파지 유지)")
c.hline(103, GRAY)
c.text(20, 112, "파지 정지 위치 gPO=103 (개구 31.2 mm)", color="#475569")
save("R10.svg", c.render())
