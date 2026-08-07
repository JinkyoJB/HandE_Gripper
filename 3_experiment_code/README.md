# Hand-E Sim-to-Real 정합성 실험 제어 코드

Hand-E Sim-to-Real 정합성 실험의 런 테이블(R01~R10)을 실행하는 코드.
실험 PC(노트북)에서 UR 컨트롤러의 Robotiq URCap 소켓(63352)으로 그리퍼를 제어한다.

## 요구 사항

- Python 3.8 이상 (표준 라이브러리만 사용)
- PC와 로봇이 같은 대역: PC `192.168.1.50`, 로봇 `192.168.1.10` (다르면 `config.py` 수정)
- (R10 자동 이동 시에만) `pip install ur_rtde`

## 파일 구성

| 파일 | 역할 |
|---|---|
| `config.py` | IP·포트·런 파라미터 (레벨/반복수 전부 여기서 수정) |
| `hande_client.py` | 63352 소켓 클라이언트 (SET/GET, 활성화, 파지 대기) |
| `logger.py` | 별도 소켓으로 gPO/gOBJ/gSTA/gFLT(+CUR) 고속 폴링 → CSV, 이벤트 마커 |
| `run.py` | 런 실행기 (아래 사용법) |

## 사용법 — 실험계획표 순서대로

```bash
python run.py r01        # 점검: 연결·활성화·변수 지원·폴링 주기 실측
python run.py r02        # 무부하 끝점 gPO (5회)
python run.py r03        # rPR 7단계 버니어 실측 — 화면 안내에 따라 캘리퍼스 값 입력
python run.py r04        # 속도 스텝응답 (rSP 5단계 × 3회)
python run.py r05        # 힘 스윕 — 시편 A 파지 10초 유지 (rFR 5단계 × 3회)
python run.py r06        # (선택) 인장 유지력 — 로드셀 값 수동 입력
python run.py r07        # gOBJ 타이밍 — 시편 A, rFR×rSP 16조합 × 2회
python run.py r08        # 무부하 폐합 대조군 (rSP 4단계 × 2회)
python run.py r09-draw   # 미학습 조합 10종 추첨 (최초 1회, r09_combos.csv 생성)
python run.py r09        # 미학습 조합 실행
python run.py r10        # Grasp Size: 파지→100mm→10초 유지 (--ur: UR 자동 이동)
python run.py summary    # 모든 런 결과 → 결과 기입용 문장으로 요약 출력·저장
```

## 결과 기입 워크플로

실험 PC는 로봇과 랜선 직결(인터넷 없음)이므로 현장에서 결과를 자동 기입하지 않는다.

1. 실험 종료 후 `python run.py summary` → 런별 '결과 기입' 문장이 출력·저장됨
2. `logs/` 폴더를 작업 PC로 복사해 실험계획표를 채운다
   (또는 summary 출력을 직접 복사·붙여넣기)

## 출력

`logs/` 폴더에 런마다 3종:

- `handE_R{런}_{일시}.csv` — 원시 폴링 시계열 (t_perf, wall_time, POS, OBJ, STA, FLT[, CUR])
- `handE_R{런}_{일시}_events.csv` — 명령 시점 마커 (시계열과 같은 t_perf 축)
- `handE_R{런}_{일시}_result.csv` — 런 요약 (실험계획표 결과 기입용 값)

R11(시뮬 비교)은 `r09_combos.csv`와 R09/R10 이벤트 CSV의 명령 시퀀스를 Isaac Sim에 재생하여 수행한다.

## 주의

- **전류(gCU)**: URCap 소켓이 전류 변수를 노출하지 않는 버전이 있다. R01이 지원 여부를
  자동 확인하며, 미지원이면 R05는 gOBJ/gPO 기반으로만 기록된다.
- 매 런 시작 시 rACT 재활성화(자가 캘리브레이션)가 자동 수행된다 — 개체 기준점 통일 목적.
- R03에서 캘리퍼스 측정 중에는 절대 새 명령을 보내지 않는다 (스크립트가 입력 대기 상태로 보장).
- 비상 시 그리퍼 개방: `python -c "from hande_client import HandE; import config as C;
  g=HandE(C.ROBOT_IP,C.GRIPPER_PORT); g.connect(); g.set_vars(POS=0,SPE=255,FOR=0,GTO=1)"`
