@echo off
chcp 65001 > nul
set PYTHONUTF8=1
cd /d "%~dp0"
echo ============================================
echo  09 미학습 조합 (검증용 데이터)
echo ============================================
echo.
echo  [준비] 08과 동일 - 무부하입니다
echo    - 환봉을 손가락 사이에서 완전히 빼세요
echo    - 시작부터 끝까지 계속 비어 있어야 합니다
echo.
echo  [본 시험] 사전 추첨된 10조합 x 2회 = 20회, 약 10분
echo            Enter 후 전자동, 지켜보기만 하면 됩니다
echo.
echo  [조합 목록] untrained_combos.csv (이미 추첨 완료)
echo    1: rPR=27  rSP=41  rFR=146
echo    2: rPR=57  rSP=139 rFR=26
echo    3: rPR=19  rSP=228 rFR=77
echo    4: rPR=222 rSP=236 rFR=50
echo    5: rPR=169 rSP=106 rFR=39
echo    6: rPR=15  rSP=65  rFR=32
echo    7: rPR=229 rSP=69  rFR=230
echo    8: rPR=57  rSP=248 rFR=154
echo    9: rPR=244 rSP=56  rFR=253
echo   10: rPR=151 rSP=174 rFR=125
echo.
echo  ! 09-draw 를 다시 실행하지 마세요 (조합이 고정되어야 함)
echo  ! 이 데이터는 11 검증 전용 - 모델 피팅에 쓰면 안 됩니다
echo.
echo  [예상] 무부하이므로 gOBJ=3 (목표도달, 물체없음)
echo ============================================
echo.
pause
echo.
python run.py 09
echo.
echo ============================================
echo  09 종료. logs 폴더 CSV 확인.
echo   -^> 이 명령 시퀀스를 Isaac Sim 에 그대로 재생해
echo      실물과 비교하는 것이 11 입니다
echo ============================================
pause > nul
