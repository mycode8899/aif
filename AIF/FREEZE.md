# AIF 冻结声明（第三方验收期）

**生效时间**：2026-11-08
**生效范围**：AIF/0.9 核心、AIF/1.0-alpha Array Lab、公开测试向量、规范与指南、发布门槛、双向验收框架
**决策**：从本声明起，**不再增加任何自有实现**，全部精力转向寻找并验收一名真正独立的第三方实现者。
**当前结论不变**：`AIF/1.0 Stable` **不得发布**；对外只能称 `AIF/0.9 完整工程`。

---

## 1. 优先原则：规范约束实现，不是实现定义规范

> **AIF 的规范不能为了让当前 Python 和 JavaScript 两个实现通过测试而被反向定义。**
> 由冻结的规范和公开测试向量约束实现；实现的分歧是实现的缺陷或规范的歧义，
> **不是**修改规范、向量或判定条件去迁就实现的理由。

由此派生四条硬规则：

1. **裁判唯一**：`specification/AIF-0.9.md`（normative）与 `conformance/vectors.json`（42 向量）是唯一验收依据。两者冲突时以规范为准，并把冲突登记为规范歧义。
2. **实现服从**：Python / JavaScript 两套现有实现均为**作者自写的参考实现**，不具备定义规范的资格。第三方实现同样不定义规范。
3. **失败留痕**：任一向量失败、任一负例被接受、任一负 reduction 数据，一律原样记录。禁止删除失败案例、禁止放宽相等判定、禁止重生成向量来"洗掉"失败。
4. **修订公开**：规范或向量确需变更，必须走第 5 节流程：先登记 → 公开修订 → 版本递增 → 全部实现同步 → 全量重跑 → 重新冻结并更新哈希。**不允许私下改实现或改测试来通过验收。**

### 一处需要明说的历史局限

本规范与 Python 实现是**同期编写**的，并非先有独立规范、后有实现。`specification/AIF-0.9.md` 自身状态行仍写「**冻结候选**」。本次冻结只保证「**从现在起**不再反向定义」，**不能追溯消除作者默契**——这恰恰是必须由真人第三方独立实现来验证的原因，不能靠再写一个自己的版本或包装文档来替代。

> 本声明是**治理文件，不具规范性效力，不修改规范原文一字**。
> 规范 §13 中「任何一次分歧都被视为规范 bug，必须同时修规范与双方实现」是冻结前的内部开发约定；
> 冻结后以本声明第 5 节的公开修订流程为准。若第三方认为二者存在冲突，
> 请登记为规范歧义（见 `third_party/SPEC_ISSUES.md`），在公开修订之前**以规范原文为准**。

---

## 2. 冻结对象

### Tier A — 字节级冻结（24 个文件，哈希见 `FROZEN.sha256`）

| 你指定冻结的内容 | 具体文件 | 数量 |
|---|---|:--:|
| AIF 0.9 核心代码 | `aif/{__init__,encoder,decoder}.py`；`implementations/js/{decoder,encoder,cli,batch_cli,encode_cli}.js`、`implementations/js/README.md` | 9 |
| AIF 1.0-alpha Array Lab | `array_lab/{lab_spec.py,lab_codecs.py,run_lab.py,LAB_REPORT.md,README.md,fitted_thresholds.json}` | 6 |
| 42 个公开测试向量 | `conformance/vectors.json`、`conformance/build_vectors.py`（生成器一并冻结，否则可重新生成不同向量） | 2 |
| IMPLEMENTER_GUIDE.md | `conformance/IMPLEMENTER_GUIDE.md` | 1 |
| 正式语法规范 | `specification/AIF-0.9.md` | 1 |
| RELEASE_GATES.md | `RELEASE_GATES.md` | 1 |
| 双向验收框架 | `conformance/bidirectional.py`、`ADAPTER_PROTOCOL.md`、`THIRD_PARTY_CHECKLIST.md`、`third_party_adapter.example.json` | 4 |

**Tier A 内任何文件的任何字节变化都视为解冻**，须先走第 5 节流程。

### Tier B — 只读（本次验收不得为通过而改动）

`tests/`、`benchmarks/`、`examples/`、`research/`、`provenance/`、`README.md`、`tests/FUZZ_REPORT.md`、`array_lab/fitted_thresholds.json` 的生成输入。
若因公开修订规范而必须同步修改测试，须在修订记录中逐文件列出并留痕。

### Tier C — 允许新增（本轮唯一允许的写入）

`third_party/`（治理、公告、歧义登记簿、验收记录模板、公开交付包）、`FREEZE.md`、`FROZEN.sha256`。
**明确禁止**在 Tier C 中新增任何 AIF 编码器 / 解码器 / 适配器实现代码——第三套实现不存在，也不会由本项目补上。

### 一个刻意不冻结的输出文件

`conformance/BIDIRECTIONAL_REPORT.md` 是**运行结果**，`bidirectional.py` 每次执行都会重写它。
真正的第三方验收将覆盖它，因此：
- 现有内容已归档为 `third_party/archive/BIDIRECTIONAL_REPORT.internal-baseline.md`；
- 归档件证明的是「作者自写参考实现 B 的内部验证」，**不是**第三方结果，两者不得混淆。

---

## 3. 冻结时如实保留的未解决问题

| 问题 | 状态 | 冻结期处置 |
|---|---|---|
| 0.9 在 `@record` 边界被截断时**静默少返回一条记录**（无记录总数声明，无法检出） | 已发现，**未修复** | 冻结核心代码意味着**验收期内不修**。已预登记为 `SI-001`，要求第三方独立判断并记录依据，不得参考任何现有实现 |
| 标量数组 token 效率（V8 `07 Array` **−37.99%**） | 未解决 | 保持负数原样，不删、不美化、不改写结论 |
| 0.1–0.8 原始源码、V3–V6 benchmark | 部分恢复，10 组明确 Missing | 不用重建代码冒充原版 |
| 规范「冻结候选」措辞 | 未改 | 验收期冻结 ≠ 1.0 Stable；第三方通过并公开修订后才重新评估 |
| 第三方独立实现 | **0 个** | 唯一剩余主目标 |

---

## 4. 校验冻结是否被破坏

在 `AIF/` 目录执行：

```bash
sha256sum -c FROZEN.sha256
python AIF/conformance/build_vectors.py --verify
python AIF/tests/verify_all.py
```

- 第 1 条必须 24/24 `OK`；任何 `FAILED` 说明 Tier A 被改动。
- 第 2、3 条是既有验证（`42 vectors VERIFIED`、`9/9 CHECKS PASSED`），**不得**用它们替代第 1 条。
- 交付给第三方的包另有 `third_party/bundle/SHA256SUMS`，用于核对其拿到的材料与冻结原件逐字节一致。

---

## 5. 解冻 / 公开修订流程（唯一合法路径）

1. **登记**：任何人（尤其第三方实现者）在 `third_party/SPEC_ISSUES.md` 记录问题：条款号、输入、两种合理理解、期望的确定性规则。
2. **不私下处理**：在公开记录之前，验收方不得改向量、不得放宽判定、不得提示实现者「按我们实现的行为写」。
3. **公开修订**：修订 `specification/AIF-0.9.md` 与 `conformance/vectors.json`，附变更说明、版本号递增、旧向量保留为历史记录（**不删除**）。
4. **同步全部实现**：Python、JavaScript、以及第三方实现各自按新规范调整；这一步是**实现服从规范**，不是规范迁就实现。
5. **全量重跑**：`verify_all.py`、双向验收、benchmark 全部重跑，负结果照留。
6. **重新冻结**：更新 `FROZEN.sha256`、公开交付包哈希、`RELEASE_GATES.md`，并注明本次修订由哪个 ISSUE 触发。

未走完 1–6，`RELEASE_GATES.md` 门槛 #5「正式语法规范冻结」维持 `⚠️ 部分`，门槛 #6 维持 `❌ 未达成`。

---

## 6. 冻结不解除的结论

- 门槛 #6「第三方独立实现通过一致性测试」**仍未达成**。
- 作者自写的 JS 实现是**参考实现 B**，不计入第三方；本会话不会再写第三套实现。
- 双向框架 `A→B 33/33`、`B→A 33/33` 只证明**内部框架联通**，不证明规范可被独立实现。
- **`AIF/1.0 Stable` 不得发布。**

材料索引见 `third_party/README.md`；招募公告见 `third_party/CALL_FOR_IMPLEMENTERS.md`；
验收记录模板见 `third_party/ACCEPTANCE_RECORD.md`（当前为空白，无任何第三方数据）。
