"""Hand-E Sim-to-Real 정합성 실험 실행기.

실험계획표의 런 번호와 1:1 대응:
    python run.py r01          # 점검: 활성화·변수 지원·폴링 주기
    python run.py r02          # 무부하 끝점 gPO
    python run.py r03          # rPR 7단계 버니어 실측 (진행자 입력)
    python run.py r04          # 속도 스텝응답
    python run.py r05          # 힘 스윕 (시편 A 파지 10초 유지)
    python run.py r06          # (선택) 인장 유지력 보조 로깅
    python run.py r07          # gOBJ 타이밍 (rFR×rSP 16조합)
    python run.py r08          # 무부하 폐합 대조군
    python run.py r09-draw     # 미학습 조합 10종 추첨 (1회만)
    python run.py r09          # 미학습 조합 실행
    python run.py r10          # Grasp Size 시나리오 (--ur: UR 자동 이동)

각 런은 원시 폴링 CSV + 이벤트 CSV + 결과 요약 CSV를 logs/ 에 남긴다.
"""
import argparse
import csv
import os
import random
import statistics
import sys
import time

import config as C
from hande_client import HandE
from logger import PollLogger, timestamp

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, C.OUTPUT_DIR)


# ---------------------------------------------------------------- 공용 -----
def result_writer(run_name, header):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"handE_{run_name}_{timestamp()}_result.csv")
    fp = open(path, "w", newline="", encoding="utf-8-sig")
    w = csv.writer(fp)
    w.writerow(header)
    return fp, w, path


def routine_header(gr):
    """매 런 공통 루틴: 재활성화 → 워밍업 1회."""
    print("[공통] rACT 재활성화 (자가 캘리브레이션)...")
    gr.activate()
    print("[공통] 워밍업 1회 (기록 제외)...")
    gr.move(255, 128, 64)
    gr.wait_arrival(C.MOVE_TIMEOUT_S)
    gr.move(0, 128, 64)
    gr.wait_arrival(C.MOVE_TIMEOUT_S)
    flt = gr.get_var("FLT")
    if flt != 0:
        print(f"⚠ gFLT={flt} — 매뉴얼 4장 점검 후 재시작 권장")
    print("[공통] 준비 완료\n")


def pause(msg):
    input(f">>> {msg} — 준비되면 Enter: ")


# ---------------------------------------------------------------- R01 -----
def r01(args):
    """점검: 연결·활성화·변수 지원 여부·폴링 주기 실측."""
    with HandE(C.ROBOT_IP, C.GRIPPER_PORT, C.SOCKET_TIMEOUT) as gr:
        print(f"연결 OK: {C.ROBOT_IP}:{C.GRIPPER_PORT}")
        probed = gr.probe()
        print("변수 지원 여부:")
        for k, v in probed.items():
            print(f"  {k}: {'OK (=%s)' % v if v is not None else '미지원'}")
        if gr.cur_var is None:
            print("⚠ 전류(CUR) 변수 미지원 — R05는 gOBJ/gPO 기반으로만 기록됨")
        gr.activate()
        print("활성화 OK (gSTA=3)")
        # 폴링 주기 실측: 무부하 1왕복 동안 폴링
        with PollLogger(C.ROBOT_IP, C.GRIPPER_PORT, OUT, "R01") as log:
            time.sleep(0.5)
            log.mark("close_cmd")
            gr.move(255, 128, 64)
            gr.wait_arrival(C.MOVE_TIMEOUT_S)
            log.mark("open_cmd")
            gr.move(0, 128, 64)
            gr.wait_arrival(C.MOVE_TIMEOUT_S)
            time.sleep(0.5)
        print(f"폴링 샘플 {log.n_samples}개, 평균 주기 {log.mean_period_ms:.1f} ms")
        print(f"→ 기입: gFLT={gr.get_var('FLT')}, 폴링 주기={log.mean_period_ms:.1f}ms, gSTA=3")


# ---------------------------------------------------------------- R02 -----
def r02(args):
    fp, w, path = result_writer("R02", ["rep", "gPO_open", "gPO_closed"])
    opens, closes = [], []
    with HandE(C.ROBOT_IP, C.GRIPPER_PORT, C.SOCKET_TIMEOUT) as gr:
        routine_header(gr)
        for rep in range(1, C.R02_REPS + 1):
            gr.move(0, 128, 128)
            gr.wait_arrival(C.MOVE_TIMEOUT_S)
            time.sleep(C.R02_SETTLE_S)
            po_open = gr.get_var("POS")
            gr.move(255, 128, 128)
            gr.wait_arrival(C.MOVE_TIMEOUT_S)
            time.sleep(C.R02_SETTLE_S)
            po_closed = gr.get_var("POS")
            w.writerow([rep, po_open, po_closed])
            opens.append(po_open)
            closes.append(po_closed)
            print(f"  rep{rep}: open={po_open}, closed={po_closed}")
        gr.move(0, 128, 64)
        gr.wait_arrival(C.MOVE_TIMEOUT_S)
    fp.close()
    print(f"\n→ 기입: gPO_open={statistics.mean(opens):.1f}±{statistics.pstdev(opens):.2f}, "
          f"gPO_closed={statistics.mean(closes):.1f}±{statistics.pstdev(closes):.2f}")
    print(f"결과 파일: {path}")


# ---------------------------------------------------------------- R03 -----
def r03(args):
    fp, w, path = result_writer(
        "R03", ["direction", "rPR", "gPO", "caliper_mm_reads", "caliper_mm_mean"])
    with HandE(C.ROBOT_IP, C.GRIPPER_PORT, C.SOCKET_TIMEOUT) as gr:
        routine_header(gr)
        print("측정 규칙: 손끝 패드 중앙·동일 깊이, 캘리퍼스는 밀지 않고 가볍게 접촉,"
              f" 지점당 {C.R03_CALIPER_READS}회 읽기\n")
        plans = [("closing", 0, C.R03_RPR_STEPS),            # 0에서 출발해 닫힘 방향 접근
                 ("opening", 255, C.R03_RPR_STEPS[::-1])]    # 255에서 출발해 열림 방향 접근
        for direction, start, steps in plans:
            print(f"=== {direction} 방향 ({'0→값' if start == 0 else '255→값'}) ===")
            for rpr in steps:
                gr.move(start, C.R03_SPE, C.R03_FOR)
                gr.wait_arrival(C.MOVE_TIMEOUT_S)
                time.sleep(0.5)
                gr.move(rpr, C.R03_SPE, C.R03_FOR)
                gr.wait_arrival(C.MOVE_TIMEOUT_S)
                time.sleep(1.0)
                gpo = gr.get_var("POS")
                reads = []
                while len(reads) < C.R03_CALIPER_READS:
                    raw = input(f"  rPR={rpr} (gPO={gpo}) — 실측 개구 mm "
                                f"({C.R03_CALIPER_READS}회, 쉼표 구분): ").strip()
                    try:
                        reads = [float(x) for x in raw.split(",")]
                        if len(reads) != C.R03_CALIPER_READS:
                            print(f"  ⚠ {C.R03_CALIPER_READS}개 필요"); reads = []
                    except ValueError:
                        print("  ⚠ 숫자만 입력"); reads = []
                w.writerow([direction, rpr, gpo,
                            "/".join(str(x) for x in reads), statistics.mean(reads)])
                fp.flush()
        gr.move(0, 128, 64)
        gr.wait_arrival(C.MOVE_TIMEOUT_S)
    fp.close()
    print(f"\n결과 파일: {path}")


# ---------------------------------------------------------------- R04 -----
def r04(args):
    fp, w, path = result_writer("R04", ["rSP", "rep", "direction", "move_time_s"])
    with HandE(C.ROBOT_IP, C.GRIPPER_PORT, C.SOCKET_TIMEOUT) as gr:
        routine_header(gr)
        with PollLogger(C.ROBOT_IP, C.GRIPPER_PORT, OUT, "R04") as log:
            for rsp in C.R04_RSP_LEVELS:
                for rep in range(1, C.R04_REPS + 1):
                    for direction, target in (("close", 255), ("open", 0)):
                        time.sleep(0.5)
                        log.mark(f"rSP={rsp}_rep{rep}_{direction}_cmd")
                        t0 = time.perf_counter()
                        gr.move(target, rsp, 128)
                        obj = gr.wait_arrival(C.MOVE_TIMEOUT_S, poll=0.005)
                        dt = time.perf_counter() - t0
                        log.mark(f"rSP={rsp}_rep{rep}_{direction}_done_obj{obj}")
                        w.writerow([rsp, rep, direction, f"{dt:.3f}"])
                        print(f"  rSP={rsp} rep{rep} {direction}: {dt:.3f}s")
                    fp.flush()
        gr.move(0, 128, 64)
        gr.wait_arrival(C.MOVE_TIMEOUT_S)
    fp.close()
    print(f"\n결과: {path}\n시계열: {os.path.join(OUT, '(R04 폴링 CSV)')} — CCTV 이동시간과 교차 확인")


# ---------------------------------------------------------------- R05 -----
def r05(args):
    fp, w, path = result_writer("R05", ["rFR", "rep", "gOBJ", "gPO_stop", "CUR_steady", "CUR_note"])
    with HandE(C.ROBOT_IP, C.GRIPPER_PORT, C.SOCKET_TIMEOUT) as gr:
        routine_header(gr)
        has_cur = gr.probe() and gr.cur_var is not None
        if not has_cur:
            print("⚠ 전류 변수 미지원 — CUR 열은 공란, 시계열은 gPO/gOBJ만 기록\n")
        pause("시편 A를 위치 핀에 고정하고 그리퍼를 파지 위치로 이송")
        with PollLogger(C.ROBOT_IP, C.GRIPPER_PORT, OUT, "R05") as log:
            for rfr in C.R05_RFR_LEVELS:
                for rep in range(1, C.R05_REPS + 1):
                    gr.move(0, C.R05_SPE, 64)
                    gr.wait_arrival(C.MOVE_TIMEOUT_S)
                    time.sleep(0.5)
                    log.mark(f"rFR={rfr}_rep{rep}_grasp_cmd")
                    gr.move(255, C.R05_SPE, rfr)
                    obj = gr.wait_arrival(C.MOVE_TIMEOUT_S)
                    log.mark(f"rFR={rfr}_rep{rep}_hold_start_obj{obj}")
                    # 10초 유지 중 전류 정상값 수집
                    curs = []
                    t0 = time.perf_counter()
                    while time.perf_counter() - t0 < C.R05_HOLD_S:
                        if has_cur:
                            curs.append(gr.get_var(gr.cur_var))
                        time.sleep(0.1)
                    log.mark(f"rFR={rfr}_rep{rep}_hold_end")
                    gpo = gr.get_var("POS")
                    cur_mean = f"{statistics.mean(curs):.1f}" if curs else ""
                    note = (f"drift={max(curs)-min(curs)}" if curs else "no CUR")
                    w.writerow([rfr, rep, obj, gpo, cur_mean, note])
                    fp.flush()
                    print(f"  rFR={rfr} rep{rep}: gOBJ={obj}, gPO={gpo}, CUR={cur_mean}")
        gr.move(0, 128, 64)
        gr.wait_arrival(C.MOVE_TIMEOUT_S)
    fp.close()
    print(f"\n결과 파일: {path}")


# ---------------------------------------------------------------- R06 -----
def r06(args):
    """(선택) 인장 유지력 — 로드셀 판독은 외부 표시기에서 진행자가 읽어 입력."""
    fp, w, path = result_writer("R06", ["rFR", "rep", "slip_force_N", "gOBJ_after_slip"])
    with HandE(C.ROBOT_IP, C.GRIPPER_PORT, C.SOCKET_TIMEOUT) as gr:
        routine_header(gr)
        pause("와이어+500N 로드셀 구성 확인, 환봉에 와이어 연결")
        with PollLogger(C.ROBOT_IP, C.GRIPPER_PORT, OUT, "R06") as log:
            for rfr in C.R06_RFR_LEVELS:
                for rep in range(1, C.R06_REPS + 1):
                    gr.move(0, 128, 64)
                    gr.wait_arrival(C.MOVE_TIMEOUT_S)
                    pause(f"rFR={rfr} rep{rep}: 환봉을 파지 위치에 배치")
                    log.mark(f"rFR={rfr}_rep{rep}_grasp_cmd")
                    gr.move(255, 128, rfr)
                    obj = gr.wait_arrival(C.MOVE_TIMEOUT_S)
                    print(f"  파지 완료 (gOBJ={obj}). 서서히 인장 → 슬립 시 로드셀 최대값 기록")
                    log.mark(f"rFR={rfr}_rep{rep}_pull_start")
                    force = input("  슬립 발생 인장력(N) 입력: ").strip()
                    log.mark(f"rFR={rfr}_rep{rep}_slip")
                    w.writerow([rfr, rep, force, gr.get_var("OBJ")])
                    fp.flush()
        gr.move(0, 128, 64)
        gr.wait_arrival(C.MOVE_TIMEOUT_S)
    fp.close()
    print(f"\n결과 파일: {path}")


# ------------------------------------------------------------ R07 / R08 -----
def _timed_grasp(gr, log, tag, rpr, rsp, rfr):
    """파지 1회: 명령→gPO 정지 시점·gOBJ 전환 시점을 고속 폴링으로 포착."""
    gr.move(0, 128, 64)
    gr.wait_arrival(C.MOVE_TIMEOUT_S)
    time.sleep(0.5)
    log.mark(f"{tag}_cmd")
    gr.move(rpr, rsp, rfr)
    gr.wait_latch()   # gPR 반향 확인 — 이후의 비제로 gOBJ만 종료 상태로 신뢰
    # 고속 관찰: gPO 변화 정지 시점과 gOBJ 비제로 전환 시점
    t_cmd = time.perf_counter()
    last_po, t_po_stop, t_obj = None, None, None
    obj_final = 0
    while time.perf_counter() - t_cmd < C.MOVE_TIMEOUT_S:
        po = gr.get_var("POS")
        obj = gr.get_var("OBJ")
        now = time.perf_counter()
        if last_po is not None and po != last_po:
            t_po_stop = None            # 아직 움직임
        elif t_po_stop is None and last_po is not None:
            t_po_stop = now             # 정지 후보 시점
        last_po = po
        if obj != 0 and t_obj is None:
            t_obj, obj_final = now, obj
            break
        time.sleep(0.002)
    debounce_ms = (t_obj - t_po_stop) * 1000 if (t_obj and t_po_stop) else None
    log.mark(f"{tag}_obj{obj_final}")
    return obj_final, last_po, debounce_ms


def r07(args):
    fp, w, path = result_writer("R07", ["rFR", "rSP", "rep", "gOBJ", "gPO_stop", "debounce_ms"])
    with HandE(C.ROBOT_IP, C.GRIPPER_PORT, C.SOCKET_TIMEOUT) as gr:
        routine_header(gr)
        pause("시편 A를 위치 핀에 고정")
        with PollLogger(C.ROBOT_IP, C.GRIPPER_PORT, OUT, "R07") as log:
            for rfr in C.R07_RFR_LEVELS:
                for rsp in C.R07_RSP_LEVELS:
                    for rep in range(1, C.R07_REPS + 1):
                        tag = f"rFR{rfr}_rSP{rsp}_rep{rep}"
                        obj, gpo, db = _timed_grasp(gr, log, tag, 255, rsp, rfr)
                        w.writerow([rfr, rsp, rep, obj, gpo,
                                    f"{db:.1f}" if db is not None else ""])
                        fp.flush()
                        print(f"  {tag}: gOBJ={obj}, gPO={gpo}, debounce={db and f'{db:.1f}ms'}")
        gr.move(0, 128, 64)
        gr.wait_arrival(C.MOVE_TIMEOUT_S)
    fp.close()
    print(f"\n결과 파일: {path}")


def r08(args):
    fp, w, path = result_writer("R08", ["rSP", "rep", "gOBJ", "gPO_stop", "debounce_ms"])
    with HandE(C.ROBOT_IP, C.GRIPPER_PORT, C.SOCKET_TIMEOUT) as gr:
        routine_header(gr)
        pause("무부하 확인 (손가락 사이 비움)")
        with PollLogger(C.ROBOT_IP, C.GRIPPER_PORT, OUT, "R08") as log:
            for rsp in C.R08_RSP_LEVELS:
                for rep in range(1, C.R08_REPS + 1):
                    tag = f"noload_rSP{rsp}_rep{rep}"
                    obj, gpo, db = _timed_grasp(gr, log, tag, 255, rsp, 128)
                    w.writerow([rsp, rep, obj, gpo, f"{db:.1f}" if db is not None else ""])
                    fp.flush()
                    print(f"  {tag}: gOBJ={obj}, debounce={db and f'{db:.1f}ms'}")
        gr.move(0, 128, 64)
        gr.wait_arrival(C.MOVE_TIMEOUT_S)
    fp.close()
    print(f"\n결과 파일: {path}")


# ---------------------------------------------------------------- R09 -----
def r09_draw(args):
    """미학습 조합 추첨 — 피팅 런에 쓴 값(rPR 끝점·7단계, rSP/rFR 레벨)과 겹치지 않게."""
    used_rpr = set([0, 255] + C.R03_RPR_STEPS)
    used_rsp = set(C.R04_RSP_LEVELS + C.R07_RSP_LEVELS + [C.R03_SPE, C.R05_SPE])
    used_rfr = set(C.R05_RFR_LEVELS + C.R07_RFR_LEVELS + [C.R03_FOR])
    rng = random.Random(C.R09_SEED)
    combos, seen = [], set()
    while len(combos) < C.R09_N_COMBOS:
        rpr = rng.randrange(10, 246)
        rsp = rng.randrange(20, 256)
        rfr = rng.randrange(0, 256)
        if rpr in used_rpr or rsp in used_rsp or rfr in used_rfr:
            continue
        if (rpr, rsp, rfr) in seen:
            continue
        seen.add((rpr, rsp, rfr))
        combos.append((rpr, rsp, rfr))
    path = os.path.join(HERE, C.R09_COMBO_FILE)
    with open(path, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.writer(fp)
        w.writerow(["combo_id", "rPR", "rSP", "rFR"])
        for i, (a, b, c) in enumerate(combos, 1):
            w.writerow([i, a, b, c])
    print(f"미학습 조합 {len(combos)}종 저장: {path} (seed={C.R09_SEED})")
    for i, (a, b, c) in enumerate(combos, 1):
        print(f"  #{i}: rPR={a}, rSP={b}, rFR={c}")


def r09(args):
    combo_path = os.path.join(HERE, C.R09_COMBO_FILE)
    if not os.path.exists(combo_path):
        sys.exit("조합 파일 없음 — 먼저 `python run.py r09-draw` 실행")
    with open(combo_path, newline="", encoding="utf-8-sig") as fp:
        combos = [(int(r["rPR"]), int(r["rSP"]), int(r["rFR"]))
                  for r in csv.DictReader(fp)]
    fp2, w, path = result_writer("R09", ["combo_id", "rep", "rPR", "rSP", "rFR", "gOBJ", "gPO_final"])
    with HandE(C.ROBOT_IP, C.GRIPPER_PORT, C.SOCKET_TIMEOUT) as gr:
        routine_header(gr)
        pause("R09 시나리오 구성 확인 (무부하 기준; 시편 사용 시 별도 기록)")
        with PollLogger(C.ROBOT_IP, C.GRIPPER_PORT, OUT, "R09") as log:
            for cid, (rpr, rsp, rfr) in enumerate(combos, 1):
                for rep in range(1, C.R09_REPS + 1):
                    gr.move(0, 128, 64)
                    gr.wait_arrival(C.MOVE_TIMEOUT_S)
                    time.sleep(0.5)
                    log.mark(f"combo{cid}_rep{rep}_cmd_rPR{rpr}_rSP{rsp}_rFR{rfr}")
                    gr.move(rpr, rsp, rfr)
                    obj = gr.wait_arrival(C.MOVE_TIMEOUT_S)
                    log.mark(f"combo{cid}_rep{rep}_done_obj{obj}")
                    time.sleep(1.0)
                    w.writerow([cid, rep, rpr, rsp, rfr, obj, gr.get_var("POS")])
                    fp2.flush()
                    print(f"  combo{cid} rep{rep}: gOBJ={obj}")
        gr.move(0, 128, 64)
        gr.wait_arrival(C.MOVE_TIMEOUT_S)
    fp2.close()
    print(f"\n결과 파일: {path} — 동일 조합을 Isaac Sim(R11)에 재생")


# ---------------------------------------------------------------- R10 -----
def r10(args):
    fp, w, path = result_writer(
        "R10", ["specimen", "rep", "grasp_gOBJ", "hold_gOBJ", "success"])
    ur = None
    if args.ur:
        try:
            from rtde_control import RTDEControlInterface
            from rtde_receive import RTDEReceiveInterface
            ur = (RTDEControlInterface(C.ROBOT_IP), RTDEReceiveInterface(C.ROBOT_IP))
            print("UR RTDE 연결 OK — 파지 후 +Z 100mm 자동 이동")
        except ImportError:
            sys.exit("ur_rtde 미설치 — `pip install ur_rtde` 또는 --ur 없이 수동 이동")
    with HandE(C.ROBOT_IP, C.GRIPPER_PORT, C.SOCKET_TIMEOUT) as gr:
        routine_header(gr)
        with PollLogger(C.ROBOT_IP, C.GRIPPER_PORT, OUT, "R10") as log:
            for spec in C.R10_SPECIMENS:
                for rep in range(1, C.R10_REPS + 1):
                    gr.move(0, C.R10_GRASP_SPE, 64)
                    gr.wait_arrival(C.MOVE_TIMEOUT_S)
                    pause(f"시편 {spec} rep{rep}: 시편 고정·그리퍼 파지 위치 확인")
                    log.mark(f"spec{spec}_rep{rep}_grasp_cmd")
                    gr.move(255, C.R10_GRASP_SPE, C.R10_GRASP_FOR)
                    grasp_obj = gr.wait_arrival(C.MOVE_TIMEOUT_S)
                    if grasp_obj != 2:
                        print(f"  ⚠ 파지 실패 (gOBJ={grasp_obj})")
                        w.writerow([spec, rep, grasp_obj, "", "FAIL"])
                        fp.flush()
                        continue
                    log.mark(f"spec{spec}_rep{rep}_lift_start")
                    if ur:
                        ctrl, recv = ur
                        pose = recv.getActualTCPPose()
                        pose[2] += C.R10_LIFT_MM / 1000.0
                        ctrl.moveL(pose, C.UR_LIFT_SPEED, C.UR_LIFT_ACC)
                    else:
                        pause(f"수동으로 +{C.R10_LIFT_MM:.0f}mm 들어올린 후")
                    log.mark(f"spec{spec}_rep{rep}_hold_start")
                    time.sleep(C.R10_HOLD_S)
                    hold_obj = gr.get_var("OBJ")
                    success = "OK" if hold_obj == 2 else "DROP"
                    log.mark(f"spec{spec}_rep{rep}_hold_end_obj{hold_obj}")
                    print(f"  시편{spec} rep{rep}: 파지 gOBJ={grasp_obj}, 유지 gOBJ={hold_obj} → {success}")
                    if ur:
                        ctrl, recv = ur
                        pose = recv.getActualTCPPose()
                        pose[2] -= C.R10_LIFT_MM / 1000.0
                        ctrl.moveL(pose, C.UR_LIFT_SPEED, C.UR_LIFT_ACC)
                    else:
                        pause("원위치로 내린 후")
                    gr.move(0, C.R10_GRASP_SPE, 64)
                    gr.wait_arrival(C.MOVE_TIMEOUT_S)
                    w.writerow([spec, rep, grasp_obj, hold_obj, success])
                    fp.flush()
    fp.close()
    print(f"\n결과 파일: {path}")


# ------------------------------------------------------------- summary -----
def _latest_result(run_name):
    """해당 런의 가장 최근 result CSV 경로 (없으면 None)."""
    import glob
    files = sorted(glob.glob(os.path.join(OUT, f"handE_{run_name}_*_result.csv")))
    return files[-1] if files else None


def _rows(path):
    with open(path, newline="", encoding="utf-8-sig") as fp:
        return list(csv.DictReader(fp))


def summary(args):
    """모든 런의 최신 result CSV를 결과 기입용 문장으로 요약."""
    def fmt_mean_sd(vals):
        return f"{statistics.mean(vals):.1f}±{statistics.pstdev(vals):.2f}"

    lines = {}
    # R02
    p = _latest_result("R02")
    if p:
        r = _rows(p)
        lines["R02"] = (f"gPO_open={fmt_mean_sd([float(x['gPO_open']) for x in r])}, "
                        f"gPO_closed={fmt_mean_sd([float(x['gPO_closed']) for x in r])}")
    # R03
    p = _latest_result("R03")
    if p:
        r = _rows(p)
        parts = []
        for d in ("closing", "opening"):
            pts = [(x["rPR"], x["gPO"], x["caliper_mm_mean"]) for x in r if x["direction"] == d]
            parts.append(f"{d}: " + ", ".join(f"rPR{a}→gPO{b}/{float(c):.2f}mm" for a, b, c in pts))
        lines["R03"] = " | ".join(parts)
    # R04
    p = _latest_result("R04")
    if p:
        r = _rows(p)
        by = {}
        for x in r:
            by.setdefault(x["rSP"], []).append(float(x["move_time_s"]))
        lines["R04"] = ", ".join(f"rSP{k}: {statistics.mean(v):.2f}s" for k, v in by.items())
    # R05
    p = _latest_result("R05")
    if p:
        r = _rows(p)
        by = {}
        for x in r:
            if x["CUR_steady"]:
                by.setdefault(x["rFR"], []).append(float(x["CUR_steady"]))
        if by:
            lines["R05"] = ", ".join(f"rFR{k}: CUR={statistics.mean(v):.1f}" for k, v in by.items())
        else:
            lines["R05"] = "CUR 미지원 — gOBJ/gPO 기록만 (" + \
                ", ".join(f"rFR{x['rFR']}:gOBJ{x['gOBJ']}" for x in r[:5]) + " ...)"
    # R06
    p = _latest_result("R06")
    if p:
        r = _rows(p)
        lines["R06"] = ", ".join(f"rFR{x['rFR']}: {x['slip_force_N']}N" for x in r)
    # R07 / R08
    for run, key in (("R07", "rFR"), ("R08", "rSP")):
        p = _latest_result(run)
        if p:
            r = _rows(p)
            dbs = [float(x["debounce_ms"]) for x in r if x["debounce_ms"]]
            ok = sum(1 for x in r if x["gOBJ"] == ("2" if run == "R07" else "3"))
            lines[run] = (f"디바운스 {fmt_mean_sd(dbs)}ms (n={len(dbs)}), "
                          f"기대 gOBJ 일치 {ok}/{len(r)}") if dbs else f"기대 gOBJ 일치 {ok}/{len(r)}"
    # R09
    p = _latest_result("R09")
    if p:
        r = _rows(p)
        lines["R09"] = f"{len(set(x['combo_id'] for x in r))}조합 × {C.R09_REPS}회 완료, CSV: {os.path.basename(p)}"
    # R10
    p = _latest_result("R10")
    if p:
        r = _rows(p)
        ok = sum(1 for x in r if x["success"] == "OK")
        lines["R10"] = f"성공 {ok}/{len(r)} (" + \
            ", ".join(f"시편{x['specimen']}r{x['rep']}:{x['success']}" for x in r) + ")"

    if not lines:
        sys.exit(f"결과 CSV 없음 — {OUT} 확인")
    out_path = os.path.join(OUT, f"summary_{timestamp()}.csv")
    with open(out_path, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.writer(fp)
        w.writerow(["런", "결과 기입"])
        for k in sorted(lines):
            w.writerow([k, lines[k]])
    print("=== 실험계획표 결과 기입용 값 ===")
    for k in sorted(lines):
        print(f"  {k}: {lines[k]}")
    print(f"\n저장: {out_path}")


# ---------------------------------------------------------------- CLI -----
def main():
    runs = {"r01": r01, "r02": r02, "r03": r03, "r04": r04, "r05": r05,
            "r06": r06, "r07": r07, "r08": r08, "r09-draw": r09_draw,
            "r09": r09, "r10": r10, "summary": summary}
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run", choices=sorted(runs.keys()), help="실행할 런")
    p.add_argument("--ur", action="store_true", help="R10: ur_rtde로 UR 자동 이동")
    args = p.parse_args()
    runs[args.run](args)


if __name__ == "__main__":
    main()
