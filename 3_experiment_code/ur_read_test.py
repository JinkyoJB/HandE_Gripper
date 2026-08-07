"""
UR5e 읽기 전용 통신 테스트 스크립트
- 로봇을 움직이지 않고 상태 데이터만 읽어옵니다.
- 통신(RTDE) 연결 확인용으로 안전하게 사용 가능합니다.

사용법:
    pip install ur_rtde
    python ur_read_test.py
"""

import math
import sys
import time

ROBOT_IP = "192.168.1.10"   # 실제 로봇 IP


def main():
    try:
        from rtde_receive import RTDEReceiveInterface
    except ImportError:
        print("[오류] ur_rtde 가 설치되어 있지 않습니다.")
        print("       다음 명령으로 설치하세요:  pip install ur_rtde")
        sys.exit(1)

    print(f"[연결 시도] {ROBOT_IP} ...")
    try:
        rtde_r = RTDEReceiveInterface(ROBOT_IP)
    except Exception as e:
        print(f"[연결 실패] {e}")
        print("  확인 사항:")
        print("   1) 로봇 전원이 켜져 있고 PC와 같은 네트워크에 있는지")
        print(f"   2) ping {ROBOT_IP} 이 되는지")
        print("   3) IP 주소가 올바른지 (티치펜던트: 설정 > 시스템 > 네트워크)")
        sys.exit(1)

    print("[연결 성공] RTDE 수신 인터페이스 연결됨\n")

    try:
        # 관절 각도 (라디안 -> 도 변환해서 함께 표시)
        q = rtde_r.getActualQ()
        q_deg = [round(math.degrees(a), 2) for a in q]
        print("관절 각도 (rad):", [round(a, 4) for a in q])
        print("관절 각도 (deg):", q_deg)

        # TCP 위치/자세 [x, y, z, rx, ry, rz]  (m, rad)
        tcp = rtde_r.getActualTCPPose()
        print("\nTCP 위치 [x,y,z](m):     ", [round(v, 4) for v in tcp[:3]])
        print("TCP 자세 [rx,ry,rz](rad):", [round(v, 4) for v in tcp[3:]])

        # 관절 속도 / TCP 속도
        print("\n관절 속도 (rad/s):", [round(v, 4) for v in rtde_r.getActualQd()])
        print("TCP 속도:        ", [round(v, 4) for v in rtde_r.getActualTCPSpeed()])

        # 로봇 상태 정보
        print("\n--- 로봇 상태 ---")
        print("로봇 모드:       ", rtde_r.getRobotMode())        # 7 = RUNNING
        print("안전 모드:       ", rtde_r.getSafetyMode())        # 1 = NORMAL
        print("디지털 입력 비트:", rtde_r.getActualDigitalInputBits())
        print("디지털 출력 비트:", rtde_r.getActualDigitalOutputBits())

        # 실시간 스트리밍 데모 (5초간 TCP Z 높이 표시)
        print("\n--- 실시간 읽기 데모 (5초) ---")
        t_end = time.time() + 5.0
        while time.time() < t_end:
            z = rtde_r.getActualTCPPose()[2]
            print(f"  TCP Z 높이: {z*1000:8.2f} mm", end="\r")
            time.sleep(0.1)
        print("\n\n[완료] 읽기 테스트 정상 종료")

    except Exception as e:
        print(f"[읽기 중 오류] {e}")
    finally:
        rtde_r.disconnect()
        print("[연결 종료]")


if __name__ == "__main__":
    main()
