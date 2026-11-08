# AIF Array Optimization Lab

独立实验目录。**不是 AIF/0.9 的修改，也不是 1.0 定稿。**

- Header 用 `AIF/1.0-alpha`，与 `AIF/0.9` 明确区分，两者 decoder 不通用。
- `AIF/aif/` 的 encoder/decoder、`specification/AIF-0.9.md`、
  `benchmarks/` 的数据与结果在本实验中**一个字都没改**，只作为基准被 import。
- 三个实验 codec 都有**真 decoder**，所有候选都经过 round-trip 校验；
  只做 token 计数而不可解码的变体不算候选方案。

## 文件

| 文件 | 作用 |
|---|---|
| `lab_spec.py` | **测量前冻结**的目标工作负载、参数网格、seed、判定门槛、统一数据生成与计数规则 |
| `lab_codecs.py` | Row / Column / Hybrid 三个实验编解码器 + 共享转义规则 |
| `run_lab.py` | 实验驱动：校准、对照、盈亏平衡、对抗、耗时、错误恢复、报告生成 |
| `LAB_REPORT.md` | 自动生成的完整报告（每次运行全部重测） |
| `fitted_thresholds.json` | Hybrid 阈值，只在校准集拟合的产物 |

```bash
python AIF/array_lab/run_lab.py     # 约 1–2 分钟，重写 LAB_REPORT.md 与阈值文件
python AIF/tests/verify_all.py      # 确认 0.9 工程未回归（Lab 不进 verify_all）
```

依赖：`tiktoken`（`cl100k_base`）、Python 3.10+。不需要 Node.js。

## 三种编码

输入统一为 `[{"items": [ 扁平标量对象, ... ]}, ...]`，组内对象数可变。
三者共用**完全相同**的 schema 声明、转义规则和 `@//data/` 块结构，
唯一差别是数据矩阵是否转置：

| 方案 | 布局 | 每块 |
|---|---|---|
| A Row | 一个对象一行 | k 行 × f 列 |
| B Column | 一个字段一行（你给的 `@//columns/` 草案） | f 行 × k 列 |
| C Hybrid | 确定性规则在 A/B 中选一 | 块头写 `@//mode/` |

```
AIF/1.0-alpha
@//columns/
items[]:object name:s qty:i ok:b
@//groups/ 2          <- 检出「截断到块边界」的静默丢数据
@//data/
3                     <- 本组对象数，支持不同长度数组
alpha,beta,gamma      <- name 列
1,2,3                 <- qty 列
true,false,@null      <- ok 列
@//data/
1
...
```

转义：`\,`（值内逗号）、`\\`、`\n`/`\r`/`\t`/`\uXXXX`、
`\e`（空串）、`-`（字段缺失）、`@null`（null）、`\@` / `\-`（首字符转义）。
空格不转义 —— 值按整行读取，空格无结构含义。

## 关键结论（详见 `LAB_REPORT.md`）

- 预先定义的**对象数组**目标工作负载（48 数据点 × 3 seed）上，
  三个实验方案都稳定优于 JSON（+43.04% ～ +43.78%），
  相对 0.9-S（+26.97%）多省约 16 pp / 7,600 tokens 每组。
- **k=1 的小型数组负担被消除**：0.9 在 k=1 是 −24.70%、k≥2 才转正；
  三个实验方案 k=1 即为正。原因是 schema 全局只声明一次。
- **Hybrid 是负面结果**：比「总是 Row」只省 1,001 tokens（0.050%），
  却要多一层语法和最高编码耗时，不值得立项。
- **错误恢复抓到 0.9 的真实缺陷**：`@record` 边界截断会静默少一条记录
  （0.9 没有记录总数声明）；实验 codec 因 `@//groups/` 为 0 次静默损坏。
- **必须说清的偏袒**：目标工作负载是 AIF 已知优势场景，0.9 本身 45/48 正例，
  所以这**不是**「Array 问题整体解决」。标量数组 V8 `07 Array` 仍为 −38.25%，
  三个实验方案明确不覆盖该结构。

## 明确的设计边界

- 只支持**扁平标量对象**；对象内嵌对象/数组会明确报错，不静默产出错误数据。
- 字段名不允许空格、逗号、`:`、`@`、`[]` 等语法字符。
- 不支持局部错误恢复（全部 fail-fast）。
- 只测了 `cl100k_base` 一个 tokenizer、Python 一个实现。
- 合成数据，不是真实生产流量；结论只在声明的参数范围内成立。
