@echo off
chcp 65001 >nul
title 키즈노트 백업 프로그램 빌드

echo ============================================================
echo   키즈노트 백업 프로그램 - Windows 빌드 도구
echo ============================================================
echo.

:: Python 설치 확인
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [1/4] Python이 설치되어 있지 않습니다. 설치를 시작합니다...
    echo.
    echo Python 공식 설치 파일을 다운로드합니다...
    curl -o python_installer.exe https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe
    echo.
    echo Python 설치 중... (자동 설치, PATH 추가 포함)
    python_installer.exe /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
    del python_installer.exe
    echo Python 설치 완료!
    echo.
    echo ** 중요: 이 창을 닫고 다시 실행해주세요. **
    echo ** (PATH 설정이 반영되려면 재시작이 필요합니다) **
    pause
    exit /b
) else (
    echo [1/4] Python 확인 완료
    python --version
)

echo.
echo [2/4] 필요한 라이브러리 설치 중...
pip install requests pyinstaller --quiet
echo 라이브러리 설치 완료!

echo.
echo [3/4] 프로그램 빌드 중... (1~2분 소요)
python -m PyInstaller --onefile --name=키즈노트백업 --add-data "kidsnote_backup.py;." --noconfirm --clean kidsnote_app.py

echo.
if exist "dist\키즈노트백업.exe" (
    echo [4/4] ============================================================
    echo   빌드 성공!
    echo   실행 파일: dist\키즈노트백업.exe
    echo ============================================================
    echo.
    echo dist 폴더를 엽니다...
    explorer dist
) else (
    echo [오류] 빌드에 실패했습니다.
)

echo.
pause
