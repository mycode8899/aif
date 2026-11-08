"""
AIF TOKEN BENCHMARK V7 - RERUN (AIF/0.9 only)

目的
----
在不改动任何数据集的前提下，重新验证恢复包中重建版 AIF/0.9 的
token 数字和 8/8 round-trip，让「阶段 1」真正闭环。

与原始 test_token_benchmark_v7.py 的差别
----------------------------------------
1. 8 个数据集生成函数直接从 V7 原件 import，逐字复用，没有改动任何数据。
2. AIF 0.8 / Compact 的源文件未恢复，相关列输出 N/A，不估算、不伪造。
3. 每个数据集都真正 decode，并做结构相等比较后才写 PASS。
4. Reduction 保留负值，不隐藏 AIF 比 JSON 更耗 token 的数据集。

注意
----
本结果来自恢复包的重建版 encoder/decoder（使用 @missing 占位语法），
与项目背景中旧版 V7 的数字不可直接比较。

运行
----
python test_token_benchmark_v7_rerun.py
"""

import sys
import types

# V7 原件顶层 import 了未恢复的 aif_encoder_v08 / aif_decoder_v08。
# 这里用空实现占位，只为借用它的 8 个数据集生成函数；
# 这些占位函数不参与任何编码、解码或 token 计数。
for _module_name, _funcs in {
    "aif_encoder_v08": {"json_to_aif": lambda *a, **k: ""},
    "aif_decoder_v08": {"aif_to_json": lambda *a, **k: []},
}.items():
    _module = types.ModuleType(_module_name)
    for _func_name, _func in _funcs.items():
        setattr(_module, _func_name, _func)
    sys.modules[_module_name] = _module

import tiktoken

import test_token_benchmark_v7 as v7
from aif_encoder_v09 import json_to_aif
from aif_decoder_v09 import aif_to_json


TOKENIZER_NAME = v7.TOKENIZER_NAME
RECORDS = v7.RECORDS

enc = tiktoken.get_encoding(TOKENIZER_NAME)


def token_count(text):
    return len(enc.encode(text))


# 数据集生成函数全部引用 V7 原件，未复制、未修改
DATASETS = [
    ("1. Flat Agent Records", v7.make_flat_agent_records),
    ("2. Nested Agent State", v7.make_nested_agent_state),
    ("3. Tool Calls", v7.make_tool_calls),
    ("4. Multiple Tool Calls", v7.make_multiple_tool_calls),
    ("5. Messages", v7.make_messages),
    ("6. Memory", v7.make_memory),
    ("7. Optional Tool Results", v7.make_optional_tool_results),
    ("8. Mixed Agent State", v7.make_mixed_agent_state),
]


def main():
    print("=" * 74)
    print("AIF TOKEN BENCHMARK V7 - RERUN (AIF/0.9 only)")
    print("=" * 74)
    print(f"Tokenizer:       {TOKENIZER_NAME}")
    print(f"Records/dataset: {RECORDS:,}")
    print("Data source:     test_token_benchmark_v7.py (原件, 数据集未改动)")
    print("AIF 0.8/Compact: N/A (源文件未恢复, 不估算不伪造)")
    print("Build:           恢复包重建版 encoder/decoder (@missing 语法)")
    print("Warning:         与背景中旧版 V7 数字不可直接比较")
    print("=" * 74)

    results = []

    for name, make_records in DATASETS:
        records = make_records(RECORDS)
        json_tokens = token_count(v7.json_text(records))

        try:
            aif_text = json_to_aif(records)
            aif_tokens = token_count(aif_text)
            reduction = (json_tokens - aif_tokens) / json_tokens * 100

            try:
                decoded = aif_to_json(aif_text)
                passed = v7.normalize(decoded) == v7.normalize(records)
                status = "PASS" if passed else "FAIL"
                error = ""
            except Exception as exc:
                status = "FAIL"
                error = f"  decode error: {exc!r}"

            print()
            print(name)
            print(f"  Records:            {len(records):,}")
            print(f"  JSON tokens:        {json_tokens:,}")
            print(f"  AIF 0.9 tokens:     {aif_tokens:,}")
            print(f"  AIF 0.8 tokens:     N/A (源文件未恢复)")
            print(f"  Compact tokens:     N/A (源文件未恢复)")
            print(f"  Reduction:          {reduction:+.2f}%")
            print(f"  AIF 0.9 Round-trip: {status}{error}")

            results.append({
                "name": name,
                "json": json_tokens,
                "aif": aif_tokens,
                "reduction": reduction,
                "status": status,
            })

        except Exception as exc:
            print()
            print(name)
            print(f"  JSON tokens:        {json_tokens:,}")
            print(f"  AIF 0.9 encode error: {exc!r}")
            print(f"  AIF 0.9 Round-trip: FAIL")
            results.append({
                "name": name,
                "json": json_tokens,
                "aif": None,
                "reduction": None,
                "status": "FAIL",
            })

    print()
    print("=" * 74)
    print("SUMMARY")
    print("-" * 74)
    for r in results:
        if r["aif"] is None:
            aif_text = "N/A"
            reduction_text = "N/A"
        else:
            aif_text = f'{r["aif"]:,}'
            reduction_text = f'{r["reduction"]:+8.2f}%'
        print(
            f'{r["name"]:<30} '
            f'JSON={r["json"]:>9,} '
            f'AIF0.9={aif_text:>9} '
            f'Reduction={reduction_text} '
            f'RT={r["status"]}'
        )

    passed = sum(1 for r in results if r["status"] == "PASS")
    worse = [
        r["name"] for r in results
        if r["reduction"] is not None and r["reduction"] < 0
    ]
    print("-" * 74)
    print(f"Round-trip: {passed}/8 PASS")
    print(f"AIF 比 JSON 更耗 token 的数据集: {len(worse)} 组"
          + (": " + ", ".join(worse) if worse else ""))
    print("=" * 74)

    if passed != 8:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
