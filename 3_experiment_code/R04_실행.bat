@echo off
chcp 65001 > nul
set PYTHONUTF8=1
cd /d "%~dp0"
echo ============================================
echo  R04 속도 스텝응답 (rSP - 폐합속도 커브)
echo  - 손가락 사이를 비우고 시작 (무부하)
echo  - 전자동: rSP 5단계 x 3회 x 개폐
echo  - (선택) CCTV 녹화 ON, fps 메모
echo ============================================
echo.
python run.py r04
echo.
echo ============================================
echo  R04 종료. logs 폴더 CSV 확인.
echo  창을 닫으려면 아무 키나 누르세요.
echo ============================================
pause > nul
