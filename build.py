#!/usr/bin/env python3
"""
키즈노트 백업 프로그램 빌드 스크립트
- macOS: 실행파일 생성 (onedir)
- Windows: .exe 실행파일 생성 (onefile, 콘솔 숨김)

사용법:
  pip install pyinstaller
  python build.py
"""

import platform
import subprocess
import sys


def build():
    system = platform.system()
    app_name = "키즈노트백업"

    separator = ";" if system == "Windows" else ":"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        f"--name={app_name}",
        "--add-data", f"kidsnote_backup.py{separator}.",
        "--noconfirm",
        "--clean",
    ]

    if system == "Windows":
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")

    cmd.append("kidsnote_app.py")

    print(f"빌드 시작 ({system})...")
    print(f"명령어: {' '.join(cmd)}")
    print()

    result = subprocess.run(cmd)

    if result.returncode == 0:
        if system == "Darwin":
            print(f"\n빌드 성공! dist/{app_name} 폴더가 생성되었습니다.")
            print(f"dist/{app_name} 폴더를 zip으로 압축하여 배포하세요.")
        elif system == "Windows":
            print(f"\n빌드 성공! dist\\{app_name}.exe 가 생성되었습니다.")
            print(f"다른 Windows 사용자에게 dist\\{app_name}.exe 파일을 배포하세요.")
        else:
            print(f"\n빌드 성공! dist/{app_name} 이 생성되었습니다.")
    else:
        print("\n빌드 실패!")
        sys.exit(1)


if __name__ == "__main__":
    build()
