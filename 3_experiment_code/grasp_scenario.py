"""10 파지 시나리오 — 신호 궤적 정합 검증용 (UR5e 자동 이동).

시나리오(1회차):
    파지 → 상승 → 3초 유지
         → 2시방향 이동 → joint6 +90° → 복귀 → joint6 -90° → 복귀 → 원위치 복귀
         → 10시방향 이동 → joint6 +90° → 복귀 → joint6 -90° → 복귀 → 원위치 복귀
         → 하강 → 개방(놓기)

목적:
    실물 Hand-E가 내보내는 신호 시계열(gPO/gOBJ/전류)과 Isaac Sim 모델 출력이
    같은 명령 시퀀스에서 일치하는지 비교할 기준 데이터를 만든다.
    수평 이동과 손목 회전으로 관성 하중을 걸어 파지 유지까지 함께 본다.

사람이 하는 일:
    회차 시작 시 그리퍼를 시편 파지 위치로 수동 이동 후 Enter. 이후 전자동.

실행:
    python grasp_scenario.py            # 본 시험
    python grasp_scenario.py --dry      # 리허설: 파지 없이 경로만 (충돌 확인용)
    python grasp_scenario.py --reps 1   # 회차 수 지정
"""
import argparse
import csv
import math
import os
import statistics
import time

import config as C
from hande_client import HandE
from logger import PollLogger, timestamp

# ------------------------------------------------------------- 시편 정보 -----
SPECIMEN_ID = "A"
SPECIMEN_MASS_KG = 0.21
SPECIMEN_MM = None             # 실측 직경(mm). 넣으면 gPO 교차검증에 사용

# --------------------------------------------------------- 시나리오 설정 -----
REPS = 3
HOLD_S = 3.0                   # 상승 후 유지 (기존 10초에서 단축)
SETTLE_S = 1.0                 # 각 이동 후 정착
LIFT_MM = C.EXP10_LIFT_MM        # 상승 거리 (config.py, 현재 30mm)

MOVE_MM = 50.0                 # ★ 2시/10시 방향 수평 이동 거리 — 작업공간 확인 후 조정
ROT_DEG = 90.0                 # joint6 회전 각도

# 시계 방향 정의: 12시 = 베이스 프레임 +Y, 시계방향으로 각도 증가
# ★ 실제 로봇 배치에 따라 기준이 다르면 이 값을 조정
CLOCK_DEG = {"2시": 60.0, "10시": -60.0}

GRASP_SPE = 128
GRASP_FOR = 128
OPEN_SPE = 128
OPEN_FOR = 64

# UR 이동 파라미터 (안전을 위해 저속)
LIN_SPEED = C.UR_LIFT_SPEED    # m/s
LIN_ACC = C.UR_LIFT_ACC        # m/s^2
JNT_SPEED = 0.3                # rad/s
JNT_ACC = 0.5                  # rad/s^2

# 03 실측 보정 커브
CAL_A, CAL_B = 53.489, -0.2164

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, C.OUTPUT_DIR)


def mm_from_gpo(gpo):
    return CAL_A + CAL_B * gpo


def clock_vec(name):
    """시계 방향 이름 → 수평면 단위벡터 (dx, dy)."""
    a = math.radians(CLOCK_DEG[name])
    return math.sin(a), math.cos(a)


class UR:
    def __init__(self, ip):
        from rtde_control import RTDEControlInterface
        from rtde_receive import RTDEReceiveInterface
        self.ctrl = RTDEControlInterface(ip)
        self.recv = RTDEReceiveInterface(ip)

    def pose(self):
        return list(self.recv.getActualTCPPose())

    def move_delta(self, dx=0.0, dy=0.0, dz=0.0):
        """현재 TCP에서 상대 직선 이동 (m 단위)."""
        p = self.pose()
        p[0] += dx
        p[1] += dy
        p[2] += dz
        self.ctrl.moveL(p, LIN_SPEED, LIN_ACC)

    def rotate_j6(self, deg):
        """joint6만 상대 회전."""
        q = list(self.recv.getActualQ())
        q[5] += math.radians(deg)
        self.ctrl.moveJ(q, JNT_SPEED, JNT_ACC)

    def stop(self):
        try:
            self.ctrl.stopScript()
        except Exception:
            pass


def snapshot(gr):
    """현재 그리퍼 상태 (gPO, gOBJ)."""
    return gr.get_var("POS"), gr.get_var("OBJ")


def close_and_sample(gr, timeout):
    """파지 명령 후 도착까지 대기하며 전류 샘플링.

    Hand-E는 리드스크류 자기잠금이라 유지 중 전류가 0이므로,
    의미 있는 값은 폐합 중 최대 전류다.
    """
    gr.move(255, GRASP_SPE, GRASP_FOR)
    gr.wait_latch()
    t0 = time.perf_counter()
    curs, obj = [], 0
    while time.perf_counter() - t0 < timeout:
        try:
            if gr.cur_var:
                curs.append(gr.get_var(gr.cur_var))
            obj = gr.get_var("OBJ")
        except IOError:
            continue
        if obj != 0:
            break
    return obj, time.perf_counter() - t0, (max(curs) if curs else None)


def rotate_cycle(ur, gr, log, tag, checks):
    """joint6 +ROT → 복귀 → -ROT → 복귀. 각 구간마다 gOBJ 확인."""
    for sign in (+1, -1):
        log.mark(f"{tag}_j6{sign:+.0f}_start")
        ur.rotate_j6(sign * ROT_DEG)
        time.sleep(SETTLE_S)
        po, ob = snapshot(gr)
        checks.append((f"{tag}_j6{sign:+.0f}", po, ob))
        log.mark(f"{tag}_j6{sign:+.0f}_end_obj{ob}")

        log.mark(f"{tag}_j6{sign:+.0f}_back_start")
        ur.rotate_j6(-sign * ROT_DEG)
        time.sleep(SETTLE_S)
        po, ob = snapshot(gr)
        checks.append((f"{tag}_j6{sign:+.0f}_back", po, ob))
        log.mark(f"{tag}_j6{sign:+.0f}_back_end_obj{ob}")


def run_rep(ur, gr, log, rep, dry):
    tag = f"rep{rep}"
    checks = []
    print(f"\n[{rep}] 시나리오 시작")

    # 0) 개방 상태에서 시작
    gr.move(0, OPEN_SPE, OPEN_FOR)
    gr.wait_arrival(C.MOVE_TIMEOUT_S)
    input(f"  >>> 그리퍼를 시편 파지 위치로 이동한 뒤 Enter: ")

    # 1) 파지
    if dry:
        print("  [리허설] 파지 생략 — 경로만 확인")
        obj, t_grasp, cur_peak = 0, 0.0, None
        gpo_grasp = gr.get_var("POS")
    else:
        log.mark(f"{tag}_grasp_cmd")
        obj, t_grasp, cur_peak = close_and_sample(gr, C.MOVE_TIMEOUT_S)
        gpo_grasp = gr.get_var("POS")
        log.mark(f"{tag}_grasp_done_obj{obj}")
        print(f"  파지: gOBJ={obj}, gPO={gpo_grasp} ({mm_from_gpo(gpo_grasp):.2f}mm), "
              f"{t_grasp*1000:.0f}ms, 전류peak={cur_peak}")
        if obj != 2:
            print(f"  ⚠ gOBJ={obj} — 물체 파지(2)가 아닙니다. 중단합니다.")
            gr.move(0, OPEN_SPE, OPEN_FOR)
            gr.wait_arrival(C.MOVE_TIMEOUT_S)
            return None

    # 2) 상승
    log.mark(f"{tag}_lift_start")
    ur.move_delta(dz=LIFT_MM / 1000.0)
    time.sleep(SETTLE_S)
    log.mark(f"{tag}_lift_end")
    print(f"  상승 {LIFT_MM:.0f}mm 완료")

    # 3) 유지
    log.mark(f"{tag}_hold_start")
    time.sleep(HOLD_S)
    po, ob = snapshot(gr)
    checks.append((f"{tag}_hold", po, ob))
    log.mark(f"{tag}_hold_end_obj{ob}")
    print(f"  {HOLD_S:.0f}초 유지: gOBJ={ob}, gPO={po}")

    # 4) 2시 / 10시 방향 이동 + 회전
    for name in ("2시", "10시"):
        dx, dy = clock_vec(name)
        log.mark(f"{tag}_{name}_move_start")
        ur.move_delta(dx=dx * MOVE_MM / 1000.0, dy=dy * MOVE_MM / 1000.0)
        time.sleep(SETTLE_S)
        po, ob = snapshot(gr)
        checks.append((f"{tag}_{name}_arrived", po, ob))
        log.mark(f"{tag}_{name}_move_end_obj{ob}")
        print(f"  {name} 방향 {MOVE_MM:.0f}mm 이동: gOBJ={ob}")

        rotate_cycle(ur, gr, log, f"{tag}_{name}", checks)

        log.mark(f"{tag}_{name}_return_start")
        ur.move_delta(dx=-dx * MOVE_MM / 1000.0, dy=-dy * MOVE_MM / 1000.0)
        time.sleep(SETTLE_S)
        po, ob = snapshot(gr)
        checks.append((f"{tag}_{name}_returned", po, ob))
        log.mark(f"{tag}_{name}_return_end_obj{ob}")
        print(f"  {name} 위치 복귀 완료: gOBJ={ob}")

    # 5) 하강
    log.mark(f"{tag}_lower_start")
    ur.move_delta(dz=-LIFT_MM / 1000.0)
    time.sleep(SETTLE_S)
    log.mark(f"{tag}_lower_end")
    print(f"  하강 완료")

    # 6) 놓기
    po_end, ob_end = snapshot(gr)
    log.mark(f"{tag}_release_cmd")
    gr.move(0, OPEN_SPE, OPEN_FOR)
    gr.wait_arrival(C.MOVE_TIMEOUT_S)
    time.sleep(SETTLE_S)
    log.mark(f"{tag}_release_done")
    print(f"  개방 완료")

    if dry:
        return None

    held = all(ob == 2 for _, _, ob in checks)
    drift = po_end - gpo_grasp
    print(f"  → 전 구간 파지 유지: {'OK' if held else '실패 구간 있음'}, "
          f"드리프트 {drift:+d} count")
    if not held:
        for nm, po, ob in checks:
            if ob != 2:
                print(f"      ✗ {nm}: gOBJ={ob}, gPO={po}")

    return {
        "rep": rep,
        "gPO_grasp": gpo_grasp,
        "opening_mm": round(mm_from_gpo(gpo_grasp), 2),
        "grasp_gOBJ": obj,
        "grasp_time_ms": round(t_grasp * 1000, 1),
        "CUR_peak_close": cur_peak if cur_peak is not None else "",
        "gPO_end": po_end,
        "gPO_drift": drift,
        "all_phases_held": "OK" if held else "FAIL",
        "n_phase_checks": len(checks),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry", action="store_true",
                    help="리허설: 파지 없이 경로만 실행 (충돌 확인)")
    ap.add_argument("--reps", type=int, default=REPS, help=f"반복 횟수 (기본 {REPS})")
    args = ap.parse_args()

    print("=" * 58)
    print("  10 파지 시나리오 — 신호 궤적 정합 검증")
    print("=" * 58)
    print(f"  파지 → 상승{LIFT_MM:.0f}mm → 유지{HOLD_S:.0f}s")
    print(f"       → 2시 {MOVE_MM:.0f}mm 이동 → j6 ±{ROT_DEG:.0f}° → 복귀")
    print(f"       → 10시 {MOVE_MM:.0f}mm 이동 → j6 ±{ROT_DEG:.0f}° → 복귀")
    print(f"       → 하강 → 놓기      ×{args.reps}회")
    print(f"  시편 {SPECIMEN_ID}: {SPECIMEN_MASS_KG}kg")
    if args.dry:
        print("  ** 리허설 모드: 파지하지 않고 경로만 실행 **")
    print("=" * 58)

    ur = None
    rows = []
    try:
        ur = UR(C.ROBOT_IP)
        print("UR RTDE 연결 OK")
    except ImportError:
        raise SystemExit("ur_rtde 미설치 — pip install ur_rtde")
    except Exception as e:
        raise SystemExit(f"UR 연결 실패: {e}\n  → UR을 Remote Control 모드로 두었는지 확인")

    try:
        with HandE(C.ROBOT_IP, C.GRIPPER_PORT, C.SOCKET_TIMEOUT) as gr:
            print("\n[공통] rACT 재활성화 (자가 캘리브레이션)...")
            print("  ⚠ 지금 손가락 사이가 비어 있어야 합니다")
            gr.activate()
            gr.probe()
            print(f"[공통] 전류 변수: {gr.cur_var or '미지원'}")
            flt = gr.get_var("FLT")
            if flt != 0:
                print(f"⚠ gFLT={flt} — 점검 권장")

            with PollLogger(C.ROBOT_IP, C.GRIPPER_PORT, OUT, "10") as log:
                for rep in range(1, args.reps + 1):
                    r = run_rep(ur, gr, log, rep, args.dry)
                    if r:
                        rows.append(r)
    finally:
        if ur:
            ur.stop()

    if not rows:
        print("\n(기록된 회차 없음 — 리허설이었거나 파지 실패)")
        return

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"handE_10scenario_{timestamp()}_result.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print("\n" + "=" * 58)
    print("  결과 요약")
    print("=" * 58)
    gp = [r["gPO_grasp"] for r in rows]
    ok = sum(1 for r in rows if r["all_phases_held"] == "OK")
    print(f"  파지 gPO 평균 {statistics.mean(gp):.1f} (σ {statistics.pstdev(gp):.2f}) "
          f"→ 개구 {mm_from_gpo(statistics.mean(gp)):.2f}mm")
    print(f"  전 구간 파지 유지: {ok}/{len(rows)} 회차")
    print(f"  최대 드리프트: {max((r['gPO_drift'] for r in rows), key=abs):+d} count")
    print(f"\n  결과 파일: {path}")
    print("\n  [11 시뮬 재생 사양]")
    print(f"    파지 rPR=255, rSP={GRASP_SPE}, rFR={GRASP_FOR}")
    print(f"    상승 {LIFT_MM:.0f}mm → 유지 {HOLD_S:.0f}s")
    print(f"    2시/10시 {MOVE_MM:.0f}mm 이동, joint6 ±{ROT_DEG:.0f}°")
    print(f"    직선 {LIN_SPEED}m/s, 관절 {JNT_SPEED}rad/s, 구간간 정착 {SETTLE_S}s")
    print("    * gOBJ 전환에는 실측 244ms 보고 지연 적용")


if __name__ == "__main__":
    main()
