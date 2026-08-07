@echo off
chcp 65001 > nul
set PYTHONUTF8=1
cd /d "%~dp0"
echo ============================================
echo  R10 파지 시나리오 (UR 자동 이동/회전)
echo ============================================
echo.
echo  ***** 로봇이 자동으로 크게 움직입니다 *****
echo    - UR 을 Remote Control 모드로 두세요
echo    - 비상정지 버튼을 손 닿는 곳에
echo    - 처음이라면 먼저 리허설을 권장합니다:
echo        python r10_scenario.py --dry
echo      (파지 없이 경로만 돌려 충돌 여부 확인)
echo.
echo  [시나리오] 회차마다
echo    파지 -^> 상승 30mm -^> 3초 유지
echo    -^> 2시방향 50mm 이동 -^> joint6 +90 / -90 -^> 복귀
echo    -^> 10시방향 50mm 이동 -^> joint6 +90 / -90 -^> 복귀
echo    -^> 하강 -^> 놓기
echo    총 3회 반복
echo.
echo  [사람이 하는 일] 회차 시작 시 Enter 1번
echo    활성화 후 "파지 위치로 이동한 뒤 Enter" 프롬프트에서
echo    그리퍼를 시편 위치로 수동 이동 -^> Enter -^> 이후 전자동
echo.
echo  [정상 신호] 전 구간에서 gOBJ=2 유지
echo    이동/회전 중 gOBJ 가 바뀌면 미끄러진 것
echo ============================================
echo.
pause
echo.
python r10_scenario.py
echo.
echo ============================================
echo  R10 종료 - 실험실 작업 완료!
echo   화면의 [R11 시뮬 재생 사양] 을 기록하세요
echo ============================================
pause > nul
