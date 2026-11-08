"""Run the whole AIF/0.9 test suite. Exit code 0 means everything passed."""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILES = [
    "test_roundtrip.py",
    "test_edge_cases.py",
    "test_array_objects.py",
]


def main():
    print("#" * 70)
    print("# AIF/0.9 FULL TEST SUITE")
    print("#" * 70)

    all_ok = True
    for filename in FILES:
        result = subprocess.run(
            [sys.executable, str(HERE / filename)],
            cwd=str(HERE.parent),
        )
        all_ok = all_ok and result.returncode == 0
        print()

    print("#" * 70)
    print(f"# RESULT: {'ALL TESTS PASSED' if all_ok else 'SOME TESTS FAILED'}")
    print("#" * 70)
    raise SystemExit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
