# AIF — AI-Native Format

AIF 是一种面向 AI Agent / LLM 之间**结构化数据交换**的面向行文本格式。它把 schema 与数据分离，字段名和类型只声明一次，Record 按 schema 顺序排列，从而在大量重复结构的数据上减少 token。

**AIF 不是「更短的 JSON」，也不承诺所有数据都比 JSON 省。** 长自然语言文本、scalar 数组等场景可能更耗 token。它的价值是 AI-native structured communication。

当前版本：**AIF/0.9**（Python 与 JavaScript 两个**作者自写的参考实现**，均以 `specification/AIF-0.9.md` 为准并互相验证）。

> 发布状态见 `RELEASE_GATES.md`：**尚未达到 1.0 Stable**。7 条门槛中 4 条达成、2 条部分、1 条未达成 —— 缺的是「未参与原始实现的第三方独立实现」，这一步不能由本项目自己补。

---

## 目录结构

```
AIF/
├── README.md                       本文件
├── RELEASE_GATES.md                ★ 1.0 发布门槛状态表（7 条逐条登记）
├── aif/
│   ├── __init__.py                 统一入口 json_to_aif / aif_to_json
│   ├── encoder.py                  编码器（含 Text Mode）
│   └── decoder.py                  解码器（固定槽位游标模型）
├── implementations/js/             参考实现 B（作者自写，非第三方、非 SDK）
│   ├── decoder.js                  aifToJson()
│   ├── encoder.js                  jsonToAif()（B→A 方向）
│   ├── cli.js / batch_cli.js       decoder bridge
│   ├── encode_cli.js               encoder bridge
│   └── README.md
├── specification/
│   └── AIF-0.9.md                  正式语法规范（含跨语言互操作约束 §12）
├── conformance/                    ★ 1.0 一致性验收包
│   ├── IMPLEMENTER_GUIDE.md         语言无关的实现者指南
│   ├── vectors.json                 42 个公开测试向量（严格合法 JSON）
│   ├── build_vectors.py             生成 / --verify 校验向量
│   ├── bidirectional.py             A↔B 双向兼容性验证
│   ├── BIDIRECTIONAL_REPORT.md      报告（自动生成）
│   ├── ADAPTER_PROTOCOL.md          第三方 CLI 接入协议
│   ├── THIRD_PARTY_CHECKLIST.md     ★ 门槛 #6 验收清单
│   └── third_party_adapter.example.json
├── array_lab/                      ★ Array Optimization Lab（实验性，非 0.9）
│   ├── lab_spec.py                  测量前冻结的目标工作负载与判定门槛
│   ├── lab_codecs.py                Row / Column / Hybrid 三个可解码实验编码器
│   ├── run_lab.py                   实验驱动（校准 / 对照 / 盈亏平衡 / 耗时 / 错误恢复）
│   ├── LAB_REPORT.md                完整报告（自动生成）
│   ├── fitted_thresholds.json       Hybrid 阈值（只在校准集拟合）
│   └── README.md
├── provenance/                     ★ 历史源码溯源
│   ├── FILE_MANIFEST.md             Original / Reconstructed / Missing 清单（含 SHA256）
│   └── build_manifest.py            实测生成脚本
├── tests/                          104 项单元测试 + fuzz + 一键验证
│   └── verify_all.py               ★ 9/9 CHECKS PASSED
├── benchmarks/
│   ├── benchmark_v8.py             17 类数据集 V8 benchmark
│   └── RESULTS.md                  实测结果（由脚本生成）
├── research/                       第一 / 第二轮 Token Efficiency 研究
│   ├── token_study.py / FINDINGS.md
│   ├── study_round2.py / FINDINGS_ROUND2.md
│   └── predictor.py / predictor_model.json
└── examples/
    ├── make_examples.py            生成并校验示例
    └── *.json / *.aif              5 组示例数据与其 AIF 文本
```

`array_lab/` 使用独立 header `AIF/1.0-alpha`，与 `AIF/0.9` **不兼容**，
两者不可共用 decoder；它没有修改 0.9 的任何文件。

## 快速开始

需要 Python 3.10+、`tiktoken`、Node.js ≥ 18（**无需 npm install**）：

```bash
python -m pip install tiktoken
python AIF/tests/verify_all.py        # ★ 一键全量验证
```

`verify_all.py` 正常应输出 `9/9 CHECKS PASSED`。也可以单独跑：

```bash
python AIF/tests/run_all.py                    # ALL TESTS PASSED (104/104)
python AIF/tests/test_spec_examples.py         # SPEC EXAMPLES: 2/2 MATCH
python AIF/tests/cross_validate.py             # 78/78 AGREE
python AIF/tests/fuzz_roundtrip.py             # 639/639，0 静默损坏、0 分歧
python AIF/conformance/build_vectors.py --verify   # 42 vectors VERIFIED
python AIF/conformance/bidirectional.py        # A→B 33/33, B→A 33/33
python AIF/benchmarks/benchmark_v8.py         # 17/17 PASS，重写 RESULTS.md
python AIF/examples/make_examples.py          # 5/5 PASS
python AIF/array_lab/run_lab.py               # Array Lab 报告（约 1–2 分钟）
python AIF/provenance/build_manifest.py       # 重写溯源清单
python AIF/research/token_study.py            # 第一轮报告
python AIF/research/study_round2.py           # 第二轮报告
python AIF/research/predictor.py --self-test  # 5/5 PASS
```

研究脚本 `token_study.py` / `study_round2.py` / `array_lab/run_lab.py`
是**独立实验**（各约 1–3 分钟），不进 `verify_all.py`，也不改动格式、
encoder、decoder 或任何 benchmark 数据。`predictor.py` 是独立研究工具，
不被核心包、任何测试或 benchmark 导入。
`conformance/` 的两项**已进** `verify_all.py`，因为它们属于发布门槛。

代码调用：

```python
import sys
sys.path.insert(0, "AIF")
from aif import json_to_aif, aif_to_json

data = [{"id": "a1", "profile": {"city": "Shanghai"}}]
text = json_to_aif(data)
assert aif_to_json(text) == data

text_mode = json_to_aif(data, text_mode=True)   # 长文本可选
assert aif_to_json(text_mode) == data
```

## 当前完成度

| 阶段 | 状态 |
|---|---|
| 1 修复 0.9 decoder / V7 8/8 PASS | 完成（重建版基线 + 正式 token 数字） |
| 2 AIF/0.9 Specification | 完成 |
| 3 完善 Array of Objects | 完成（13/13 系统用例） |
| 4 重新设计 Benchmark | 完成（17 类数据集，V8） |
| 5 Token Efficiency 研究 | 完成（Text Mode 实现 + 量化结论） |
| 6 AIF 1.0 目录结构 | 完成本目录；未做多语言 SDK / 协议层 |
| 附加：规范自洽性验证 | 完成（**两个作者自写的参考实现** + 双实现交叉测试 + fuzz）；**不等于第三方独立实现** |
| 阶段 5 深化：Token Efficiency 研究 | 完成（4 个 tokenizer、crossover 扫描、counterfactual，见 `research/FINDINGS.md`） |
| 阶段 5 深化：第二轮研究 | 完成（对象数组 counterfactual、`should_use_aif` 证伪，见 `research/FINDINGS_ROUND2.md`） |
| 本轮：Array 行/列/混合对照实验 | 完成（`array_lab/LAB_REPORT.md`，48 数据点 × 3 seed） |
| 本轮：历史源码溯源清单 | 完成（明确标记 Missing，**未找回、未冒充**） |
| 本轮：1.0 一致性验收包 | 完成框架与公开向量；**第三方实现仍缺** |
| 本轮：发布门槛状态表 | 完成（`RELEASE_GATES.md`） |

### 验证结果

| 检查 | 结果 |
|---|---|
| 单元测试 `run_all.py` | **104/104 PASS**（32 V7 + 59 边界/错误 + 13 对象数组） |
| 规范示例一致性 `test_spec_examples.py` | **2/2 MATCH**（逐行比对 + 可解码） |
| 双实现一致性 `cross_validate.py` | **78/78 AGREE**（5 示例 + V7×2 + V8×2 + 边界×2 + 1000 条规模） |
| 随机 fuzz `fuzz_roundtrip.py` | **639/639** 无损；81 组被 encoder 明确拒绝；0 静默损坏、0 跨语言分歧 |
| V8 benchmark round-trip | **17/17 PASS** |
| 示例校验 | **5/5 PASS** |
| 历史 V7 重跑 | **8/8 PASS** |
| 公开测试向量 | **42**（33 正向 + 9 负向），`--verify` 防篡改 |
| 双向兼容性 A↔B | **A→B 33/33、B→A 33/33**，逐字节 33/33，negative FAIL 0 |
| **一键验证 `verify_all.py`** | **9/9 CHECKS PASSED** |
| Array Lab | 48 数据点 × 3 seed，三方案 round-trip 全 PASS |
| 溯源清单 | 根目录 10 个文件逐一带 SHA256；10 组 Missing 明确登记 |

两个实现都从规范出发编写，但**都是本项目作者自写**，只证明规范自洽。
fuzz 使用固定 seed `20261108`，报告在 `tests/FUZZ_REPORT.md`；
任何一次分歧都视为**规范 bug**，规范与双方实现一起修。

## 本轮：三个待解决问题

### 1. Array 场景 token 效率 → 已在**预先定义的目标工作负载**上达成

`array_lab/` 实现 Row / Column / Hybrid 三个**真能解码**的 `AIF/1.0-alpha`
实验编码器，共用同一数据、`cl100k_base`、同一 JSON 序列化规则。
目标工作负载在 `lab_spec.py` 里**测量前冻结**（对象数组，f∈{3,5,8}、
k∈{2,5,10,20,50}、N=200、seed 101/202/303 + 变长组，共 48 数据点）。

| 方案 | 平均 reduction | 正例 | 相对 0.9 增量 |
|---|---:|---:|---:|
| A Row | **+43.78%** | 48/48 | 每组少 7,618 tokens / +16.81 pp |
| B Column | +43.04% | 48/48 | 每组少 7,546 tokens |
| C Hybrid | +43.73% | 48/48 | 比「总是 Row」只省 0.050%，不值得新语法 |
| 0.9-S / 0.9-T（基准） | +26.97% | 45/48 | — |

**必须同时说清的三点**：① 目标工作负载是 AIF 已知优势场景，0.9 本身就有
45/48 正例，所以贡献是「相对 0.9 的增量」而非「从负转正」，偏袒问题在报告
§2.4 正面回答；② 标量数组 V8 `07 Array` 仍是 **−37.99%**，三方案明确不覆盖，
**没有解决**；③ 盈亏平衡点已量化 —— 实验编码 k\*=1，0.9 k\*=2（k=1 时
0.9 为 −24.70%、实验编码为 +28.52%），小型数组的结构负担确实被消除了。

另一个收获：错误恢复测试抓到 **0.9 的真实缺陷** —— 截断到 `@record`
边界会静默少一条记录（0.9 没有记录总数声明）。实验 codec 用 `@//groups/`
声明做到 0 次静默损坏。所有方案仍都是 fail-fast，不支持局部恢复。

### 2. 历史源码 → 已明确标记，未冒充

`provenance/FILE_MANIFEST.md` 由脚本实测生成，逐文件带 SHA256：

- `Original` 3 个（`aif_decoder_v09_original.py`、`test_token_benchmark_v7.py`、
  `BENCHMARK.md`）+ 2 个恢复包元数据；
- `Reconstructed` 4 个；`New` 1 个（本会话 V7 rerun）；
- **Missing 10 组**：0.1–0.8 全部 encoder/decoder、0.9 原始 encoder、
  V3–V6 benchmark、早期测试与历史 README。

`aif_decoder_v09.py` 与 `_reconstructed.py` 经哈希验证**字节相同**，
是同一份重建代码的两个文件名，不算两个版本。
结论如实写为：**历史实验只有叙述性记录，未完整恢复，且不能用重建版替代**。

### 3. 第三方独立实现 → **未达成，且不能由本项目自己补**

规范、42 个公开测试向量、语言无关的 `IMPLEMENTER_GUIDE.md`、
CLI 接入协议、双向验收框架、身份与禁止事项清单全部就绪；
框架用作者自写的 JS 参考实现 B 跑通 **A→B 33/33、B→A 33/33**，
并用临时适配器验证过 `--adapter` 第三方接入路径可用。

但 `implementations/js/` **是本项目作者在同一会话写的**，
早前把它称为「第二个独立实现」是误导，已更正：两个作者自写的实现
只能证明规范自洽，不能排除「作者默契」。门槛 #6 需要一位
**未参与原始实现**的开发者，只依据规范/向量/指南独立实现 —— 这一步需要真人。
详见 `conformance/THIRD_PARTY_CHECKLIST.md`。

**不把「所有 Array 场景都优于 JSON」当作目标**；目标是明确优势/劣势场景
与盈亏平衡点，并在预先定义的目标工作负载上取得可重复优势。

## V8 关键结论

Tokenizer `cl100k_base`，每类 1000 条，17 类数据同规模：

- 结构化数据优势明显：Deep nested **+54.08%**、Nested +42.79%、Tool Calls +38.81%（Text Mode +47.14%）、Flat +33.28%。
- **AIF 更差的数据集完整保留**：Structured Mode 有 5 组为负，最差 Long Text **−109.60%**、Array **−37.99%**；Text Mode 仍有 1 组为负（Array −37.99%）。
- Text Mode 让 Long Text 从 −109.60% → **+4.10%**、Messages 从 −29.76% → **+8.08%**，且 decoder 无需改动。
- 缺失标记由 `@missing` 改为 `-`，17 类数据合计省 **17,930 tokens**。

完整数字和负 reduction 清单见 `benchmarks/RESULTS.md`。

## 研究：Token Efficiency（阶段 5 深化）

`python AIF/research/token_study.py` → `research/FINDINGS.md`。**只读实验，不改格式**，所有 counterfactual 仅供 token 计数，不是已实现语法。

- **多 tokenizer 交叉验证**：`cl100k_base` / `o200k_base` / `p50k_base` / `r50k_base` 四个 tokenizer 下结论方向一致 —— 17 类中 Structured 有 5～6 组更差、Text Mode 都只剩 1 组更差。差异照实记录：`17 Mixed realistic` 在 cl100k 为 +10.22%，在 p50k/r50k 转为 −2.45%（老 BPE 切分更细）。
- **Array 弱点定位**：不是值本身，而是 `@array / count / 每元素一行` 的结构开销。21 组参数扫描中原格式**始终为负**（−27.75% ～ −0.55%）。行内数组 counterfactual 对短字符串数组有效（k≥5 转正），但**对整数数组零收益** —— 不是通用解法。
- **长文本 crossover**：Structured 仅 2/14 组为正，Text Mode 14/14 全正；但文本越长收益越薄（2000 字符时仅 +0.26%），因为文本本身主导 token 总量，这是数学必然。
- **量化判据**：字段越多、键名越长越占优（50 字段/键长 12 → +78.94%；1 字段/键长 2 → −0.80%）。**字段名重复总量远大于值体量、且记录数多**时才该用 AIF。
- **反直觉负面结果**：把连续 `-` 合并为 `-N` 反而**多花 3,333 tokens**——`-\n` 在 BPE 里是单 token，`-N` 会被切成两个。即使把 `-` 行全删（理论下界、不可解码）也只省 4.33%。结论：**单字符 `-` 已接近 BPE 最优，不为缺失表示引入新语法**。

建议：0.9 保持定稿不动；行内数组留作 AIF/1.0 候选扩展单独立项；长文本默认 Text Mode；「少量记录 + 长文本 + 大量短数组」直接保留 JSON。

## 研究：第二轮 — 对象数组与决策预估

`python AIF/research/study_round2.py` → `research/FINDINGS_ROUND2.md`。**只读，不改格式**；所有变体仍是仅用于计数的 counterfactual，不是已实现语法。

- **对象数组行内化有效但不通用**：57 组中 50 组省、3 组更费、4 组持平，平均 **+2,810 tokens/组**。`pipe`（Text Mode + `|` 分隔）几乎零收益 —— `|` 自身也要占 token，行内化只在 Structured Mode 下有意义。
- **真正的大头是 schema 重复**：`@objects` 的 schema 行在每条记录里都重写一次。全局只声明一次（hoist）平均省 **+3,628 tokens/组**，V8 `10 Multiple Tool Calls` 省 **+16,983**；hoist + inline 组合上限 +6,439 tokens/组。
- **两项都不进 0.9**：它们要求同时改 encoder、Python/JS 两套 decoder、规范、双实现一致性与 fuzz，而 0.9 已定稿。schema hoisting 列为 **AIF/1.0 候选扩展**单独立项。
- **预估器研究得到否定结论**：线性模型在从未参与拟合的 V8 17 类上 MAE **21.78pp**（系统性高估，预测 +30～+57% 而实际 +0～+54%），误判代价 **11,019 tokens** 与「总是用 AIF Text Mode」完全相同，**没有增量价值**。可解释粗规则在 V8 上代价 0，但在独立合成留出集上代价 **50,083 tokens**（线性模型仅 448）—— 谁都不能泛化。
- **证伪证据**：`array_density≈1.39` 这一档同时存在「该用 JSON」（最优 reduction 0%）与「AIF 省 24.93%」的数据；聚合特征丢掉了 BPE 在 token 级的切分信息，所以「该不该用 AIF」无法被几个结构特征可靠判定。
- **因此 `should_use_aif(data, exact=True)` 是唯一可靠路径**：真编码、真计数、验证 round-trip、100% 准确，适合批量/缓存决策。`exact=False`（线性模型或粗规则）的结果一律带 `reliable=False` 与警告，只作粗筛，**不能作为决策依据**。

`predictor.py` 不属于核心包、不进 `verify_all.py`。用法：`--demo`、`--self-test`（5/5）、`--file data.json --exact`（推荐）、`--method rule`、`--train`（重新拟合）。

## 已修复的问题

| 问题 | 处理 |
|---|---|
| `Invalid boolean value: English` / `Expected @record, got: AI` | 每个 schema 字段固定一个值槽位，游标不再靠「看下一行像什么」猜 optional |
| decoder 把 AIF 文本当文件名 `open()` | 输入类型校验，非字符串直接 `TypeError` |
| 字符串值恰为 `@missing` / `@null` / `-` 导致数据丢失 | 以 `@` / `-` 开头的值强制转义 |
| 单条记录 `[{...}]` 解码成 `{...}` | `@single` 标记，单/多记录类型无损 |
| 嵌套对象为 null 被当成字段缺失 | `@onull:<path>` |
| 语法两套并存 | 定稿采用草案的 `field?:s` / `tools[]:object`，差异见规范 §10 |
| **控制字符静默损坏数据**（fuzz 发现） | `\v` `\f` `\x1c` `\x85` `\u2028` 等被 `splitlines()` 当换行；现一律 `\uXXXX` 转义，且 decoder 只按 LF/CRLF/CR 切分 |
| **空对象 `{}` / `[{}]` 解码报错**（fuzz 发现） | 空 schema 行按位置读取，不再「跳过所有空行」 |
| **大整数 / NaN / Infinity 跨语言分歧**（独立实现发现） | encoder 明确拒绝，规范 §12 定义数值范围 |
| **字段名语法字符未全部校验**（fuzz 发现） | 推断 schema 时逐层校验，违反即报错，不产出歧义 token |

## 已知限制

- AIF 0.1–0.8 的全部 encoder/decoder 源码、v3–v6 benchmark 脚本**未恢复**；本目录不依赖它们。恢复包根目录下的 `aif_encoder_v09.py` / `aif_decoder_v09.py` / `*_original.py` / `test_token_benchmark_v7.py` 是**历史文件**，不是交付实现。
- 历史 `test_token_benchmark_v7.py` 仍缺 v08 模块依赖；`test_token_benchmark_v7_rerun.py` 是当时的替代验证脚本，0.8 / Compact 列为 `N/A`，未伪造数字。
- 旧 `aif_decoder_v09_original.py` 的游标错位**没有被修复**，只是被重建版取代，作为历史快照保留。
- 不支持嵌套数组、字段名含空白/语法字符、顶层非对象、schema 字段混合类型、超出 ±(2^53−1) 的整数、NaN/Infinity。详见规范 §11。
- schema 由全体记录预先推断，不支持流式增量编码。
- `implementations/js/` 是**作者自写的参考实现 B**（decoder + encoder），不是第三方独立实现，也**不是 SDK**。多语言 SDK、`Content-Type: application/aif`、HTTP / WebSocket 传输层均按计划不做。
- `research/predictor.py` 的近似模式**未校准**（V8 留出 MAE 21.78pp、误判代价与平凡基线相同），只有 `exact=True` 可靠；它是研究工具，不是生产决策组件。
- 对象数组 `@objects` 的 schema 行每条记录重复一次，已量化为 AIF/1.0 候选优化点（见 `research/FINDINGS_ROUND2.md`），**当前 0.9 未改动**。
- `array_lab/` 的三个实验 codec 只支持扁平标量对象数组，**不覆盖标量数组**；header `AIF/1.0-alpha` 与 0.9 不兼容，不能混用 decoder。
- **0.9 已知可靠性缺陷（本轮实测发现）**：文本被截断到 `@record` 边界时，decoder 会静默少返回一条记录而不报错，因为 0.9 没有记录总数声明。实验 codec 已用 `@//groups/` 规避；0.9 本身**未修改**，建议作为 1.0 候选修复项。
- 规范目前是「0.9 冻结候选」：第三方实现期间若发现歧义，须公开修订并重新冻结。
- 项目仍在本机目录，**未发布到公开仓库**，因此「运行环境可复现」只做到本地完全可复现。
- 距离打上 "AIF/1.0 stable" 还差**第三方独立实现**（门槛 #6）；目前是两个作者自写的实现，不是生态。逐条状态见 `RELEASE_GATES.md`。

## 原则

不改数据来美化 benchmark、不隐藏负 reduction、不删失败案例、不声称 AIF 一定比 JSON 省、不用「加个空值判断」掩盖游标错位、**不把 counterfactual 计数实验说成已实现的格式特性**、**不把未校准的近似预估包装成可靠组件**、**不把重建版冒充历史原件**、**不把作者自写的第二实现冒充第三方独立实现**、**不事后修改预先定义的目标工作负载来凑结论**。所有结论可复现：重跑 `verify_all.py`（测试与一致性）、`array_lab/run_lab.py`（Array 实验）、`research/token_study.py` 或 `research/study_round2.py`（研究）即重新生成报告。
