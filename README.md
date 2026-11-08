# AIF — AI-Native Format

面向 AI Agent / LLM 之间**结构化数据交换**的面向行文本格式。它把 schema 与数据分离，字段名与类型只声明一次，从而在大量重复结构的数据上减少 token。

> **AIF 不是「更短的 JSON」，也不承诺所有数据都比 JSON 省。**
> 长自然语言文本、标量数组等场景可能更耗 token。这是设计事实，不是待修的 bug。

**当前状态：`AIF/0.9 完整工程` —— 不是 `AIF/1.0 Stable`，不得如此标记。**
`AIF/RELEASE_GATES.md` 登记的 7 条发布门槛为 **4 达成 / 2 部分 / 1 未达成**；未达成的是门槛 #6「第三方独立实现通过一致性测试」。两个现有实现（Python、JavaScript）都是**同一作者自写**，不构成第三方验证。

---

## 目录导航

| 路径 | 内容 |
|---|---|
| [`AIF/`](AIF/) | 主工程（本文件是仓库顶层导航；完整技术文档见 [`AIF/README.md`](AIF/README.md)） |
| [`AIF/specification/AIF-0.9.md`](AIF/specification/AIF-0.9.md) | **正式语法规范（normative）** |
| [`AIF/conformance/`](AIF/conformance/) | 42 个公开测试向量、实现者指南、双向验收框架 |
| [`AIF/third_party/`](AIF/third_party/) | **当前主目标**：第三方验收工作区、招募公告、公开交付包 |
| [`AIF/FREEZE.md`](AIF/FREEZE.md) | 冻结声明与公开修订流程 |
| [`AIF/array_lab/`](AIF/array_lab/) | `AIF/1.0-alpha` Array Optimization Lab（实验性，**不是 0.9**） |
| [`AIF/benchmarks/RESULTS.md`](AIF/benchmarks/RESULTS.md) | V8 benchmark 完整结果（含全部负 reduction） |
| [`AIF/provenance/FILE_MANIFEST.md`](AIF/provenance/FILE_MANIFEST.md) | 历史源码溯源清单 |

**仓库根目录下的 10 个历史文件**（`aif_decoder_v09*.py`、`aif_encoder_v09.py`、`test_*.py`、`BENCHMARK.md`、`README_RECOVERY.md`、`RECOVERY_STATUS.md`）是**恢复包原件，按原样保留、未作修改**。
其中哪些是 `Original`、哪些是 `Reconstructed`、哪些明确 `Missing`，见 [`RECOVERY_STATUS.md`](RECOVERY_STATUS.md) 与 [`AIF/provenance/FILE_MANIFEST.md`](AIF/provenance/FILE_MANIFEST.md)。
**重建代码不冒充历史原件**；0.1–0.8 全部源码、V3–V6 benchmark、0.9 原始 encoder 共 10 组明确标记为无法恢复。

---

## 快速开始

```bash
cd AIF
python -c "from aif import json_to_aif, aif_to_json; t = json_to_aif([{'name':'Ada','age':36}]); print(t); print(aif_to_json(t))"
```

Python 3.13；Node ≥ 18（JavaScript 参考实现）；benchmark 需 `tiktoken 0.14.0` + `cl100k_base`。

一键复现全部验证：

```bash
cd AIF
python tests/verify_all.py                          # 9/9 CHECKS PASSED
python tests/run_all.py                             # 104/104
python tests/cross_validate.py                      # 78/78
python tests/fuzz_roundtrip.py                      # 639/639
python conformance/build_vectors.py --verify        # 42 vectors VERIFIED
python conformance/bidirectional.py                 # A→B 33/33、B→A 33/33
python benchmarks/benchmark_v8.py                   # 17/17 round-trip
sha256sum -c FROZEN.sha256                          # 24/24 OK（冻结完整性）
```

> 上述 `33/33` 是**作者自写参考实现 B 的内部双向验证**，**不是**第三方验收结果。

---

## 当前主目标：寻找真正独立的第三方实现者

本项目**不再增加自有实现**。要验证的不是性能，而是：

> 一位**完全没有参与过本项目**的开发者，能否只依据规范与 42 个公开测试向量，从零写出一个通过一致性测试的实现？

- 招募公告：[`AIF/third_party/CALL_FOR_IMPLEMENTERS.md`](AIF/third_party/CALL_FOR_IMPLEMENTERS.md)
- 公开交付包（**不含任何 Python / JavaScript 实现源码**）：[`AIF/third_party/bundle/`](AIF/third_party/bundle/)，另附可下载的 `aif-0.9-third-party-bundle.zip`
- 规范歧义登记簿：[`AIF/third_party/SPEC_ISSUES.md`](AIF/third_party/SPEC_ISSUES.md)
- 验收记录模板（**当前空白、未执行**）：[`AIF/third_party/ACCEPTANCE_RECORD.md`](AIF/third_party/ACCEPTANCE_RECORD.md)
- 提交方式：在本仓库开 Issue / Discussion

**交付给第三方的材料只有**：规范、测试向量、语言无关实现者指南、CLI 接入协议、适配器模板、验收清单。
**刻意不提供**任何现有实现源码、内部研究报告，也不给「某处该怎么解析」的口头提示。
若某行为只能靠阅读参考实现才能确定，请记录为**规范歧义**，不要猜、也不要照抄实现。

验收由维护方运行：

```bash
python AIF/conformance/build_vectors.py --verify
python AIF/conformance/bidirectional.py --adapter <第三方适配器配置>.json
```

---

## 冻结与公开修订

`AIF/FREEZE.md`（2026-11-08）把 **24 个文件字节级冻结**，清单见 `AIF/FROZEN.sha256`：
0.9 核心代码、Array Lab、42 向量及其生成器、正式规范、实现者指南、发布门槛表、双向验收框架。

**核心原则**：规范与公开测试向量约束实现，**实现不得反向定义规范**。
不得为了让某个实现通过测试而修改向量、删除失败案例、放宽相等判定，或私下按实现结果改规范。
规范或向量确需变更，必须走 `FREEZE.md` 第 5 节的公开流程：登记 → 公开修订 → 版本递增 → 全部实现同步 → 全量重跑 → 重新冻结。

> **关于本仓库的发布与冻结状态表**：`AIF/RELEASE_GATES.md` 是 2026-11-08 的**冻结快照**，
> 其中门槛 #7「项目仍在本机目录，尚未发布到任何公开仓库」描述的是**冻结时刻**的状态。
> 本仓库公开后该条已与事实不符，但按冻结规则**未修改该文件**；
> 其更新须走公开修订流程。**本 README 是「当前是否已公开」的事实来源。**
> 发布本身**不达成门槛 #6**，也不改变「1.0 Stable 不得发布」的结论。

---

## 如实保留的负面结果与已知缺陷

| 项 | 事实 |
|---|---|
| 标量数组 token | V8 `07 Array` **−37.99%**（比 JSON 更耗），未解决 |
| 长文本 | 默认 Structured Mode **−109.60%**；Text Mode 降到 +4.10%，但不能让所有数据变正 |
| Hybrid 编码 | 比「总是 Row」只省 1,001 tokens（0.050%），不值得立项 —— 负面结论原样保留 |
| 0.9 静默截断 | 文本截断到 `@record` 边界会**静默少返回一条记录**（无记录总数声明）；已发现，验收期内按冻结决定**不修**，登记为 `SI-001` |
| 历史源码 | 10 组明确 Missing，不用重建代码冒充原版 |
| 第三方独立实现 | **0 个**，需真人开发者 |

规范本身也有必须明说的局限：`AIF-0.9.md` 与 Python 实现**同期编写**，状态行仍为「冻结候选」，并非先有独立规范后有实现。冻结只能保证「从现在起」不反向定义，不能追溯消除作者默契 —— 这正是需要第三方独立实现来验证的原因。

---

## 环境与复现

Python 3.13 / Node 22 / `tiktoken 0.14.0` / 主口径 `cl100k_base`（另测 `o200k_base`、`p50k_base`、`r50k_base`）。
所有 benchmark 数据由固定 seed 脚本生成，无手工数据；负 reduction 一律保留、不美化。

## License

MIT — 见 [LICENSE](LICENSE)。第三方实现者可自由依据规范与测试向量进行独立实现。
