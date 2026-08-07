"""R05 사전 검증 — rFR=0 / rFR=255 각 1회 파지하여 로드셀 값 확인.

본 시험(run.py r05: 15회 × 10초) 전에, 파지력이 로드셀 측정축으로
제대로 전달되는지 확인한다. 안전을 위해 저력(rFR=0)부터 수행한다.

  - 사양상 예상 파지력: rFR=0 → 약 20N, rFR=255 → 약 185N
  - 정지 gPO는 R03 보정식으로 환봉 직경과 대조 (Ø45mm → gPO 약 39)
  - 전류(COU)도 함께 기록 → rFR↔힘↔전류 3자 관계의 예비 확인

실행:  python r05_precheck.py
"""
import csv
import os
import statistics
import time

import config as C
from hande_client import HandE
from logger import timestamp

# R03 실측 보정 커브: 개구(mm) = A + B × gPO
CAL_A, CAL_B = 53.489, -0.2164

HOLD_S = 10.0                      # 유지 시간 (로드셀 정상값 읽기용)
LEVELS = [0, 255]                  # 저력 → 최대력 순서
EXPECT_N = {0: 20, 255: 185}       # Robotiq 사양식 예상값
SPECIMEN_MM = 45.0                 # 환봉 실측 직경 (다르면 수정)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, C.OUTPUT_DIR)


def mm_from_gpo(gpo):
    return CAL_A + CAL_B * gpo


def trial(gr, rfr):
    """rFR 1개 조건으로 1회 파지 → 유지 → 로드셀 값 입력받기."""
    print(f"\n{'='*52}")
    print(f"  rFR={rfr}   (사양 예상 파지력 ≈ {EXPECT_N[rfr]}N)")
    print(f"{'='*52}")
    if rfr == max(LEVELS):
        print("  ⚠ 최대력 시험입니다. 정렬이 확실한지 다시 확인하세요.")
    input(">>> 로드셀 영점(tare) 확인, 환봉 정렬 확인 후 Enter: ")

    gr.move(0, C.R05_SPE, 64)                     # 완전 개방
    gr.wait_arrival(C.MOVE_TIMEOUT_S)
    time.sleep(0.5)

    print("  파지 중...")
    gr.move(255, C.R05_SPE, rfr)                  # 환봉에 걸려 정지
    obj = gr.wait_arrival(C.MOVE_TIMEOUT_S)

    if obj != 2:
        print(f"  ⚠ gOBJ={obj} — 물체 파지로 감지되지 않았습니다 "
              f"(2가 정상). 환봉 위치/정렬을 확인하세요.")

    # 유지하며 전류 수집 + 로드셀 읽을 시간 제공
    print(f"  ▶ {HOLD_S:.0f}초 유지 — 지금 로드셀 표시값을 읽으세요")
    curs = []
    t0 = time.perf_counter()
    next_tick = 1.0
    while True:
        el = time.perf_counter() - t0
        if el >= HOLD_S:
            break
        if gr.cur_var:
            try:
                curs.append(gr.get_var(gr.cur_var))
            except IOError:
                pass
        if el >= next_tick:
            print(f"    {HOLD_S - el:.0f}초 남음")
            next_tick += 2.0
        time.sleep(0.1)

    gpo = gr.get_var("POS")
    obj_end = gr.get_var("OBJ")
    gr.move(0, C.R05_SPE, 64)                     # 개방
    gr.wait_arrival(C.MOVE_TIMEOUT_S)

    opening = mm_from_gpo(gpo)
    cur_mean = statistics.mean(curs) if curs else None
    cur_drift = (max(curs) - min(curs)) if curs else None

    print(f"\n  [측정] gOBJ={obj_end}, 정지 gPO={gpo} → 환산 개구 {opening:.2f}mm "
          f"(환봉 {SPECIMEN_MM:.1f}mm 대비 {opening - SPECIMEN_MM:+.2f}mm)")
    if cur_mean is not None:
        print(f"         전류(COU) 평균={cur_mean:.1f}, 드리프트={cur_drift}")
    else:
        print("         전류 미지원")

    # 로드셀 값 입력
    while True:
        raw = input(f"  >>> 로드셀에서 읽은 파지력(N) 입력 (건너뛰려면 s): ").strip()
        if raw.lower() == "s":
            force = None
            break
        try:
            force = float(raw)
            break
        except ValueError:
            print("      숫자만 입력하세요 (예: 21.5)")

    return {
        "rFR": rfr, "gOBJ": obj_end, "gPO_stop": gpo,
        "opening_mm": round(opening, 2),
        "COU_mean": round(cur_mean, 1) if cur_mean is not None else "",
        "COU_drift": cur_drift if cur_drift is not None else "",
        "force_N": force if force is not None else "",
        "expect_N": EXPECT_N[rfr],
    }


def verdict(rows):
    """정상 여부 판정 — 힘 크기와 개구 환산을 함께 본다."""
    print(f"\n{'='*52}")
    print("  사전 검증 판정")
    print(f"{'='*52}")
    ok = True

    for r in rows:
        # 개구 환산 대조 (R03 커브 교차검증)
        d = r["opening_mm"] - SPECIMEN_MM
        if abs(d) <= 3.0:
            print(f"  ✓ rFR={r['rFR']:3d} 개구 환산 {r['opening_mm']:.2f}mm "
                  f"— 환봉 {SPECIMEN_MM:.1f}mm와 부합 ({d:+.2f}mm)")
        else:
            ok = False
            print(f"  ✗ rFR={r['rFR']:3d} 개구 환산 {r['opening_mm']:.2f}mm "
                  f"— 환봉과 {d:+.2f}mm 차이. 정렬/직경 확인 필요")

        # 파지력 대조
        if r["force_N"] == "":
            print(f"    · rFR={r['rFR']:3d} 로드셀 값 미입력 — 판정 보류")
            continue
        f, e = float(r["force_N"]), r["expect_N"]
        lo, hi = e * 0.5, e * 1.5
        if lo <= f <= hi:
            print(f"  ✓ rFR={r['rFR']:3d} 파지력 {f:.1f}N — 예상 {e}N 대비 정상 범위")
        else:
            ok = False
            print(f"  ✗ rFR={r['rFR']:3d} 파지력 {f:.1f}N — 예상 {e}N에서 크게 벗어남 "
                  f"(허용 {lo:.0f}~{hi:.0f}N). 힘이 로드셀 축으로 전달되는지 확인")

    # 단조성 확인
    fs = [(r["rFR"], r["force_N"]) for r in rows if r["force_N"] != ""]
    if len(fs) == 2 and float(fs[1][1]) <= float(fs[0][1]):
        ok = False
        print(f"  ✗ rFR을 0→255로 올렸는데 파지력이 증가하지 않음 "
              f"({fs[0][1]}N → {fs[1][1]}N). 힘 명령이 반영되지 않는 상태")

    print()
    if ok:
        print("  ▶ 판정: 정상 — 본 시험(R05_실행.bat) 진행 가능")
    else:
        print("  ▶ 판정: 이상 — 위 항목 점검 후 재실행 권장 (본 시험 전 해결 필요)")
    return ok


def main():
    print("=" * 52)
    print("  R05 사전 검증 — 로드셀 힘 전달 확인")
    print("  rFR=0(저력) → rFR=255(최대력) 순서로 각 1회 파지")
    print("=" * 52)

    rows = []
    with HandE(C.ROBOT_IP, C.GRIPPER_PORT, C.SOCKET_TIMEOUT) as gr:
        print("\n[공통] rACT 재활성화 (자가 캘리브레이션)...")
        gr.activate()
        gr.probe()
        print(f"[공통] 전류 변수: {gr.cur_var or '미지원'}")
        flt = gr.get_var("FLT")
        if flt != 0:
            print(f"⚠ gFLT={flt} — 매뉴얼 4장 점검 권장")

        for rfr in LEVELS:
            rows.append(trial(gr, rfr))

        gr.move(0, 128, 64)
        gr.wait_arrival(C.MOVE_TIMEOUT_S)

    verdict(rows)

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"handE_R05precheck_{timestamp()}_result.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\n결과 저장: {path}")


if __name__ == "__main__":
    main()
