# 1.0 Stable 第三方独立实现验收清单

## 当前状态：**未达成（0 个第三方独立实现）**

| 已有实现 | 作者 | 是否计入门槛 #6 |
|---|---|:---:|
| `AIF/aif/`（Python encoder + decoder） | 本项目 / 本会话 | ❌ 原始实现 |
| `AIF/implementations/js/decoder.js` | 本项目 / 本会话 | ❌ 作者自写的参考实现 B |
| `AIF/implementations/js/encoder.js` | 本项目 / 本会话 | ❌ 作者自写的参考实现 B |
| 未参与原始实现的开发者写的实现 | — | **尚未出现** |

**必须明确**：`decoder.js` 在上一轮曾被称作「第二个独立实现」，
那只表示它**没有复用 Python 代码结构**、可用于发现规范歧义；
它仍是同一作者在同一会话里写的，**不构成第三方独立实现**。
两个作者自写的实现只能证明规范自洽，不能排除「作者默契」。
用户指出这一点是正确的，本清单据此更正。

## 「第三方」的定义（全部满足）

1. 实现者**没有参与**本项目的任何 encoder / decoder / 规范 / benchmark 编写；
2. 拿到的材料**只有**下面的公开交付包，没有参考实现源码、没有口头提示、
   没有事先看过测试向量的预期 AIF 文本以外的内部讨论；
3. 用与本项目不同的语言或完全独立的代码库从零实现；
4. 实现过程若发现规范歧义，先记录并反馈，**不通过阅读参考实现来猜答案**。

第 4 条最重要：照着别人的代码"翻译"一遍，验证不了规范是否写清楚。

## 给第三方的公开交付包

| 文件 | 用途 |
|---|---|
| `specification/AIF-0.9.md` | 正式语法规范（normative，冻结） |
| `conformance/IMPLEMENTER_GUIDE.md` | 语言无关的实现者指南，不引用 Python 实现 |
| `conformance/vectors.json` | 42 个公开测试向量（33 正向 + 9 负向），严格合法 JSON |
| `conformance/ADAPTER_PROTOCOL.md` | CLI 接入协议 |
| `conformance/third_party_adapter.example.json` | 适配器模板 |

**不提供**（避免污染独立性）：

- ❌ `AIF/aif/` 的 Python 源码
- ❌ `AIF/implementations/js/` 的 JS 源码
- ❌ 本项目内部的研究报告、fuzz 报告、讨论记录
- ❌ 任何「看这里就知道该怎么解析」的口头提示

验收脚本 `bidirectional.py` 与参考实现 A 由**验收方**运行，第三方不需要读它。

## 六步验收流程（对应发布门槛）

| # | 步骤 | 状态 |
|---|---|:---:|
| 1 | 发布正式 AIF 语法规范（类型、数组、嵌套对象、optional、null、转义、错误处理） | ✅ 已冻结 |
| 2 | 发布公开测试向量（输入 JSON / 预期 AIF / 预期解码 JSON） | ✅ 42 个 |
| 3 | 提供独立于 Python 实现的规范说明 | ✅ `IMPLEMENTER_GUIDE.md` |
| 4 | 找一位**未参与原始实现**的开发者独立实现 Decoder | ⬜ **未完成（需真人）** |
| 5 | 用同一组测试向量交叉验证 | ✅ 框架就绪，待第三方运行 |
| 6 | 验证编码器 A → 解码器 B，编码器 B → 解码器 A | ✅ 框架就绪；用作者自写 B 已 33/33 跑通，待第三方重跑 |

第 4 步是唯一无法由本项目自己完成的：**不能再写一个我们自己的版本来冒充**。

## 通过标准

```bash
python AIF/conformance/build_vectors.py --verify
python AIF/conformance/bidirectional.py --adapter <第三方配置>.json
```

报告 `BIDIRECTIONAL_REPORT.md` 必须同时满足：

- `A→B` **33/33 PASS**（第三方 decoder 解码参考 AIF，两种模式）
- `B→A` **33/33 PASS**（第三方 encoder 的 AIF 被参考 decoder 还原）
- `negative` **FAIL 0**（7 个可构造负例全部拒绝；2 个非 JSON 值按 `construct_hint` 单独验证）
- 适配器 `third_party: true`，且身份经人工确认
- 第三方在实现期间提出的**规范歧义清单**为空，或全部已修入规范并重新冻结

只实现 decoder 也能满足门槛的一半：此时 `B→A` 标 `N/A`，
但需在发布说明中如实写明「仅验证了单向兼容性」。

## 禁止事项（验收方同样受约束）

- ❌ 为了让第三方通过而修改测试向量、删除失败案例或放宽相等判定
- ❌ 第三方实现失败时，反过来改规范去迁就实现（应记录歧义、公开修订）
- ❌ 把作者自写的第二/第三个实现计入「第三方」
- ❌ 因某个负 reduction 或某个向量失败而隐藏该数据

## 完成后的记录

把以下内容写进 `RELEASE_GATES.md` 并附证据路径：

- 实现者 / 团队标识、所用语言、交付日期
- 公开材料清单与哈希
- `BIDIRECTIONAL_REPORT.md` 全文
- 规范歧义清单及处理结果
- 验收人签字（人工确认独立性）

在此之前，AIF 只能称为 `AIF/0.9 完整工程`，**不得打 1.0 Stable 标签**。
