#!/usr/bin/env python3
"""
라이선스 키 생성 도구

사용법:
  python generate_license.py        # 1개 생성
  python generate_license.py 10     # 10개 생성

생성된 키를 Google Sheets의 licenses 시트에 붙여넣기:
  license_key | used_count | max_count | status | created_at | last_used
  KN-XXXX-XXXX | 0         | 3         | active | 2026-02-25 |
"""

import random
import string
import sys
from datetime import date


def generate_key():
    """KN-XXXX-XXXX 형태의 라이선스 키 생성"""
    chars = string.ascii_uppercase + string.digits
    part1 = ''.join(random.choices(chars, k=4))
    part2 = ''.join(random.choices(chars, k=4))
    return f"KN-{part1}-{part2}"


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    today = date.today().isoformat()

    print(f"\n--- 라이선스 키 {count}개 생성 ---\n")
    print(f"{'라이선스 키':<16} | used_count | max_count | status | created_at")
    print("-" * 70)

    for _ in range(count):
        key = generate_key()
        print(f"{key:<16} | 0          | 3         | active | {today}")

    print(f"\n위 내용을 Google Sheets에 복사하세요.")
    print(f"(헤더 행: license_key | used_count | max_count | status | created_at | last_used)\n")


if __name__ == "__main__":
    main()
