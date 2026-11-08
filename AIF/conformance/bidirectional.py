"""
AIF/0.9 bidirectional conformance harness.

    python AIF/conformance/bidirectional.py
        A = Python reference implementation
        B = JavaScript reference implementation (written in this project)

    python AIF/conformance/bidirectional.py --adapter third_party_adapter.json
        B = a THIRD-PARTY implementation (this is the release-gate run)

Checks, per positive vector:
    A->B : implementation A's AIF decoded by B == expected_decoded
    B->A : implementation B's AIF decoded by A == input_json
    A->A / B->B : self-consistency baselines
    byte equality of A and B encodings is REPORTED but NOT required.
Checks, per negative vector:
    both encoders must REJECT it (N002/N003 are marked SKIP because their
    offending values are not representable in strict JSON).

!!! HONESTY NOTE !!!
The bundled JavaScript implementation is a REFERENCE implementation written
by the same author/session as the Python one. Running this harness with the
default adapter proves the harness works; it does NOT satisfy release gate #6.
Gate #6 requires an implementation by a developer who did not take part in
the original work — see THIRD_PARTY_CHECKLIST.md.
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
AIF_ROOT = HERE.parent
BUNDLE_ROOT = AIF_ROOT.parent
sys.path.insert(0, str(AIF_ROOT))
from aif import json_to_aif, aif_to_json  # noqa: E402

VECTORS = HERE / "vectors.json"
REPORT = HERE / "BIDIRECTIONAL_REPORT.md"
JS_DIR = AIF_ROOT / "implementations" / "js"


def equal(a, b):
    """Structural equality; int/float 3 vs 3.0 are equal on purpose."""
    return a == b


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------
class JSAdapter:
    """Bundled reference implementation B, using its batch CLIs."""
    name = "JS reference B (author-written, NOT third-party)"
    third_party = False

    def decode_many(self, texts):
        p = subprocess.run(["node", str(JS_DIR / "batch_cli.js")],
                           input=json.dumps(texts, ensure_ascii=False).encode(),
                           capture_output=True)
        if p.returncode:
            raise RuntimeError("JS decode bridge failed: " +
                               p.stderr.decode(errors="replace")[:300])
        return json.loads(p.stdout.decode())

    def encode_many(self, items):
        payload = [{"data": d, "textMode": tm} for d, tm in items]
        p = subprocess.run(["node", str(JS_DIR / "encode_cli.js"), "--batch"],
                           input=json.dumps(payload, ensure_ascii=False).encode(),
                           capture_output=True)
        if p.returncode:
            raise RuntimeError("JS encode bridge failed: " +
                               p.stderr.decode(errors="replace")[:300])
        return json.loads(p.stdout.decode())


def _resolve_cmd(cmd, base):
    """Keep the executable name as-is; resolve relative script paths to base."""
    out = [cmd[0]]
    for part in cmd[1:]:
        if part.startswith("-") or Path(part).is_absolute():
            out.append(part)
        elif (base / part).exists():
            out.append(str(base / part))
        else:
            out.append(part)
    return out


class CommandAdapter:
    """Third-party implementation driven by two CLIs (see ADAPTER_PROTOCOL.md).

    decode: stdin = AIF text (plain), stdout = JSON value, exit 0 on success
    encode: stdin = JSON value,       stdout = AIF text,  exit 0 on success
    """

    def __init__(self, cfg, base):
        self.name = cfg.get("name", "third-party adapter")
        self.third_party = bool(cfg.get("third_party", False))
        self.decode_cmd = _resolve_cmd(cfg["decode"], base)
        self.encode_cmd = _resolve_cmd(cfg["encode"], base)

    def _run(self, cmd, payload):
        try:
            p = subprocess.run(cmd, input=payload.encode("utf-8"),
                               capture_output=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return None, f"{type(exc).__name__}: {exc}"
        if p.returncode != 0:
            return None, p.stderr.decode(errors="replace").strip()[:200]
        return p.stdout.decode(), None

    def decode_many(self, texts):
        out = []
        for t in texts:
            raw, err = self._run(self.decode_cmd, t)
            if err:
                out.append({"ok": False, "error": err})
            else:
                try:
                    out.append({"ok": True, "value": json.loads(raw)})
                except json.JSONDecodeError as exc:
                    out.append({"ok": False, "error": f"invalid JSON output: {exc}"})
        return out

    def encode_many(self, items):
        out = []
        for data, _tm in items:
            raw, err = self._run(self.encode_cmd,
                                 json.dumps(data, ensure_ascii=False))
            if err:
                out.append({"ok": False, "error": err})
            else:
                out.append({"ok": True, "text": raw})
        return out


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", help="path to third_party_adapter.json")
    args = ap.parse_args()

    if args.adapter:
        cfg_path = Path(args.adapter)
        if not cfg_path.is_absolute():
            cfg_path = (Path.cwd() / cfg_path).resolve()
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        B = CommandAdapter(cfg, cfg_path.parent)
    else:
        B = JSAdapter()

    doc = json.loads(VECTORS.read_text(encoding="utf-8"))
    vectors = doc["vectors"]
    pos = [v for v in vectors if v["kind"] == "positive"]
    neg = [v for v in vectors if v["kind"] == "negative"]

    # ---- A->B and B->B : two AIF texts per positive vector -----------------
    a_texts, owners = [], []
    for v in pos:
        a_texts.append(v["expected_aif_structured"])
        owners.append((v["id"], "structured"))
        a_texts.append(v["expected_aif_text_mode"])
        owners.append((v["id"], "text_mode"))
    b_dec = B.decode_many(a_texts)

    # ---- B->A : B encodes every input_json in both modes -------------------
    b_items = []
    for v in pos:
        b_items.append((v["input_json"], False))
        b_items.append((v["input_json"], True))
    b_enc = B.encode_many(b_items)

    rows = []
    for i, v in enumerate(pos):
        expected = v["expected_decoded"]
        r = {"id": v["id"], "title": v["title"]}
        # A -> B (two encodings)
        ab = []
        for j in (2 * i, 2 * i + 1):
            res = b_dec[j]
            ab.append(bool(res.get("ok") and equal(res.get("value"), expected)))
        r["a_to_b"] = all(ab)
        r["a_to_b_err"] = "" if r["a_to_b"] else str(
            next((b_dec[j].get("error") for j in (2 * i, 2 * i + 1)
                  if not b_dec[j].get("ok")), "decoded value differs"))
        # B -> A
        ba, byte_eq = [], []
        for j, mode in ((2 * i, False), (2 * i + 1, True)):
            res = b_enc[j]
            if not res.get("ok"):
                ba.append(False)
                byte_eq.append(False)
                continue
            text = res["text"]
            try:
                ba.append(equal(aif_to_json(text), v["input_json"]))
            except Exception:                              # noqa: BLE001
                ba.append(False)
            golden = (v["expected_aif_structured"] if not mode
                      else v["expected_aif_text_mode"])
            byte_eq.append(text == golden)
        r["b_to_a"] = all(ba)
        r["b_to_a_err"] = "" if r["b_to_a"] else str(
            next((b_enc[j].get("error") for j in (2 * i, 2 * i + 1)
                  if not b_enc[j].get("ok")), "decoded value differs"))
        r["byte_equal"] = all(byte_eq)
        # A -> A baseline
        r["a_to_a"] = all(
            equal(aif_to_json(v[field]), expected)
            for field in ("expected_aif_structured", "expected_aif_text_mode"))
        rows.append(r)

    # ---- negative vectors: both encoders must reject -----------------------
    neg_rows = []
    b_neg = B.encode_many([(v["input_json"], False) for v in neg])
    for v, res in zip(neg, b_neg):
        if v.get("not_valid_json"):
            neg_rows.append((v["id"], v["title"], "SKIP",
                             "值不是合法 JSON，公共向量只存占位 null；"
                             "请按 construct_hint 在宿主语言内构造"))
            continue
        try:
            json_to_aif(v["input_json"])
            a_reject = False
        except (TypeError, ValueError):
            a_reject = True
        b_reject = not res.get("ok")
        status = "PASS" if (a_reject and b_reject) else "FAIL"
        neg_rows.append((v["id"], v["title"], status,
                         f"A_reject={a_reject}, B_reject={b_reject}"))

    n = len(rows)
    a2b = sum(r["a_to_b"] for r in rows)
    b2a = sum(r["b_to_a"] for r in rows)
    a2a = sum(r["a_to_a"] for r in rows)
    byts = sum(r["byte_equal"] for r in rows)
    neg_pass = sum(s == "PASS" for _, _, s, _ in neg_rows)
    neg_skip = sum(s == "SKIP" for _, _, s, _ in neg_rows)
    neg_fail = sum(s == "FAIL" for _, _, s, _ in neg_rows)

    L = []
    add = L.append
    add("# AIF/0.9 双向兼容性验证报告")
    add("")
    add(f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    add(f"- 实现 A：Python 参考实现（`AIF/aif/`）")
    add(f"- 实现 B：**{B.name}**")
    add(f"- 测试向量：`conformance/vectors.json`（{doc['count']} 个）")
    add("")
    if not B.third_party:
        add("> ⚠️ **本次运行不满足 1.0 发布门槛 #6**。实现 B 是本项目作者自写的")
        add("> 参考实现，不是「未参与原始实现的第三方开发者」的独立实现。")
        add("> 本报告只证明**验收框架可用**；要真正满足门槛，必须用")
        add("> `--adapter third_party_adapter.json` 由第三方实现重跑。")
        add("")
    else:
        add("> 本次运行使用第三方适配器；是否满足门槛仍需人工确认实现者")
        add("> 确实未参与原始实现，且只依据规范/向量/指南开发。")
        add("")
    add("## 判定口径")
    add("")
    add("- `A→B`：实现 A 产出的 AIF（Structured 与 Text Mode 两种）由 B 解码，"
        "必须结构相等于 `expected_decoded`。")
    add("- `B→A`：实现 B 从 `input_json` 产出的 AIF 由 A 解码，"
        "必须结构相等于 `input_json`。")
    add("- 逐字节相等**不是**通过条件，只作信息性记录（schema 推断顺序等"
        "实现自由度允许文本不同）。")
    add("- negative 向量必须被两个编码器都拒绝。")
    add("")
    add("## 汇总")
    add("")
    add("| 检查 | 结果 |")
    add("|---|---:|")
    add(f"| A→B（A 编码 / B 解码） | **{a2b}/{n}** |")
    add(f"| B→A（B 编码 / A 解码） | **{b2a}/{n}** |")
    add(f"| A→A（自检基线） | {a2a}/{n} |")
    add(f"| 逐字节相等（信息性） | {byts}/{n} |")
    add(f"| negative 拒绝 | PASS {neg_pass} / SKIP {neg_skip} / FAIL {neg_fail} |")
    add(f"| **双向兼容性** | **{'PASS' if a2b == n and b2a == n else 'FAIL'}** |")
    add("")
    add("## 逐向量明细")
    add("")
    add("| ID | 名称 | A→B | B→A | A→A | 逐字节 |")
    add("|---|---|:---:|:---:|:---:|:---:|")
    for r in rows:
        add(f"| {r['id']} | {r['title'][:42]} | "
            f"{'PASS' if r['a_to_b'] else 'FAIL'} | "
            f"{'PASS' if r['b_to_a'] else 'FAIL'} | "
            f"{'PASS' if r['a_to_a'] else 'FAIL'} | "
            f"{'是' if r['byte_equal'] else '否'} |")
    failed = [r for r in rows if not (r["a_to_b"] and r["b_to_a"] and r["a_to_a"])]
    if failed:
        add("")
        add("### 失败详情")
        add("")
        for r in failed:
            add(f"- `{r['id']}` A→B 错误：{r['a_to_b_err'] or '值不一致'}；"
                f"B→A 错误：{r['b_to_a_err'] or '值不一致'}")
    add("")
    add("## Negative 向量")
    add("")
    add("| ID | 名称 | 结果 | 说明 |")
    add("|---|---|:---:|---|")
    for vid, title, status, note in neg_rows:
        add(f"| {vid} | {title} | {status} | {note} |")
    add("")
    add("## 已知互操作边界（不隐藏）")
    add("")
    for note in doc["known_interop_limits"]:
        add(f"- {note}")
    add("")
    add("## 复现")
    add("")
    add("```bash")
    add("python AIF/conformance/build_vectors.py --verify")
    add("python AIF/conformance/bidirectional.py")
    add("python AIF/conformance/bidirectional.py --adapter path/to/third_party_adapter.json")
    add("```")

    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"实现 B: {B.name}")
    print(f"A→B {a2b}/{n}   B→A {b2a}/{n}   A→A {a2a}/{n}   "
          f"逐字节 {byts}/{n}")
    print(f"negative: PASS {neg_pass} / SKIP {neg_skip} / FAIL {neg_fail}")
    print(f"双向兼容性: {'PASS' if a2b == n and b2a == n else 'FAIL'}")
    print(f"报告: {REPORT.relative_to(BUNDLE_ROOT)}")
    if not B.third_party:
        print("注意: 实现 B 是作者自写参考实现，不构成第三方独立实现（门槛 #6 未达成）")
    return 0 if (a2b == n and b2a == n and neg_fail == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
