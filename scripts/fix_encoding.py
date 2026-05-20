#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""과거 인코딩 복구 작업의 보관용 안내 스크립트.

이 스크립트는 더 이상 자동 치환을 수행하지 않습니다. 예전에는 깨진 주석과
로마자화된 문구를 대량 치환하는 용도로 사용했지만, 현재 저장소는 한국어
기준 문서와 명시적인 언어 검사(`scripts/check_language_artifacts.py`)를
사용합니다.

새로운 인코딩 문제가 발견되면 이 파일을 실행해 고치지 말고, 아래 순서로
처리하세요.

1. `python scripts/check_language_artifacts.py`로 문제 범위를 확인합니다.
2. 실제 사용자 노출 문구인지, 종목명/데이터/외부 고유명사인지 분류합니다.
3. 사용자 노출 문구라면 해당 파일을 직접 한국어로 수정합니다.
4. 수정 후 언어 검사와 변경 범위에 맞는 테스트를 실행합니다.

이 파일을 남겨두는 이유는 같은 유형의 대량 인코딩 사고가 다시 발생했을 때
과거 복구 방식이 있었다는 사실과 현재 권장 절차를 한 곳에서 확인하기 위해서입니다.
"""

from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(
        description="보관용 안내: 인코딩 문제는 언어 검사 후 직접 수정하세요."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="호환성을 위해 남겨둔 옵션입니다. 실제 변경은 수행하지 않습니다.",
    )
    parser.add_argument(
        "--path",
        default=".",
        help="호환성을 위해 남겨둔 옵션입니다. 실제 스캔은 수행하지 않습니다.",
    )
    parser.parse_args()

    print("이 스크립트는 보관용 안내 스크립트이며 파일을 수정하지 않습니다.")
    print("인코딩/언어 문제 검사는 다음 명령을 사용하세요:")
    print("  python scripts/check_language_artifacts.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
