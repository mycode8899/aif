# AIF/0.9 第三方公开交付包 — 清单

**包版本**：`aif-0.9-third-party-bundle` / 2026-11-08
**冻结依据**：`AIF/FREEZE.md`（24 个 Tier A 文件字节级冻结，哈希见 `AIF/FROZEN.sha256`）
**用途**：只交给未参与本项目的第三方实现者，作为**唯一实现依据**。

> 本包**不含任何实现源码**。规范与 42 个公开测试向量是唯一裁判，
> 实现不得反向定义规范（见 `AIF/FREEZE.md` 第 1 节）。

---

## 1. 包内文件

| 文件 | 来源（冻结原件） | SHA256 | 说明 |
|---|---|---|---|
| `AIF-0.9.md` | `specification/AIF-0.9.md` | `78f15e08311e159c7adf612b16aa24ee74aeaac2e2dfdc2878da15a68f546e12` | 正式规范（normative） |
| `IMPLEMENTER_GUIDE.md` | `conformance/IMPLEMENTER_GUIDE.md` | `f4a6074bedbba7bdc0f9afcc8d70ab4438badee0d81eaf56612623d29b8169e1` | 语言无关实现者指南 |
| `vectors.json` | `conformance/vectors.json` | `75cdf1ca6b71a34ceb2218f5d0a16a4a74f637860f90f37b0dba0cf3b0a3b7ed` | 42 向量（33 正向 + 9 负向） |
| `ADAPTER_PROTOCOL.md` | `conformance/ADAPTER_PROTOCOL.md` | `4c96b5c9311f7da1ce24d312edb6a46c3c391a23e6612e2d268eede07b1df7f4` | 验收 CLI I/O 协议（无 AIF 语义） |
| `third_party_adapter.example.json` | `conformance/third_party_adapter.example.json` | `e62af975c4077a8dd60fd8197a01f5feb0136e7e5912704700a3497aaaf2a00a` | 适配器配置模板 |
| `THIRD_PARTY_CHECKLIST.md` | `conformance/THIRD_PARTY_CHECKLIST.md` | `fedb874720f216fc066a8ea8a050aa1d832dd3efd174745bfe61fa991d430206` | 独立性定义与验收流程 |
| `SPEC_ISSUES.md` | `third_party/SPEC_ISSUES.md`（Tier C 新增） | `2a30190f7079dcd9f8bb3f8c4308a7a82cece18ae948cdf5ec79627d06ea6195` | 公开歧义登记簿（3 条内部已知项，0 条第三方问题） |
| `CALL_FOR_IMPLEMENTERS.md` | `third_party/CALL_FOR_IMPLEMENTERS.md`（Tier C 新增） | `cc24d18b45daad6bfa993e0b04ea4f85f3c4d03f166eda57b3b5088a47137478` | 招募公告 |
| `MANIFEST.md` | 本文件 | — | 索引（不参与自校验） |
| `SHA256SUMS` | 自动生成 | — | 上表 8 个实质文档的校验清单 |

**前 6 项已逐一比对，与 `FROZEN.sha256` 中冻结原件的哈希完全一致（逐字节副本，未改一字）。**

在包目录内自检：

```bash
sha256sum -c SHA256SUMS     # 必须 8/8 OK
```

---

## 2. 刻意不提供（独立性红线）

| 排除内容 | 路径 |
|---|---|
| Python 实现源码 | `AIF/aif/*.py` |
| JavaScript 实现源码 | `AIF/implementations/js/*.js` |
| 验收框架源码 | `AIF/conformance/bidirectional.py`、`build_vectors.py` |
| 内部测试 / fuzz / benchmark / 研究报告 | `AIF/tests/`、`AIF/benchmarks/`、`AIF/research/`、`AIF/array_lab/` |
| 溯源与发布状态 | `AIF/provenance/`、`AIF/RELEASE_GATES.md`、`AIF/third_party/archive/` |
| 预期输出之外的"标准答案"、解析细节口头提示 | — |

> `vectors.json` 中的 `expected_aif_*` 是**解码测试输入**，不是要求逐字节复现的编码标准。
> 禁止硬编码 / 查表；验收时有一次使用未公开输入的人工抽查。
> `ADAPTER_PROTOCOL.md` 内的 Python 片段只是 stdin/stdout 外壳，不是 AIF 实现参考。

---

## 3. 修订规则

若第三方发现规范歧义：

1. 先写入 `SPEC_ISSUES.md` 并公开；
2. 维护方公开修订规范与向量、版本递增、旧向量保留；
3. 全部实现同步、全量重跑、更新 `AIF/FROZEN.sha256` 与本清单哈希；
4. **重新发布本包并更新包版本号**。

**不得**为让实现通过而私下改实现、改向量、放宽判定或反向定义规范。
在此之前，本包对应的规范状态仍是「冻结候选（验收期冻结）」，项目**不得**标记 `AIF/1.0 Stable`。
