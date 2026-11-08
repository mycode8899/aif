"""V7 8-dataset round-trip regression, including single-record shapes."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aif import json_to_aif, aif_to_json  # noqa: E402
from _v7_data import DATASETS, RECORDS_PER_DATASET  # noqa: E402


def run():
    print("=" * 70)
    print("TEST 1/3  V7 round-trip (8 datasets x 1/20/1000 records)")
    print("=" * 70)

    passed = 0
    total = 0

    for name, make_records in DATASETS:
        all_ok = True
        detail = ""

        for n in (1, 20, RECORDS_PER_DATASET):
            records = make_records(n)
            try:
                text = json_to_aif(records)
                decoded = aif_to_json(text)
                ok = decoded == records and type(decoded) is type(records)
            except Exception as exc:
                ok = False
                detail = f"{type(exc).__name__}: {exc}"

            total += 1
            passed += int(ok)
            if not ok:
                all_ok = False
                if not detail:
                    detail = "structure or type mismatch"

        # Single dict (not a list) must come back as a dict.
        single = make_records(1)[0]
        try:
            text = json_to_aif(single)
            decoded = aif_to_json(text)
            ok = decoded == single and type(decoded) is dict
        except Exception as exc:
            ok = False
            detail = f"single dict: {type(exc).__name__}: {exc}"
        total += 1
        passed += int(ok)
        if not ok:
            all_ok = False

        print(f"  {name:<30} {'PASS' if all_ok else 'FAIL'}  {detail}")
        if not all_ok and detail:
            print(f"    {detail[:160]}")

    print("-" * 70)
    print(f"  subtotal: {passed}/{total} PASS")
    return passed, total


if __name__ == "__main__":
    ok, total = run()
    raise SystemExit(0 if ok == total else 1)
