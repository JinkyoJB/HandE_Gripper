"""Robotiq 2F 그리퍼 제어 - 순수 소켓, 외부 패키지 불필요.

로봇에 Robotiq URCap이 설치되어 있으면 로봇 IP의 포트 63352에서
그리퍼 소켓 서버가 열린다. ASCII 명령으로 제어한다.

명령 형식:
  SET <VAR> <VALUE>\n   -> "ack" 응답
  GET <VAR>\n           -> "<VAR> <value>" 응답

주요 변수:
  ACT 활성화(1), GTO 목표추종(1), POS 위치(0=열림 ~ 255=닫힘),
  SPE 속도(0~255), FOR 힘(0~255), STA 상태, OBJ 물체감지, PRE 목표위치

주의: POS의 0/255가 열림/닫힘인지는 2F-85/2F-140 모델·장착에 따라 다를 수 있음.
"""

import socket
import time

from config import ROBOT_IP, GRIPPER_PORT

OPEN_POS = 0      # 완전 열림
CLOSE_POS = 255   # 완전 닫힘


class RobotiqGripper:
    def __init__(self, ip=ROBOT_IP, port=GRIPPER_PORT, timeout=3.0):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.sock = None

    def connect(self):
        self.sock = socket.create_connection((self.ip, self.port), self.timeout)
        return self

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def __enter__(self):
        return self.connect()

    def __exit__(self, *args):
        self.close()

    def _set(self, var, value):
        self.sock.sendall(f"SET {var} {value}\n".encode())
        return self.sock.recv(1024).decode().strip()  # "ack"

    def _get(self, var):
        self.sock.sendall(f"GET {var}\n".encode())
        resp = self.sock.recv(1024).decode().strip()  # "VAR value"
        return int(resp.split()[1])

    def activate(self, timeout=10.0):
        """그리퍼 활성화(캘리브레이션). STA==3 이 되면 완료."""
        if self._get("STA") == 3:
            return  # 이미 활성화됨
        self._set("ACT", 0)
        time.sleep(0.5)
        self._set("ACT", 1)
        self._set("GTO", 1)
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self._get("STA") == 3:
                return
            time.sleep(0.2)
        raise TimeoutError("그리퍼 활성화 시간 초과")

    def move(self, position, speed=255, force=100, wait=True):
        """position 0~255 로 이동. wait=True 면 동작 완료까지 대기."""
        position = max(0, min(255, int(position)))
        self._set("SPE", speed)
        self._set("FOR", force)
        self._set("GTO", 1)
        self._set("POS", position)
        if not wait:
            return
        # OBJ: 0=이동중, 1/2=물체 물림, 3=목표 도달
        t0 = time.time()
        while time.time() - t0 < 5.0:
            obj = self._get("OBJ")
            if obj != 0:
                break
            time.sleep(0.05)
        return {"pos": self._get("POS"), "obj": self._get("OBJ")}

    def open(self, **kw):
        return self.move(OPEN_POS, **kw)

    def close_gripper(self, **kw):
        return self.move(CLOSE_POS, **kw)


if __name__ == "__main__":
    with RobotiqGripper() as g:
        print("활성화 중...")
        g.activate()
        print("현재 위치:", g._get("POS"))

        print("열기...")
        print(g.open())
        time.sleep(1)

        print("닫기...")
        print(g.close_gripper())  # obj가 1/2면 물체를 물었다는 뜻
        time.sleep(1)

        print("반쯤 열기...")
        print(g.move(128))
