"""로봇 이동 + 그리퍼를 합친 간단한 pick & place 데모.

흐름: 그리퍼 열기 -> 물체 위로 이동 -> 내려가기 -> 그리퍼 닫기(잡기)
      -> 올리기 -> 놓을 위치로 이동 -> 그리퍼 열기(놓기)

실제 좌표(PICK_POSE / PLACE_POSE)는 사용자의 셋업에 맞게 반드시 수정할 것.
안전을 위해 속도/가속도는 낮게 설정되어 있음.
"""

import time

from rtde_control import RTDEControlInterface
from rtde_receive import RTDEReceiveInterface

from config import ROBOT_IP
from gripper import RobotiqGripper

# TCP 포즈 [x, y, z, rx, ry, rz] (m, rad) — 반드시 본인 셋업 값으로 교체!
PICK_POSE = [-0.15, -0.40, 0.20, 3.14, 0.0, 0.0]
PLACE_POSE = [0.15, -0.40, 0.20, 3.14, 0.0, 0.0]
LIFT = 0.10          # 집었다 들어올릴 높이 (m)
SPEED, ACCEL = 0.15, 0.3


def main():
    rtde_c = RTDEControlInterface(ROBOT_IP)
    rtde_r = RTDEReceiveInterface(ROBOT_IP)
    gripper = RobotiqGripper().connect()
    try:
        gripper.activate()
        gripper.open()

        # 1) 집을 위치 위로 이동 후 하강
        above_pick = list(PICK_POSE); above_pick[2] += LIFT
        rtde_c.moveL(above_pick, SPEED, ACCEL)
        rtde_c.moveL(PICK_POSE, SPEED, ACCEL)

        # 2) 잡기
        result = gripper.close_gripper()
        print("잡기 결과:", result)  # obj가 1/2면 물체 물림 성공

        # 3) 들어올려 놓을 위치로 이동
        rtde_c.moveL(above_pick, SPEED, ACCEL)
        above_place = list(PLACE_POSE); above_place[2] += LIFT
        rtde_c.moveL(above_place, SPEED, ACCEL)
        rtde_c.moveL(PLACE_POSE, SPEED, ACCEL)

        # 4) 놓기
        gripper.open()
        rtde_c.moveL(above_place, SPEED, ACCEL)

        print("pick & place 완료.")
    finally:
        gripper.close()
        rtde_c.stopScript()
        rtde_c.disconnect()
        rtde_r.disconnect()


if __name__ == "__main__":
    main()
