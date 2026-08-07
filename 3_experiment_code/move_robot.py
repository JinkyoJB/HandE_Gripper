"""UR 로봇 이동 예제 - ur_rtde 라이브러리 사용.

설치:  pip install ur_rtde

주의:
  - 실행 전 로봇이 켜져 있고(브레이크 해제, RUNNING 모드), 원격 제어(Remote Control)
    또는 로컬 모드에서 외부 제어가 허용되어 있어야 한다.
  - moveL/moveJ 는 실제로 로봇을 움직인다. 주변 안전을 반드시 확보하고,
    처음에는 속도/가속도를 낮게(아래 값) 두고 테스트할 것.
"""

import time

from rtde_control import RTDEControlInterface
from rtde_receive import RTDEReceiveInterface

from config import ROBOT_IP


def main():
    rtde_c = RTDEControlInterface(ROBOT_IP)
    rtde_r = RTDEReceiveInterface(ROBOT_IP)
    try:
        # 현재 상태 읽기
        q = rtde_r.getActualQ()             # 관절 각도 [rad] x6
        tcp = rtde_r.getActualTCPPose()     # TCP 포즈 [x,y,z,rx,ry,rz]
        print("현재 관절각(rad):", [round(v, 4) for v in q])
        print("현재 TCP 포즈   :", [round(v, 4) for v in tcp])

        # --- 관절 공간 이동 (moveJ) ---
        # 현재 위치에서 1번 관절만 +10도(약 0.175rad) 돌렸다 되돌리기
        speed, accel = 0.3, 0.3   # 낮게 시작 (rad/s, rad/s^2)
        target = list(q)
        target[0] += 0.175
        print("moveJ 이동...")
        rtde_c.moveJ(target, speed, accel)
        time.sleep(0.5)
        rtde_c.moveJ(q, speed, accel)       # 원위치 복귀

        # --- 직선 이동 (moveL) 예시 (주석) ---
        # TCP를 Z축으로 +5cm 올렸다 내리기
        # pose_up = list(tcp); pose_up[2] += 0.05
        # rtde_c.moveL(pose_up, 0.1, 0.1)     # 속도 0.1m/s, 가속 0.1m/s^2
        # rtde_c.moveL(tcp, 0.1, 0.1)

        print("완료.")
    finally:
        rtde_c.stopScript()   # 제어 스크립트 정리
        rtde_c.disconnect()
        rtde_r.disconnect()


if __name__ == "__main__":
    main()
