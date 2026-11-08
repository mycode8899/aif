"""
Build the AIF provenance manifest from the bytes actually on disk.

Classification is a HUMAN judgement, recorded in the tables below with an
explicit evidence source. This script only measures (size / mtime / sha256)
and writes the report; it never decides what "original" means.

Run:
    python AIF/provenance/build_manifest.py
Writes:
    AIF/provenance/FILE_MANIFEST.md
"""

import hashlib
import platform
from datetime import datetime
from pathlib import Path

BUNDLE = Path(__file__).resolve().parents[2]
AIF_DIR = BUNDLE / "AIF"
OUT = Path(__file__).with_name("FILE_MANIFEST.md")

ORIGINAL_DOC = "RECOVERY_STATUS.md + README_RECOVERY.md（恢复包自带声明）"

# (filename, category, evidence)
CLASSIFICATION = [
    ("aif_decoder_v09_original.py", "Original",
     f"{ORIGINAL_DOC}：'Retrieved original files'，V7 时期的旧 decoder 快照，已知游标错位"),
    ("test_token_benchmark_v7.py", "Original",
     f"{ORIGINAL_DOC}：'Retrieved original files'，V7 benchmark 脚本原件"),
    ("BENCHMARK.md", "Original",
     f"{ORIGINAL_DOC}：'Retrieved original files'，AIF 0.1–0.6 的设计与结果**叙述记录**"),
    ("README_RECOVERY.md", "Original (metadata)",
     "恢复包自带说明文档；是恢复过程的元数据，不是 AIF 实现源码"),
    ("RECOVERY_STATUS.md", "Original (metadata)",
     "恢复包自带说明文档；Original/Reconstructed/Missing 分类的一手证据"),
    ("aif_encoder_v09.py", "Reconstructed",
     f"{ORIGINAL_DOC}：明确列为重建；原件未找回"),
    ("aif_decoder_v09.py", "Reconstructed",
     f"{ORIGINAL_DOC}：明确列为重建；与 _reconstructed.py 字节相同"),
    ("aif_decoder_v09_reconstructed.py", "Reconstructed",
     f"{ORIGINAL_DOC}：明确列为重建"),
    ("test_stress_v09.py", "Reconstructed",
     f"{ORIGINAL_DOC}：明确列为重建"),
    ("test_token_benchmark_v7_rerun.py", "New (this session)",
     "2026-11-08 本会话新建；只测 0.9 的 V7 重跑脚本，不是 V7 原件，也不修改原件"),
]

# Files explicitly declared missing by RECOVERY_STATUS.md.
MISSING = [
    ("aif_encoder_v07.py / aif_decoder_v07.py", "AIF 0.7", "叙述：BENCHMARK.md 只覆盖到 0.6，0.7 无实现存档"),
    ("aif_encoder_v08.py / aif_decoder_v08.py", "AIF 0.8", "叙述：项目背景含 0.8 示例与结果，但源码未找回"),
    ("aif_encoder_v08_compact.py / aif_decoder_v08_compact.py", "AIF 0.8 Compact", "叙述：项目背景含 Compact 结果，但源码未找回"),
    ("aif_encoder_v09.py（原始版本）", "AIF 0.9", "恢复包内同名文件是**重建版**；原件未找回"),
    ("test_token_benchmark_v3.py", "Benchmark V3", "叙述：项目背景含 100/1000 records 结论，脚本未找回"),
    ("test_token_benchmark_v4.py", "Benchmark V4", "叙述：项目背景含 flat/nested/array 结论，脚本未找回"),
    ("test_token_benchmark_v5.py", "Benchmark V5", "叙述：项目背景含 6 类 Agent 场景结论，脚本未找回"),
    ("test_token_benchmark_v6.py", "Benchmark V6", "叙述：项目背景含 array-of-objects 规模扫描结论，脚本未找回"),
    ("AIF 0.1–0.6 的 encoder / decoder 源码", "AIF 0.1–0.6", "BENCHMARK.md 只有结果记录与设计说明，无源码"),
    ("早期 round-trip / edge-case 测试、历史 README", "测试与文档", "RECOVERY_STATUS.md 明确列为未找回"),
]


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    lines = []
    add = lines.append
    add("# AIF 历史源码溯源清单（Provenance Manifest）")
    add("")
    add(f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    add(f"- 环境：Python {platform.python_version()}，{platform.system()}")
    add(f"- 扫描根目录：`{BUNDLE}`")
    add(f"- 生成脚本：`AIF/provenance/build_manifest.py`（哈希与大小均从磁盘实测）")
    add("")
    add("> **不可混淆声明**：本清单中 `Reconstructed` 的文件是依据当年保留的设计、示例")
    add("> 与测试结果**重新实现**的，不是历史原件的逐字副本。`New` 是本会话产物。")
    add("> 二者都**不得**被用来声称「AIF 0.1–0.8 的历史代码 / V3–V6 实验已完整恢复」。")
    add("> 历史实验目前只有 `BENCHMARK.md` 与项目背景中的**叙述性记录**，")
    add("> 叙述记录不是可执行源码，也不等于可复现实验。")
    add("")
    add("## 类别定义")
    add("")
    add("| 类别 | 含义 |")
    add("|---|---|")
    add("| `Original` | 从历史文件/对话中实际找回，内容保持原样 |")
    add("| `Original (metadata)` | 恢复包自带说明，属一手证据，但不是 AIF 实现 |")
    add("| `Reconstructed` | 原件未找回，依设计/示例/测试重建，**非逐字副本** |")
    add("| `New (this session)` | 2026-11-08 本会话新建，与历史无关 |")
    add("| `Missing` | 磁盘上不存在，且无任何可核验的源码副本 |")
    add("")
    add("分类依据是一手文档 `RECOVERY_STATUS.md` / `README_RECOVERY.md` 的明确声明；")
    add("本脚本不自行判定来源，只负责实测哈希、大小、时间戳并输出表格。")
    add("")

    add("## 表 1：恢复包根目录逐文件登记")
    add("")
    add("| 文件 | 类别 | 字节 | SHA256 (前 16) | 分类证据 |")
    add("|---|---|---:|---|---|")
    found = set()
    for name, cat, evidence in CLASSIFICATION:
        p = BUNDLE / name
        if not p.exists():
            add(f"| `{name}` | {cat} | — | **NOT FOUND** | {evidence} |")
            continue
        found.add(name)
        st = p.stat()
        add(f"| `{name}` | {cat} | {st.st_size:,} | `{sha256(p)[:16]}…` | {evidence} |")
    add("")
    extra = sorted(p.name for p in BUNDLE.iterdir()
                   if p.is_file() and p.name not in found)
    if extra:
        add("**未在分类表中的根目录文件（需人工判定）**： " +
            "、".join(f"`{n}`" for n in extra))
    else:
        add("根目录所有文件均已登记，无未分类文件。")
    add("")

    # Byte-identity check that matters for the "two decoders" claim.
    a, b = BUNDLE / "aif_decoder_v09.py", BUNDLE / "aif_decoder_v09_reconstructed.py"
    if a.exists() and b.exists():
        add(f"- 字节一致性核验：`aif_decoder_v09.py` 与 `aif_decoder_v09_reconstructed.py` "
            f"**{'完全相同' if sha256(a) == sha256(b) else '不同'}**"
            f"（SHA256 `{sha256(a)[:16]}…`）。两者是同一份重建代码的两个文件名，")
        add("  不构成两个独立版本，更不能算作「找回的原件 + 重建版」各一份。")
        add("")

    add("## 表 2：明确缺失（Missing）")
    add("")
    add("| 文件 / 文件组 | 所属版本 | 现存证据的性质 |")
    add("|---|---|---|")
    for name, ver, note in MISSING:
        add(f"| `{name}` | {ver} | {note} |")
    add("")
    add("**结论**：AIF 0.1–0.8 的全部 encoder/decoder 源码、V3–V6 benchmark 脚本")
    add("**均为 Missing**。项目背景和 `BENCHMARK.md` 中的数字是历史叙述，")
    add("可作为设计线索，但不能当作已恢复的、可复现的历史实验。")
    add("")
    add("## 表 3：本会话新建交付（New，不属于历史恢复）")
    add("")
    add("`AIF/` 目录下的全部内容是 2026-11-08 本会话新建的工程交付，")
    add("与 0.1–0.8 历史源码恢复无关：")
    add("")
    add("| 子目录 | 文件数 | 性质 |")
    add("|---|---:|---|")
    labels = {
        "aif": "AIF/0.9 定稿 encoder/decoder（新写，非 0.9 原件）",
        "specification": "AIF/0.9 正式规范",
        "tests": "测试、fuzz、双实现一致性、一键验证",
        "benchmarks": "V8 benchmark 与结果",
        "examples": "示例与测试向量素材",
        "implementations": "参考实现（作者自写，非第三方）",
        "research": "第一/第二轮 Token Efficiency 研究",
        "array_lab": "本轮 Array Optimization Lab（实验性）",
        "conformance": "本轮 1.0 一致性验收包",
        "provenance": "本清单与生成脚本",
    }
    total = 0
    if AIF_DIR.exists():
        for sub in sorted(p for p in AIF_DIR.iterdir() if p.is_dir()):
            n = sum(1 for p in sub.rglob("*")
                    if p.is_file() and "__pycache__" not in p.parts)
            total += n
            add(f"| `{sub.name}/` | {n} | {labels.get(sub.name, '—')} |")
        root_files = sum(1 for p in AIF_DIR.iterdir() if p.is_file())
        total += root_files
        add(f"| `AIF/README.md` 等根目录文件 | {root_files} | 项目说明 |")
        add(f"| **合计** | **{total}** | 全部为 New |")
    add("")
    add("## 复现与核对")
    add("")
    add("```bash")
    add("python AIF/provenance/build_manifest.py   # 重新实测并生成本清单")
    add("sha256sum aif_decoder_v09_original.py     # 核对任一 Original 文件")
    add("```")
    add("")
    add("若日后找回任何 Missing 文件，应先核验其 SHA 不在本清单的 `Reconstructed` 集合中，")
    add("再以新类别 `Original (recovered later)` 登记，并保留发现日期与来源，")
    add("避免与已有重建版混淆。")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已生成 {OUT.relative_to(BUNDLE)}")
    print(f"根目录登记 {len(found)} 个文件；Missing {len(MISSING)} 组；"
          f"AIF/ 交付 {total} 个文件")


if __name__ == "__main__":
    main()
