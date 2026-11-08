"""One-command verification for the whole AIF/0.9 delivery.

    python AIF/tests/verify_all.py

Runs every check from a clean state and reports a single PASS/FAIL summary.
Requires Python 3.10+, tiktoken, and Node.js >= 18 (for the JS reference
implementation). No npm packages are needed.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CHECKS = [
    ("单元测试 104 项",
     [sys.executable, "AIF/tests/run_all.py"],
     ["ALL TESTS PASSED"]),
    ("规范示例与实现一致",
     [sys.executable, "AIF/tests/test_spec_examples.py"],
     ["SPEC EXAMPLES: 2/2 MATCH"]),
    ("Python / JS 双实现一致性",
     [sys.executable, "AIF/tests/cross_validate.py"],
     ["AGREE", "Two independent implementations agree"]),
    ("随机 fuzz 720 组",
     [sys.executable, "AIF/tests/fuzz_roundtrip.py"],
     ["silent corruptions : 0", "cross-language disagreements: 0"]),
    ("示例文件生成与校验",
     [sys.executable, "AIF/examples/make_examples.py"],
     ["5/5 PASS"]),
    ("V8 benchmark 17 类",
     [sys.executable, "AIF/benchmarks/benchmark_v8.py"],
     ["17/17 PASS"]),
    ("历史 V7 重跑",
     [sys.executable, "test_token_benchmark_v7_rerun.py"],
     ["8/8 PASS"]),
    ("公开测试向量未被篡改",
     [sys.executable, "AIF/conformance/build_vectors.py", "--verify"],
     ["VERIFIED (42 vectors"]),
    ("双向兼容性 A<->B",
     [sys.executable, "AIF/conformance/bidirectional.py"],
     ["双向兼容性: PASS"]),
]


def main():
    print("# AIF/0.9 FULL VERIFICATION")
    print("#" * 72)
    if shutil.which("node") is None:
        print("WARNING: Node.js not found -> cross-language checks will fail.")
        print("         Install Node.js >= 18 to run them (no npm packages needed).")
    print()

    results = []
    for name, cmd, required in CHECKS:
        proc = subprocess.run(
            cmd, cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        missing = [token for token in required if token not in output]
        ok = proc.returncode == 0 and not missing
        results.append((name, ok))
        print(f"  {name:<34} {'PASS' if ok else 'FAIL'}")
        if not ok:
            if missing:
                print("      missing expected output:", missing)
            print("      exit code:", proc.returncode)
            print("      last lines:")
            for line in output.strip().splitlines()[-12:]:
                print("        " + line)

    print("#" * 72)
    passed = sum(ok for _, ok in results)
    print(f"# RESULT: {passed}/{len(CHECKS)} CHECKS PASSED")
    if passed != len(CHECKS):
        print("# Failed checks:")
        for name, ok in results:
            if not ok:
                print("#   -", name)
        return 1
    print("# All verification steps green.")
    print("#" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
