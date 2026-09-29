"""Hand-E Sim-to-Real 정합성 실험 설정.

실험 계획의 런 테이블(01~10)과 1:1 대응.
값을 바꾸면 모든 런 스크립트에 공통 적용된다.
"""

# ---------------------------------------------------------------- 통신 -----
ROBOT_IP = "192.168.1.10"      # UR 펜던트 Static IP
GRIPPER_PORT = 63352           # Robotiq URCap 그리퍼 소켓
SOCKET_TIMEOUT = 2.0           # s

# ---------------------------------------------------------------- 출력 -----
OUTPUT_DIR = "logs"            # CSV 저장 폴더 (스크립트 기준 상대경로)

# ------------------------------------------------------------ 런 파라미터 -----
# 02: 무부하 끝점
EXP02_REPS = 5
EXP02_SETTLE_S = 2.0             # 정착 대기

# 03: 버니어 직접 측정 (rPR 7단계, 닫힘/열림 방향)
EXP03_RPR_STEPS = [32, 64, 96, 128, 160, 192, 224]
EXP03_CALIPER_READS = 3          # 지점당 캘리퍼스 읽기 횟수
EXP03_SPE = 128
EXP03_FOR = 128

# 04: 속도 스텝응답
EXP04_RSP_LEVELS = [32, 64, 128, 192, 255]
EXP04_REPS = 3

# 05: 힘 스윕 (시편 A 파지 10초 유지)
EXP05_RFR_LEVELS = [0, 64, 128, 192, 255]
EXP05_REPS = 3
EXP05_HOLD_S = 10.0
EXP05_SPE = 128

# 06(선택): 인장 유지력
EXP06_RFR_LEVELS = [64, 128, 255]
EXP06_REPS = 3

# 07: gOBJ 타이밍 (시편 A 파지, rFR × rSP 16조합)
EXP07_RFR_LEVELS = [64, 128, 192, 255]
EXP07_RSP_LEVELS = [32, 128, 192, 255]
EXP07_REPS = 2

# 08: 무부하 폐합 대조군
EXP08_RSP_LEVELS = [32, 128, 192, 255]
EXP08_REPS = 2

# 09: 미학습 조합 (r09-draw 로 추첨하여 파일로 고정)
EXP09_COMBO_FILE = "untrained_combos.csv"
EXP09_N_COMBOS = 10
EXP09_REPS = 2
EXP09_SEED = 20260714            # 추첨 재현용 시드

# 10: Grasp Size 시나리오
EXP10_SPECIMENS = ["A"]          # 시편 B(30mm급) 미확보 — A(Ø45mm 계장 환봉) 1종만 수행
EXP10_REPS = 3
EXP10_GRASP_SPE = 128
EXP10_GRASP_FOR = 128
EXP10_HOLD_S = 10.0
EXP10_LIFT_MM = 30.0             # UR 자동 상승/하강 거리 (레이저 장비 범위 고려해 100→30 축소)

# UR 이동 (10에서 --ur 옵션 사용 시, ur_rtde 필요)
UR_LIFT_SPEED = 0.05           # m/s
UR_LIFT_ACC = 0.1              # m/s^2

# 공통: 파지 완료 대기 타임아웃
MOVE_TIMEOUT_S = 8.0
