# AIF 1.0 Stable 发布门槛 — 状态表

> 本文件按用户重新设定的 7 条门槛逐条登记**当前真实状态**。
> 状态只用四种：`✅ 达成` / `⚠️ 部分（有条件）` / `❌ 未达成` / `🙋 需人类执行`。
> 不把「本地能跑」说成「已公开发布」，不把「作者自写的第二实现」说成「第三方」。

**当前结论：不得打 `AIF/1.0 Stable` 标签。** 交付物是 `AIF/0.9 完整工程`。

---

## 本轮「三个问题」逐条交代

| 问题 | 你给的完成标准 | 本轮结果 | 判定 |
|---|---|---|:---:|
| **1. Array 场景 token 效率** | 在明确的目标数据集上，找到稳定优于 JSON 的编码方案 | `AIF/array_lab/` 实现 Row / Column / Hybrid 三个**可解码**实验编码器。在**测量前冻结**的对象数组目标工作负载（15 组参数 × 3 seed + 变长组 = 48 数据点）上：Row **+43.78%**、Column +43.04%、Hybrid +43.73%，**48/48 正例、3/3 seed 均值为正、round-trip 48/48 PASS** | ✅ 达成（附条件） |
| **2. 历史源码与 Benchmark** | 找回原始文件，或明确标记无法恢复的版本，不用重建代码冒充原版 | `provenance/FILE_MANIFEST.md` 逐文件带 SHA256 登记：3 个 `Original`、2 个 `Original (metadata)`、4 个 `Reconstructed`、1 个 `New`；**10 组明确 `Missing`**（0.1–0.8 全部源码、V3–V6 benchmark、0.9 原始 encoder）。明确声明历史实验只有叙述性记录，未完整恢复 | ✅ 达成（标记，非找回） |
| **3. 第三方独立实现** | 第三方开发者只依据规范，独立实现编码器或解码器，并通过一致性测试 | 规范、42 个公开向量、语言无关实现者指南、CLI 接入协议、双向验收框架全部就绪；用作者自写的 JS 参考实现 B 跑通 **A→B 33/33、B→A 33/33**。但**没有任何未参与原始实现的开发者写过实现**，这一步我无法代劳 | ❌ **未达成 / 🙋 需人类执行** |

### 问题 1 的三条附条件（不打折）

1. **目标工作负载偏袒 AIF，已正面声明**：对象数组是 AIF 已知优势场景，同场基准 0.9 本身就有 45/48 正例。所以结论是「**相对 0.9 的增量**」（Row 每组少 7,618 tokens / +16.81 pp，48/48 更优），不是「Array 问题整体解决」。详见 `array_lab/LAB_REPORT.md` §2.4。
2. **标量数组未解决**：V8 `07 Array` 仍是 **−37.99%**（N=1000）/ −38.25%（Lab N=200）。三个实验方案**明确不覆盖**标量数组，没有伪造数字。
3. **Hybrid 是负面结果**：比「总是 Row」只省 1,001 tokens（0.050%），却要多一层语法和最高编码耗时，不值得立项。已如实保留。

**明确不设为目标**：「所有 Array 场景都比 JSON 省 token」。按你的要求，本轮目标是**明确优势/劣势场景与盈亏平衡点，并在预先定义的目标工作负载上取得可重复优势** —— 已做到：实验编码 k\*=1，0.9 k\*=2，k=1 时 0.9 为 −24.70% 而实验编码为 +28.52%。

---

## 7 条发布门槛

| # | 门槛 | 状态 | 证据 | 剩余工作 |
|---|---|:---:|---|---|
| 1 | Array 场景完成行式、列式、混合式三种方案的对照实验 | ✅ 达成 | `array_lab/LAB_REPORT.md`（297 行）、`lab_spec.py`、`lab_codecs.py`、`run_lab.py`；同数据 / 同 tokenizer / 同 JSON 规则，5 方案 + JSON 基准，含耗时与错误恢复 | 若要把结论推广到真实流量，需真实数据集 |
| 2 | 明确不同数组规模下的 token 盈亏平衡点 | ✅ 达成 | 报告 §3：f=5，k 从 1 扫到 32；Row/Column/Hybrid k\*=1，0.9-S/T k\*=2；另发现 k≥16 后 Column 反超 Row | 其他 f 值只做了 k 扫描的 f=5，未做二维全扫 |
| 3 | 核心数据类型和边界情况通过完整测试 | ✅ 达成 | `tests/verify_all.py` **9/9**；单元测试 **104/104**；fuzz **639/639** 零损坏零分歧；`conformance/vectors.json` **42** 向量（33 正向 + 9 负向）；双向兼容性 **A→B 33/33、B→A 33/33**；V8 **17/17** round-trip | 嵌套数组等仍为设计边界（明确报错，不静默） |
| 4 | 历史源码恢复情况有明确记录 | ✅ 达成 | `provenance/FILE_MANIFEST.md`（脚本自动生成、SHA256 实测、不可混淆声明）；`RECOVERY_STATUS.md` 为原始一手证据 | 0.1–0.8 源码与 V3–V6 脚本**确实缺失**，只能日后找回，不能用重建替代 |
| 5 | 正式语法规范冻结 | ⚠️ 部分 | `specification/AIF-0.9.md` 已定稿；新增 `conformance/IMPLEMENTER_GUIDE.md` 语言无关说明；规范示例与实现逐行一致由 `test_spec_examples.py` 自动校验 | 第三方实现过程中若发现歧义，须**公开修订并重新冻结**；在此之前只能称「0.9 冻结候选」 |
| 6 | 第三方独立实现通过一致性测试 | ❌ 未达成 / 🙋 | 框架 `conformance/bidirectional.py` 已就绪且可接入任意语言；`THIRD_PARTY_CHECKLIST.md` 定义身份与禁止事项；**当前 0 个第三方实现** | **必须由未参与原始实现的人类开发者完成**。本会话写的 JS decoder/encoder 属参考实现 B，不计入 |
| 7 | Benchmark 数据、代码和运行环境可以公开复现 | ⚠️ 部分 | 所有数据由脚本生成（无手工数据）、seed 固定、环境记录 Python 3.13 / tiktoken 0.14 / Node 22 / cl100k_base；`verify_all.py` 一键复现；负 reduction 全保留 | **项目仍在本机目录，尚未发布到任何公开仓库**，因此「公开复现」只做到「本地完全可复现」 |

**统计：4 条达成、2 条部分、1 条未达成（且需人类执行）。**

---

## 门槛 6 为什么不能由本项目自己完成

- 两个作者自写的实现能证明**规范自洽**，不能排除「作者默契」：写的人知道答案，
  会不自觉地把没写清的地方按自己的理解补上。
- 用户明确指出：「第三方能够独立实现并通过测试，比我们自己写出更多版本更能证明规范成熟。」
  因此**不再写第三个作者自写的实现来凑数**。
- 交付包已按「只给规范 / 向量 / 指南，不给参考实现源码」设计，
  见 `conformance/THIRD_PARTY_CHECKLIST.md`。

## 达成门槛 6 的最小动作

1. 把 `specification/AIF-0.9.md`、`conformance/IMPLEMENTER_GUIDE.md`、
   `conformance/vectors.json`、`conformance/ADAPTER_PROTOCOL.md` 交给一位
   未参与本项目的开发者（建议 Go / Rust / TypeScript）。
2. 对方只依据上述材料实现 decoder（encoder 可选），记录实现期间发现的
   **所有规范歧义**，不阅读 `AIF/aif/` 与 `AIF/implementations/js/`。
3. 验收方运行：
   ```bash
   python AIF/conformance/build_vectors.py --verify
   python AIF/conformance/bidirectional.py --adapter <对方配置>.json
   ```
4. 通过标准：`A→B 33/33`、`B→A 33/33`（仅 decoder 时标 N/A）、
   `negative FAIL 0`、`third_party: true` 且身份经人工确认。
5. 把报告、实现者标识、公开材料哈希、歧义清单写入本文件，
   再重新评估门槛 5 与 7。

## 复现本状态表所引用的全部数字

```bash
python AIF/tests/verify_all.py                 # 9/9
python AIF/array_lab/run_lab.py               # 重写 LAB_REPORT.md
python AIF/provenance/build_manifest.py       # 重写 FILE_MANIFEST.md
python AIF/conformance/build_vectors.py --verify
python AIF/conformance/bidirectional.py       # 重写 BIDIRECTIONAL_REPORT.md
```

## 不变的原则

不改数据美化 benchmark、不隐藏负 reduction、不删失败案例、
不声称 AIF 一定比 JSON 省、不把 counterfactual 说成已实现特性、
不把重建版冒充历史原件、不把作者自写的第二实现冒充第三方。
