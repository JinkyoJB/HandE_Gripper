import csv, glob, os, datetime as dt
import numpy as np

# 저장소 기준 상대경로. 데이터를 다른 곳에 두었으면 HANDE_DATA_ROOT 로 덮어쓴다.
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
ROOT = os.environ.get("HANDE_DATA_ROOT") or os.path.join(REPO, "4_raw_data")
OUT  = os.path.join(REPO, "5_analysis")          # 분석 산출물 출력 위치
MEAS = os.path.join(ROOT, "1_스마트그리퍼측정장비_데이터")
CTRL = os.path.join(ROOT, "2_로봇_그리퍼_제어_데이터")

# R03 실측 보정식 (r05_precheck.py 에 기록된 값) — 본 분석에서 재도출하여 검증
CAL_A, CAL_B = 53.489, -0.2164


def mm_from_gpo(gpo):
    return CAL_A + CAL_B * np.asarray(gpo, dtype=float)


def load_clavis(path):
    """Clavis SV CSV -> (interval, header list, ndarray, start_datetime)"""
    with open(path, encoding="cp949", errors="replace") as fh:
        lines = fh.read().splitlines()
    iv = float(lines[0])
    hdr = [h.strip() for h in lines[1].split(",") if h.strip()]
    rows = []
    for l in lines[2:]:
        if not l.strip():
            continue
        p = [x for x in l.split(",") if x.strip() != ""]
        if len(p) != len(hdr):
            continue
        rows.append([float(x) for x in p])
    a = np.array(rows)
    base = os.path.basename(path)
    stamp = base[base.rfind("_") + 1: -4]          # "2026-07-22 15-25-45"
    t0 = dt.datetime.strptime(stamp, "%Y-%m-%d %H-%M-%S")
    return iv, hdr, a, t0


def load_ctrl(path):
    """제어 폴링 로그 -> dict of ndarray + datetime array"""
    with open(path, encoding="utf-8-sig") as fh:
        r = list(csv.reader(fh))
    hdr, rows = r[0], r[1:]
    out = {h: [] for h in hdr}
    for row in rows:
        for h, v in zip(hdr, row):
            out[h].append(v)
    t = np.array([dt.datetime.fromisoformat(s) for s in out["wall_time"]])
    d = {"t": t}
    for k in ("POS", "OBJ", "STA", "FLT", "CUR"):
        if k in out:
            d[k] = np.array([float(x) if x != "" else np.nan for x in out[k]])
    d["t_perf"] = np.array([float(x) for x in out["t_perf"]])
    return d


def load_events(path):
    with open(path, encoding="utf-8-sig") as fh:
        r = list(csv.reader(fh))
    return [(dt.datetime.fromisoformat(x[1]), x[2]) for x in r[1:]]


def load_result(path):
    with open(path, encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def clavis_opening(hdr, a):
    """레이저 2채널 -> 개구 상당 신호(mm). 부호/오프셋은 gPO 정합에서 결정."""
    i1 = hdr.index("Laser Disp.#1[mm]")
    i2 = hdr.index("Laser Disp.#2[mm]")
    L1, L2 = a[:, i1].copy(), a[:, i2].copy()
    bad = (L1 < -900) | (L2 < -900)
    L1[bad] = np.nan
    L2[bad] = np.nan
    return L1, L2, bad


def grip_force(hdr, a, tare=300):
    """파지력[N] = 두 로드셀의 합 (KS B ISO 18646-3 5.3.2/5.3.3).

    시편은 원통을 2분할해 로드셀 2EA를 축방향 1/3·2/3 지점에 매설한 구조라
    두 채널은 하나의 조임 하중을 나눠 받는다. 표준도 "두 값의 합"을 규정한다.
    압축이 음수로 들어오므로 부호를 뒤집고, 앞 구간 중앙값으로 영점을 맞춘다.
    """
    i1 = hdr.index("Force 500N #1[N]")
    i2 = hdr.index("Force 500N #2[N]")
    F = -(a[:, i1] + a[:, i2])
    return F - np.median(F[:tare])


def find_files(run):
    md = glob.glob(os.path.join(MEAS, f"*{run}*", "*.csv"))
    meas = [f for f in md if " " in os.path.basename(f)]
    cd = glob.glob(os.path.join(CTRL, f"*{run}*", "*.csv"))
    raw = [f for f in cd if not f.endswith(("_result.csv", "_events.csv"))]
    ev = [f for f in cd if f.endswith("_events.csv")]
    res = [f for f in cd if f.endswith("_result.csv")]
    return sorted(meas), sorted(raw), sorted(ev), sorted(res)
