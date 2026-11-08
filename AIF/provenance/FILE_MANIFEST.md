# AIF 历史源码溯源清单（Provenance Manifest）

- 生成时间：2026-11-08 13:07:29
- 环境：Python 3.13.14，Windows
- 扫描根目录：`F:\共享文件\AIF_Project_Recovery\AIF_Project_Recovery`
- 生成脚本：`AIF/provenance/build_manifest.py`（哈希与大小均从磁盘实测）

> **不可混淆声明**：本清单中 `Reconstructed` 的文件是依据当年保留的设计、示例
> 与测试结果**重新实现**的，不是历史原件的逐字副本。`New` 是本会话产物。
> 二者都**不得**被用来声称「AIF 0.1–0.8 的历史代码 / V3–V6 实验已完整恢复」。
> 历史实验目前只有 `BENCHMARK.md` 与项目背景中的**叙述性记录**，
> 叙述记录不是可执行源码，也不等于可复现实验。

## 类别定义

| 类别 | 含义 |
|---|---|
| `Original` | 从历史文件/对话中实际找回，内容保持原样 |
| `Original (metadata)` | 恢复包自带说明，属一手证据，但不是 AIF 实现 |
| `Reconstructed` | 原件未找回，依设计/示例/测试重建，**非逐字副本** |
| `New (this session)` | 2026-11-08 本会话新建，与历史无关 |
| `Missing` | 磁盘上不存在，且无任何可核验的源码副本 |

分类依据是一手文档 `RECOVERY_STATUS.md` / `README_RECOVERY.md` 的明确声明；
本脚本不自行判定来源，只负责实测哈希、大小、时间戳并输出表格。

## 表 1：恢复包根目录逐文件登记

| 文件 | 类别 | 字节 | SHA256 (前 16) | 分类证据 |
|---|---|---:|---|---|
| `aif_decoder_v09_original.py` | Original | 11,706 | `997111ef62844f6c…` | RECOVERY_STATUS.md + README_RECOVERY.md（恢复包自带声明）：'Retrieved original files'，V7 时期的旧 decoder 快照，已知游标错位 |
| `test_token_benchmark_v7.py` | Original | 13,999 | `0569631f91ce9618…` | RECOVERY_STATUS.md + README_RECOVERY.md（恢复包自带声明）：'Retrieved original files'，V7 benchmark 脚本原件 |
| `BENCHMARK.md` | Original | 13,425 | `22571a2cd0e511b3…` | RECOVERY_STATUS.md + README_RECOVERY.md（恢复包自带声明）：'Retrieved original files'，AIF 0.1–0.6 的设计与结果**叙述记录** |
| `README_RECOVERY.md` | Original (metadata) | 2,901 | `e44e4e7d7eae4e2f…` | 恢复包自带说明文档；是恢复过程的元数据，不是 AIF 实现源码 |
| `RECOVERY_STATUS.md` | Original (metadata) | 838 | `516f61b87f6ad23e…` | 恢复包自带说明文档；Original/Reconstructed/Missing 分类的一手证据 |
| `aif_encoder_v09.py` | Reconstructed | 5,787 | `8589abd88d73a1e5…` | RECOVERY_STATUS.md + README_RECOVERY.md（恢复包自带声明）：明确列为重建；原件未找回 |
| `aif_decoder_v09.py` | Reconstructed | 4,014 | `7a21da4349b2e4c8…` | RECOVERY_STATUS.md + README_RECOVERY.md（恢复包自带声明）：明确列为重建；与 _reconstructed.py 字节相同 |
| `aif_decoder_v09_reconstructed.py` | Reconstructed | 4,014 | `7a21da4349b2e4c8…` | RECOVERY_STATUS.md + README_RECOVERY.md（恢复包自带声明）：明确列为重建 |
| `test_stress_v09.py` | Reconstructed | 1,598 | `51cb0374cb068429…` | RECOVERY_STATUS.md + README_RECOVERY.md（恢复包自带声明）：明确列为重建 |
| `test_token_benchmark_v7_rerun.py` | New (this session) | 5,617 | `20abac07a0da6243…` | 2026-11-08 本会话新建；只测 0.9 的 V7 重跑脚本，不是 V7 原件，也不修改原件 |

根目录所有文件均已登记，无未分类文件。

- 字节一致性核验：`aif_decoder_v09.py` 与 `aif_decoder_v09_reconstructed.py` **完全相同**（SHA256 `7a21da4349b2e4c8…`）。两者是同一份重建代码的两个文件名，
  不构成两个独立版本，更不能算作「找回的原件 + 重建版」各一份。

## 表 2：明确缺失（Missing）

| 文件 / 文件组 | 所属版本 | 现存证据的性质 |
|---|---|---|
| `aif_encoder_v07.py / aif_decoder_v07.py` | AIF 0.7 | 叙述：BENCHMARK.md 只覆盖到 0.6，0.7 无实现存档 |
| `aif_encoder_v08.py / aif_decoder_v08.py` | AIF 0.8 | 叙述：项目背景含 0.8 示例与结果，但源码未找回 |
| `aif_encoder_v08_compact.py / aif_decoder_v08_compact.py` | AIF 0.8 Compact | 叙述：项目背景含 Compact 结果，但源码未找回 |
| `aif_encoder_v09.py（原始版本）` | AIF 0.9 | 恢复包内同名文件是**重建版**；原件未找回 |
| `test_token_benchmark_v3.py` | Benchmark V3 | 叙述：项目背景含 100/1000 records 结论，脚本未找回 |
| `test_token_benchmark_v4.py` | Benchmark V4 | 叙述：项目背景含 flat/nested/array 结论，脚本未找回 |
| `test_token_benchmark_v5.py` | Benchmark V5 | 叙述：项目背景含 6 类 Agent 场景结论，脚本未找回 |
| `test_token_benchmark_v6.py` | Benchmark V6 | 叙述：项目背景含 array-of-objects 规模扫描结论，脚本未找回 |
| `AIF 0.1–0.6 的 encoder / decoder 源码` | AIF 0.1–0.6 | BENCHMARK.md 只有结果记录与设计说明，无源码 |
| `早期 round-trip / edge-case 测试、历史 README` | 测试与文档 | RECOVERY_STATUS.md 明确列为未找回 |

**结论**：AIF 0.1–0.8 的全部 encoder/decoder 源码、V3–V6 benchmark 脚本
**均为 Missing**。项目背景和 `BENCHMARK.md` 中的数字是历史叙述，
可作为设计线索，但不能当作已恢复的、可复现的历史实验。

## 表 3：本会话新建交付（New，不属于历史恢复）

`AIF/` 目录下的全部内容是 2026-11-08 本会话新建的工程交付，
与 0.1–0.8 历史源码恢复无关：

| 子目录 | 文件数 | 性质 |
|---|---:|---|
| `aif/` | 3 | AIF/0.9 定稿 encoder/decoder（新写，非 0.9 原件） |
| `array_lab/` | 6 | 本轮 Array Optimization Lab（实验性） |
| `benchmarks/` | 2 | V8 benchmark 与结果 |
| `conformance/` | 8 | 本轮 1.0 一致性验收包 |
| `examples/` | 11 | 示例与测试向量素材 |
| `implementations/` | 6 | 参考实现（作者自写，非第三方） |
| `provenance/` | 2 | 本清单与生成脚本 |
| `research/` | 6 | 第一/第二轮 Token Efficiency 研究 |
| `specification/` | 1 | AIF/0.9 正式规范 |
| `tests/` | 10 | 测试、fuzz、双实现一致性、一键验证 |
| `AIF/README.md` 等根目录文件 | 2 | 项目说明 |
| **合计** | **57** | 全部为 New |

## 复现与核对

```bash
python AIF/provenance/build_manifest.py   # 重新实测并生成本清单
sha256sum aif_decoder_v09_original.py     # 核对任一 Original 文件
```

若日后找回任何 Missing 文件，应先核验其 SHA 不在本清单的 `Reconstructed` 集合中，
再以新类别 `Original (recovered later)` 登记，并保留发现日期与来源，
避免与已有重建版混淆。
