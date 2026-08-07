"""그리퍼 소켓(63352) 읽기 전용 점검 — 그리퍼를 움직이지 않는다.

Robotiq URCap 데몬이 63352에서 응답하는지, 어떤 읽기 변수가 지원되는지 확인만 한다.
SET/이동 명령을 보내지 않으므로 안전하다.
"""
import socket
import sys

IP = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.10"
PORT = 63352
READ_VARS = ["STA", "PRE", "POS", "OBJ", "FLT", "CUR", "COU"]

STA_MEANING = {0: "리셋됨", 1: "활성화 중", 2: "미사용", 3: "활성 완료"}
OBJ_MEANING = {0: "이동 중", 1: "열다 막힘(물체)", 2: "닫다 물체 파지", 3: "목표 도달(물체 없음)"}


def send_recv(sock, cmd):
    sock.sendall((cmd + "\n").encode("ascii"))
    return sock.recv(1024).decode("ascii").strip()


def main():
    print(f"=== 그리퍼 소켓 읽기 점검: {IP}:{PORT} (움직임 없음) ===\n")
    try:
        sock = socket.create_connection((IP, PORT), 2.0)
        sock.settimeout(2.0)
    except socket.timeout:
        sys.exit("✗ 연결 타임아웃 — PC IP가 192.168.1.x 대역/랜선 연결 확인")
    except ConnectionRefusedError:
        sys.exit("✗ 연결 거부 — UR에 Robotiq URCap(그리퍼)이 설치·활성 상태인지 확인")
    except OSError as e:
        sys.exit(f"✗ 연결 실패: {e}")
    print("✓ 소켓 연결 OK — URCap 데몬 응답함\n")

    print("읽기 변수 지원:")
    values = {}
    for v in READ_VARS:
        try:
            resp = send_recv(sock, f"GET {v}")
            values[v] = resp
            print(f"  {v}: {resp}")
        except Exception as e:
            print(f"  {v}: 미지원/오류 ({e})")
    sock.close()

    print("\n--- 해석 ---")
    if "STA" in values:
        try:
            sta = int(values["STA"].split()[1])
            print(f"  gSTA={sta} → {STA_MEANING.get(sta, '?')}"
                  + ("  (아직 미활성 — R01에서 activate 필요)" if sta != 3 else ""))
        except Exception:
            pass
    cur = "CUR" if values.get("CUR", "").startswith("CUR") else \
          ("COU" if values.get("COU", "").startswith("COU") else None)
    print(f"  전류 변수: {cur or '미지원 (R05는 gPO/gOBJ만 기록)'}")
    print("\n판정: 소켓 정상 — 이제 `python run.py r01`로 활성화·개폐 점검 진행 가능")


if __name__ == "__main__":
    main()
