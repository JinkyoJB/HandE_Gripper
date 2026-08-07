"""Hand-E Sim-to-Real 정합성 실험 설정.

실험 계획의 런 테이블(R01~R10)과 1:1 대응.
값을 바꾸면 모든 런 스크립트에 공통 적용된다.
"""

# ---------------------------------------------------------------- 통신 -----
ROBOT_IP = "192.168.1.10"      # UR 펜던트 Static IP
GRIPPER_PORT = 63352           # Robotiq URCap 그리퍼 소켓
SOCKET_TIMEOUT = 2.0           # s

# ---------------------------------------------------------------- 출력 -----
OUTPUT_DIR = "logs"            # CSV 저장 폴더 (스크립트 기준 상대경로)

# ------------------------------------------------------------ 런 파라미터 -----
# R02: 무부하 끝점
R02_REPS = 5
R02_SETTLE_S = 2.0             # 정착 대기

# R03: 버니어 직접 측정 (rPR 7단계, 닫힘/열림 방향)
R03_RPR_STEPS = [32, 64, 96, 128, 160, 192, 224]
R03_CALIPER_READS = 3          # 지점당 캘리퍼스 읽기 횟수
R03_SPE = 128
R03_FOR = 128

# R04: 속도 스텝응답
R04_RSP_LEVELS = [32, 64, 128, 192, 255]
R04_REPS = 3

# R05: 힘 스윕 (시편 A 파지 10초 유지)
R05_RFR_LEVELS = [0, 64, 128, 192, 255]
R05_REPS = 3
R05_HOLD_S = 10.0
R05_SPE = 128

# R06(선택): 인장 유지력
R06_RFR_LEVELS = [64, 128, 255]
R06_REPS = 3

# R07: gOBJ 타이밍 (시편 A 파지, rFR × rSP 16조합)
R07_RFR_LEVELS = [64, 128, 192, 255]
R07_RSP_LEVELS = [32, 128, 192, 255]
R07_REPS = 2

# R08: 무부하 폐합 대조군
R08_RSP_LEVELS = [32, 128, 192, 255]
R08_REPS = 2

# R09: 미학습 조합 (r09-draw 로 추첨하여 파일로 고정)
R09_COMBO_FILE = "r09_combos.csv"
R09_N_COMBOS = 10
R09_REPS = 2
R09_SEED = 20260714            # 추첨 재현용 시드

# R10: Grasp Size 시나리오
R10_SPECIMENS = ["A"]          # 시편 B(30mm급) 미확보 — A(Ø45mm 계장 환봉) 1종만 수행
R10_REPS = 3
R10_GRASP_SPE = 128
R10_GRASP_FOR = 128
R10_HOLD_S = 10.0
R10_LIFT_MM = 30.0             # UR 자동 상승/하강 거리 (레이저 장비 범위 고려해 100→30 축소)

# UR 이동 (R10에서 --ur 옵션 사용 시, ur_rtde 필요)
UR_LIFT_SPEED = 0.05           # m/s
UR_LIFT_ACC = 0.1              # m/s^2

# 공통: 파지 완료 대기 타임아웃
MOVE_TIMEOUT_S = 8.0
