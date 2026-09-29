@echo off
chcp 65001 > nul
set PYTHONUTF8=1
cd /d "%~dp0"
echo ============================================
echo  05 사전 검증 (로드셀 힘 전달 확인)
echo ============================================
echo  rFR=0(저력) 1회 -^> rFR=255(최대력) 1회
echo  각 10초 유지하는 동안 로드셀 값을 읽어 입력
echo.
echo  준비: 로드셀 영점(tare), 환봉 위치핀 고정,
echo        패드 정중앙/수직 정렬
echo ============================================
echo.
python force_precheck.py
echo.
pause > nul
