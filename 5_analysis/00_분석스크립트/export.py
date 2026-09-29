"""분석 산출물 폴더 생성 — 런별 결과 문서 · 그래프 · 지표 CSV · 동기화 데이터."""
import csv, glob, json, os, shutil
import numpy as np
from common import *
from sync import series

HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "summary.json")))
DST = OUT
os.makedirs(DST, exist_ok=True)

RUNS = {
    "02": ("무부하_끝점", ["02"]),
    "03": ("버니어_보정", ["03"]),
    "04": ("속도_스텝응답", ["04"]),
    "05": ("힘_거동", ["05", "05b"]),
    "07": ("물체감지_타이밍", ["07"]),
    "08": ("무부하_대조군", ["08"]),
    "09": ("미학습_조합_검증", ["09", "09b"]),
    "10": ("파지_시나리오", ["10"]),
}
FIGNAME = {"02": "02_스트로크", "03": "03_보정커브", "04": "04_속도커브",
           "05": "05_동기화_힘시계열", "05b": "05_rFR_파지력",
           "07": "07_디바운스", "08": "08_도달판정시간",
           "09": "09_동기화_개구", "09b": "09_정지구간_편차",
           "10": "10_시나리오_타임라인"}


def wcsv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def rundir(key):
    d = os.path.join(DST, f"{key}_{RUNS[key][0]}")
    os.makedirs(d, exist_ok=True)
    return d


# ── 그래프 복사
for key, (_, figs) in RUNS.items():
    d = rundir(key)
    for fg in figs:
        for ext, src in ((".png", f"fig/{fg}.png"), (".svg", f"svg/{fg}.svg")):
            s = os.path.join(HERE, src)
            if os.path.exists(s):
                shutil.copy(s, os.path.join(d, FIGNAME[fg] + ext))

# ── 분석 스크립트 복사
sd = os.path.join(DST, "00_분석스크립트")
os.makedirs(sd, exist_ok=True)
for f in ["common.py", "sync.py", "analyze.py", "refine.py", "makesvg.py", "svgchart.py"]:
    shutil.copy(os.path.join(HERE, f), os.path.join(sd, f))
json.dump(R, open(os.path.join(DST, "summary.json"), "w"), ensure_ascii=False, indent=1)

# ── 동기화 오프셋
od = os.path.join(DST, "90_동기화")
os.makedirs(od, exist_ok=True)
wcsv(os.path.join(od, "시계_오프셋.csv"),
     ["run", "offset_s", "설명"],
     [[k, v, "제어 로그 시각 - offset = 측정장비 시각"] for k, v in R["offset"].items()]
     + [["평균", round(float(np.mean(list(R["offset"].values()))), 3), ""]])


def merged(run, extra_force=True):
    """동기화된 병합 시계열 생성 (측정장비 시간축 100 Hz)."""
    d = series(run)
    off = R["offset"][run]
    tc = d["tc"] - off
    lo = max(tc[0], d["tm"][0]); hi = min(tc[-1], d["tm"][-1])
    g = np.arange(lo, hi, 0.01)
    pos = np.interp(g, tc, d["ctrl"]["POS"])
    obj = np.interp(g, tc, d["ctrl"]["OBJ"])
    cur = np.interp(g, tc, d["ctrl"]["CUR"])
    laser = np.interp(g, d["tm"], d["sm"])
    gm = mm_from_gpo(pos)
    k, b = np.polyfit(gm, laser, 1)
    lm = (laser - b) / k
    rows = [np.round(g, 3), np.round(pos, 1), np.round(obj, 1), np.round(cur, 1),
            np.round(gm, 4), np.round(lm, 4), np.round(lm - gm, 4)]
    hdr = ["t_meas_s", "gPO", "gOBJ", "gCU", "개구_gPO환산_mm", "개구_레이저_mm", "편차_mm"]
    if extra_force:
        F = grip_force(d["hdr"], d["a"])
        F -= np.median(F[:300])
        rows.append(np.round(np.interp(g, d["tm"], F), 3))
        hdr.append("파지력_N")
    return hdr, list(zip(*rows)), off


for run in ["05", "07", "09"]:
    hdr, rows, off = merged(run)
    wcsv(os.path.join(od, f"{run}_동기화_시계열.csv"), hdr, rows)
    print(f"{run} 동기화 시계열 {len(rows)}행 (offset {off:.2f}s)")

# ── 02
d = rundir("02")
rows = []
for f in sorted(glob.glob(os.path.join(CTRL, "02_*", "*_result.csv"))):
    stamp = os.path.basename(f).split("_")[2] + "_" + os.path.basename(f).split("_")[3]
    for r in load_result(f):
        rows.append([stamp, r["rep"], r["gPO_open"], r["gPO_closed"]])
wcsv(os.path.join(d, "02_끝점_전체.csv"), ["런", "rep", "gPO_open", "gPO_closed"], rows)

# ── 03
d = rundir("03")
rr = load_result(sorted(glob.glob(os.path.join(CTRL, "03_*", "*_result.csv")))[0])
A, B = R["03"]["A"], R["03"]["B"]
rows = [[r["direction"], r["rPR"], r["gPO"], r["caliper_mm_mean"],
         round(A + B * float(r["gPO"]), 4),
         round(float(r["caliper_mm_mean"]) - (A + B * float(r["gPO"])), 4)] for r in rr]
wcsv(os.path.join(d, "03_보정_데이터.csv"),
     ["방향", "rPR", "gPO", "실측개구_mm", "회귀예측_mm", "잔차_mm"], rows)
wcsv(os.path.join(d, "03_히스테리시스.csv"), ["rPR", "닫힘-열림_mm"],
     [[k, round(v, 4)] for k, v in sorted(R["03"]["hyst"].items(), key=lambda x: int(x[0]))])

# ── 04
d = rundir("04")
wcsv(os.path.join(d, "04_속도커브.csv"),
     ["rSP", "n", "이동시간_평균_s", "이동시간_표준편차_s", "속도_mm_s", "속도_표준편차_mm_s"],
     [[r["rSP"], r["n"], r["t_mean"], r["t_sd"], r["v_mean"], r["v_sd"]] for r in R["04"]["rows"]])

# ── 05
d = rundir("05")
wcsv(os.path.join(d, "05_rFR별_파지력.csv"),
     ["rFR", "n", "파지력_평균_N", "파지력_표준편차_N", "gPO_정지", "정지개구_mm", "사양식_N"],
     [[r["rFR"], r["n"], r["F_mean"], r["F_sd"], r["gPO_stop"], r["opening_mm"],
       round(20 + (185 - 20) * r["rFR"] / 255, 1)] for r in R["05"]["rows"]])

# ── 07
d = rundir("07")
rr = load_result(sorted(glob.glob(os.path.join(CTRL, "07_*", "*_result.csv")))[0])
wcsv(os.path.join(d, "07_디바운스_전체.csv"),
     ["rFR", "rSP", "rep", "gOBJ", "gPO_stop", "개구_mm", "디바운스_ms"],
     [[r["rFR"], r["rSP"], r["rep"], r["gOBJ"], r["gPO_stop"],
       round(float(mm_from_gpo(float(r["gPO_stop"]))), 2), r["debounce_ms"]] for r in rr])

# ── 08
d = rundir("08")
wcsv(os.path.join(d, "08_도달판정시간.csv"),
     ["rSP", "지령_gOBJ3_평균_ms", "표준편차_ms", "04_전행정_이동시간_ms"],
     [[k, v[0], v[1], round(next(x["t_mean"] for x in R["04"]["rows"] if x["rSP"] == int(k)) * 1000, 0)]
      for k, v in R["sync"]["08"]["arrive_by_rsp"].items()])

# ── 09
d = rundir("09")
rr = load_result(sorted(glob.glob(os.path.join(CTRL, "09_*", "*_result.csv")))[0])
wcsv(os.path.join(d, "09_조합별_결과.csv"),
     ["combo_id", "rep", "rPR", "rSP", "rFR", "gOBJ", "gPO_final", "추종오차_count", "예측개구_mm"],
     [[r["combo_id"], r["rep"], r["rPR"], r["rSP"], r["rFR"], r["gOBJ"], r["gPO_final"],
       int(r["gPO_final"]) - int(r["rPR"]),
       round(float(mm_from_gpo(float(r["gPO_final"]))), 2)] for r in rr])

# ── 10
d = rundir("10")
rr = load_result(sorted(glob.glob(os.path.join(CTRL, "10_*", "*scenario*_result.csv")))[0])
wcsv(os.path.join(d, "10_시나리오_결과.csv"), list(rr[0].keys()),
     [list(r.values()) for r in rr])

print("완료:", DST)
