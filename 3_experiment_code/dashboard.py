"""UR Dashboard 서버(포트 29999) 제어 - 순수 소켓, 외부 패키지 불필요.

전원 켜기 / 브레이크 해제 / 프로그램 로드·재생·정지 등을 명령한다.
문서: UR Dashboard Server 명령어 목록 참고.
"""

import socket
import time

from config import ROBOT_IP, DASHBOARD_PORT


class Dashboard:
    def __init__(self, ip=ROBOT_IP, port=DASHBOARD_PORT, timeout=5.0):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.sock = None

    def connect(self):
        self.sock = socket.create_connection((self.ip, self.port), self.timeout)
        # 접속 시 로봇이 보내는 환영 메시지 비우기
        self.sock.recv(4096)
        return self

    def send(self, command):
        """명령 한 줄 전송 후 응답 문자열 반환."""
        self.sock.sendall((command + "\n").encode())
        return self.sock.recv(4096).decode().strip()

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    # 컨텍스트 매니저로도 사용 가능: with Dashboard() as db: ...
    def __enter__(self):
        return self.connect()

    def __exit__(self, *args):
        self.close()

    # --- 자주 쓰는 명령 헬퍼 ---
    def robotmode(self):
        return self.send("robotmode")

    def safetystatus(self):
        return self.send("safetystatus")

    def power_on(self):
        return self.send("power on")

    def brake_release(self):
        return self.send("brake release")

    def power_off(self):
        return self.send("power off")

    def load(self, program_name):
        return self.send(f"load {program_name}")

    def play(self):
        return self.send("play")

    def stop(self):
        return self.send("stop")


if __name__ == "__main__":
    with Dashboard() as db:
        print("PolyScope 버전:", db.send("PolyscopeVersion"))
        print("로봇 모드   :", db.robotmode())
        print("안전 상태   :", db.safetystatus())

        # 전원이 꺼져 있다면 켜고 브레이크 해제 (필요할 때만 주석 해제)
        # print("전원 켜기   :", db.power_on())
        # time.sleep(5)
        # print("브레이크 해제:", db.brake_release())
        # time.sleep(5)
        # print("로봇 모드   :", db.robotmode())  # RUNNING 이면 준비 완료
