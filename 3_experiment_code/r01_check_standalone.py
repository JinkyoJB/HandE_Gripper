
"""R01 작동 점검 — 단독 실행 파일 (이 파일 하나만 복사해서 실행 가능).

점검 순서:
  1. 소켓 연결 (UR 컨트롤러 63352 = Robotiq URCap)
  2. 읽기 변수 지원 여부 (STA/PRE/POS/OBJ/FLT + 전류 CUR/COU)
  3. 그리퍼 활성화 (rACT 0→1, 자가 캘리브레이션, gSTA=3 대기)
  4. 무부하 개폐 1왕복 (이동 시간 측정)
  5. 폴링 주기 실측 (GET POS 500회)
  6. 최종 리포트 — 실험계획표 R01 행에 기입할 값 출력

사용: python r01_check_standalone.py [로봇IP]   (기본 192.168.1.10)
요구: Python 3.8+ 표준 라이브러리만.
"""
import socket
import statistics
import sys
import time

ROBOT_IP = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.10"
PORT = 63352
TIMEOUT = 2.0

READ_VARS = ["STA", "PRE", "POS", "OBJ", "FLT"]
CUR_CANDIDATES = ["CUR", "COU"]          # 전류 변수 이름 후보 (URCap 버전별 상이)


# ---------------------------------------------------------------- 통신 -----
def send_recv(sock, cmd):
    sock.sendall((cmd + "\n").encode("ascii"))
    return sock.recv(1024).decode("ascii").strip()


def get_var(sock, name):
    resp = send_recv(sock, f"GET {name}")
    parts = resp.split()
    # 미지원 변수는 값 자리에 '?'가 온다 (예: "CUR ?")
    if len(parts) == 2 and parts[0].upper() == name.upper():
        try:
            return int(parts[1])
        except ValueError:
            raise IOError(f"GET {name} 미지원/비정상 값: {resp!r}")
    raise IOError(f"GET {name} 응답 이상: {resp!r}")


def set_vars(sock, **kw):
    cmd = "SET " + " ".join(f"{k.upper()} {int(v)}" for k, v in kw.items())
    resp = send_recv(sock, cmd)
    if "ack" not in resp.lower():
        raise IOError(f"SET 응답 이상: {resp!r}")


def wait_latch(sock, pos, timeout=2.0):
    """gPR(PRE)이 명령값을 반향할 때까지 대기 — 이후의 비제로 gOBJ만 신뢰."""
    t0 = time.time()
    while get_var(sock, "PRE") != pos:
        if time.time() - t0 > timeout:
            raise TimeoutError(f"명령 래치 실패: gPR != {pos}")
        time.sleep(0.005)


def move_and_wait(sock, pos, spe=128, force=64, timeout=8.0):
    """이동 명령 후 종료 대기. (최종 gOBJ, 이동시간 s) 반환."""
    t0 = time.perf_counter()
    set_vars(sock, POS=pos, SPE=spe, FOR=force, GTO=1)
    wait_latch(sock, pos)
    while True:
        obj = get_var(sock, "OBJ")
        if obj != 0:
            return obj, time.perf_counter() - t0
        if time.perf_counter() - t0 > timeout:
            return 0, time.perf_counter() - t0
        time.sleep(0.01)


# ---------------------------------------------------------------- 점검 -----
def main():
    report = {}
    print(f"=== R01 작동 점검: {ROBOT_IP}:{PORT} ===\n")

    # 1. 연결
    print("[1/5] 소켓 연결...")
    try:
        sock = socket.create_connection((ROBOT_IP, PORT), TIMEOUT)
        sock.settimeout(TIMEOUT)
    except socket.timeout:
        sys.exit(f"✗ 연결 타임아웃 — PC IP가 192.168.1.x 대역인지, 랜선 연결 확인")
    except ConnectionRefusedError:
        sys.exit(f"✗ 연결 거부 — 로봇 전원·URCap(그리퍼 프로그램) 활성 상태 확인")
    except OSError as e:
        sys.exit(f"✗ 연결 실패: {e} — 로봇 IP({ROBOT_IP}) 확인 (펜던트 설정)")
    print("  ✓ 연결 OK\n")

    # 2. 변수 지원
    print("[2/5] 읽기 변수 지원 점검...")
    cur_var = None
    for v in READ_VARS + CUR_CANDIDATES:
        try:
            val = get_var(sock, v)
            print(f"  {v}: OK (={val})")
            if v in CUR_CANDIDATES and cur_var is None:
                cur_var = v
        except (IOError, ValueError, socket.timeout):
            print(f"  {v}: 미지원")
    report["전류 변수"] = cur_var or "미지원"
    if cur_var is None:
        print("  ⚠ 전류 미지원 — R05(힘 거동)는 gOBJ/gPO 기반으로만 기록됨")
    print()

    # 3. 활성화
    print("[3/5] 활성화 (rACT 0→1, 자가 캘리브레이션)...")
    set_vars(sock, ACT=0)
    time.sleep(0.5)
    set_vars(sock, ACT=1)
    t0 = time.time()
    while get_var(sock, "STA") != 3:
        if time.time() - t0 > 15.0:
            sys.exit("✗ 활성화 실패: gSTA=3 도달 못 함 — 그리퍼 전원·커플링 확인")
        time.sleep(0.1)
    report["gSTA"] = 3
    print(f"  ✓ 활성화 OK ({time.time()-t0:.1f}s)\n")

    # 4. 무부하 개폐 1왕복
    print("[4/5] 무부하 개폐 1왕복 (손가락 사이 비웠는지 확인!)...")
    input("  준비되면 Enter: ")
    obj_c, t_close = move_and_wait(sock, 255)
    print(f"  닫힘: gOBJ={obj_c} ({'정상' if obj_c == 3 else '⚠ 확인 필요'}), {t_close:.2f}s")
    obj_o, t_open = move_and_wait(sock, 0)
    print(f"  열림: gOBJ={obj_o} ({'정상' if obj_o == 3 else '⚠ 확인 필요'}), {t_open:.2f}s\n")
    report["개폐 왕복"] = f"닫힘 gOBJ={obj_c}/{t_close:.2f}s, 열림 gOBJ={obj_o}/{t_open:.2f}s"

    # 5. 폴링 주기 실측
    print("[5/5] 폴링 주기 실측 (GET POS 500회)...")
    stamps = []
    for _ in range(500):
        get_var(sock, "POS")
        stamps.append(time.perf_counter())
    periods = [(b - a) * 1000 for a, b in zip(stamps, stamps[1:])]
    mean_ms = statistics.mean(periods)
    p95_ms = sorted(periods)[int(len(periods) * 0.95)]
    report["폴링 주기"] = f"평균 {mean_ms:.2f}ms / P95 {p95_ms:.2f}ms"
    print(f"  평균 {mean_ms:.2f} ms, P95 {p95_ms:.2f} ms "
          f"(≈ {1000/mean_ms:.0f} Hz — R04 속도 시계열 분해능 기준)\n")

    flt = get_var(sock, "FLT")
    report["gFLT"] = flt
    sock.close()

    # 리포트
    print("=" * 46)
    print("R01 결과 — 실험계획표에 기입:")
    print(f"  gFLT = {flt} {'(정상)' if flt == 0 else '⚠ 폴트! 매뉴얼 4장 점검'}")
    print(f"  폴링 주기 = {report['폴링 주기']}")
    print(f"  gSTA = 3 (활성화 정상)")
    print(f"  전류 변수 = {report['전류 변수']}")
    print(f"  개폐 왕복 = {report['개폐 왕복']}")
    print("=" * 46)
    ok = flt == 0 and obj_c == 3 and obj_o == 3
    print("판정:", "✓ 전체 정상 — R02부터 진행 가능" if ok else "⚠ 위 경고 항목 해결 후 진행")


if __name__ == "__main__":
    main()
