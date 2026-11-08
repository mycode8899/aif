"""
Borrow the 8 historical V7 datasets verbatim.

The V7 file imports modules that were never recovered (aif_encoder_v08,
aif_decoder_v08) and tiktoken. We install inert stubs so that ONLY its data
generator functions are loaded. No dataset value is modified.
"""

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import tiktoken  # noqa: F401
except ImportError:
    stub = types.ModuleType("tiktoken")
    stub.get_encoding = lambda name: None
    sys.modules["tiktoken"] = stub

for _name, _funcs in {
    "aif_encoder_v08": ("json_to_aif",),
    "aif_decoder_v08": ("aif_to_json",),
    "aif_encoder_v09": ("json_to_aif",),
    "aif_decoder_v09": ("aif_to_json",),
}.items():
    if _name not in sys.modules:
        _module = types.ModuleType(_name)
        for _fn in _funcs:
            setattr(_module, _fn, lambda *a, **k: None)
        sys.modules[_name] = _module

import test_token_benchmark_v7 as v7  # noqa: E402

DATASETS = [
    ("1. Flat Agent Records", v7.make_flat_agent_records),
    ("2. Nested Agent State", v7.make_nested_agent_state),
    ("3. Tool Calls", v7.make_tool_calls),
    ("4. Multiple Tool Calls", v7.make_multiple_tool_calls),
    ("5. Messages", v7.make_messages),
    ("6. Memory", v7.make_memory),
    ("7. Optional Tool Results", v7.make_optional_tool_results),
    ("8. Mixed Agent State", v7.make_mixed_agent_state),
]

RECORDS_PER_DATASET = v7.RECORDS
