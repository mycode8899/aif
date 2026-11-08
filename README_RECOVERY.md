# AIF Project Recovery Bundle

## 重要说明：恢复范围

本压缩包分为两类文件：

1. **历史原件**：从此前对话/文件库中找回，保持原内容。
2. **重建文件**：原始文件未能找回，根据当时保留的协议设计、示例和测试结果重新实现。它们不是原文件的逐字副本。

本次确实找回的历史文件：
- `aif_decoder_v09_original.py`：此前保存的 AIF/0.9 decoder 快照。它对应 V7 测试时的旧解析实现，已知存在 optional/object-array 解析错位问题。
- `test_token_benchmark_v7.py`：此前保存的 V7 benchmark 脚本原件。
- `BENCHMARK.md`：此前保存的 AIF 0.1–0.6 benchmark 与设计记录。

根据已有项目上下文重建：
- `aif_encoder_v09.py`
- `aif_decoder_v09.py`
- `aif_decoder_v09_reconstructed.py`
- `test_stress_v09.py`

**没有找回** AIF 0.1–0.8 的全部 encoder/decoder 源文件、所有旧测试脚本和所有历史版本 README。因此本压缩包不能诚实地称为全部历史代码的逐字恢复。缺失文件在 `RECOVERY_STATUS.md` 中列出。

## 新重建版 AIF/0.9 的重要差异

为了避免 V7 暴露的 optional 字段错位，重建版使用显式 `@missing` 表示“字段缺失”。这和旧示例中直接省略 optional 值的编码方式不同，但能让解析器准确知道每个字段占据一个值槽位。

示例：
```text
AIF/0.9

agent_id:s tools:array_object

@record
agent_001
@objects
name:s result.success:b
2
web_search
true
calculator
@missing
```

请注意：这是恢复包中的重建实现，不应在未审查前视为最终 AIF/0.9 标准。

## 安装与运行

建议使用 Python 3.10+。

在此文件夹打开 PowerShell：

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
python test_stress_v09.py
```

V7 benchmark 需要：

```powershell
python -m pip install tiktoken
```

历史 `test_token_benchmark_v7.py` 是原件，可能存在旧版 decoder 调用方式和 Compact round-trip 状态没有真正验证的问题。不要把它的 PASS/FAIL 输出直接当成修复版结果。

## 推荐恢复顺序

1. 先运行 `python test_stress_v09.py`，确认重建版核心 Round-trip。
2. 保存本压缩包的副本，不要覆盖历史原件。
3. 后续再修订 benchmark，让每个格式都实际 decode 并比较结构相等。
4. 再编写正式 `AIF/0.9 Specification`。
5. 通过测试后才考虑标记 AIF/1.0 stable。

## 当前已知研究结论

历史 benchmark 在 `cl100k_base` tokenizer 下显示：
- 某些重复结构化数据上 AIF 有明显 token reduction。
- Flat Agent、Nested Agent State、Tool Calls 等测试曾显示约 34%–45% reduction。
- Messages / 长文本可能比 JSON 更耗 token。
- 结果依赖数据集、tokenizer、schema 重复度和编码实现，不能宣称 AIF 永远比 JSON 短。
