# 第三方实现接入协议（Adapter Protocol）

这个协议让**任意语言**写的 AIF/0.9 实现可以直接复用
`conformance/bidirectional.py` 做双向兼容性验证，不需要改动验收框架。

## 你需要提供两个命令行程序

| 程序 | stdin | stdout | 成功 | 失败 |
|---|---|---|---|---|
| `decode` | AIF 文本（纯文本，UTF-8） | 解码结果的 **JSON**（一行或格式化均可） | exit 0 | 非 0，stderr 写原因 |
| `encode` | 一个 JSON 值（UTF-8） | AIF 文本（纯文本，不要加额外输出） | exit 0 | 非 0，stderr 写原因 |

约束：

- stdout **只能**是结果本身。日志、进度、调试信息一律走 stderr。
- `decode` 输出必须是严格合法 JSON（`NaN` / `Infinity` 不允许）。
- `encode` 遇到规范 §8 列出的非法输入必须**非 0 退出**，不能静默产出文本。
- 每次调用只处理**一个**文档；框架会为每个向量启动一次进程。
- 默认超时 30 秒/次。

Text Mode 是 Python 编码器的可选项，第三方 encoder **不要求**实现；
框架在 B→A 方向会用同一个 encode 程序跑两遍（结构化输入相同），
因此两次输出相同也算通过。若你实现了 Text Mode，可自行加参数。

## 适配器配置文件

复制 `third_party_adapter.example.json`，填好后运行：

```bash
python AIF/conformance/bidirectional.py --adapter path/to/third_party_adapter.json
```

```json
{
  "name": "Go implementation by <name/team>",
  "third_party": true,
  "decode": ["python", "decode_cli.py"],
  "encode": ["python", "encode_cli.py"]
}
```

字段说明：

| 字段 | 含义 |
|---|---|
| `name` | 出现在报告里的实现标识 |
| `third_party` | **必须如实填写**。只有实现者确实未参与原始实现时才写 `true` |
| `decode` | 命令数组。第 1 项是可执行名（如 `python` / `node` / `./aif-decode`），其余是参数 |
| `encode` | 同上 |

相对路径的脚本参数会相对**配置文件所在目录**解析；绝对路径原样使用；
以 `-` 开头的参数原样使用。

## 一个最小 Python 适配器示例

`decode_cli.py`：

```python
import json, sys
from my_aif import decode            # 你的独立实现
try:
    text = sys.stdin.read()
    sys.stdout.write(json.dumps(decode(text), ensure_ascii=False))
except Exception as exc:
    print(exc, file=sys.stderr)
    sys.exit(1)
```

`encode_cli.py`：

```python
import json, sys
from my_aif import encode            # 你的独立实现
try:
    data = json.load(sys.stdin)
    sys.stdout.write(encode(data))
except Exception as exc:
    print(exc, file=sys.stderr)
    sys.exit(1)
```

## 框架会检查什么

- `A→B`：参考实现 A 的 33 个正向向量（Structured + Text Mode 两种 AIF）
  交给你的 `decode`，结果必须结构相等于 `expected_decoded`。
- `B→A`：你的 `encode` 从 `input_json` 产出的 AIF 交给 A 的 decoder，
  必须还原 `input_json`。
- `negative`：9 个非法输入，你的 `encode` 必须全部拒绝；
  N002/N003 因非有限数值不是合法 JSON，框架标 `SKIP`，
  请按向量里的 `construct_hint` 在宿主语言内单独验证。
- **逐字节相等不要求**，只作为信息记录。

通过标准：`A→B 33/33`、`B→A 33/33`、`negative FAIL 0`。
