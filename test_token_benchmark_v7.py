import json
import copy
import tiktoken

from aif_encoder_v08 import json_to_aif as json_to_aif_v08
from aif_decoder_v08 import aif_to_json as aif08_to_json

from aif_encoder_v09 import json_to_aif as json_to_aif_v09
from aif_decoder_v09 import aif_to_json as aif09_to_json

try:
    from aif_encoder_v08_compact import json_to_aif as json_to_aif_compact
except ImportError:
    json_to_aif_compact = None


# ============================================================
# AIF TOKEN BENCHMARK V7
# ============================================================

RECORDS = 1000
TOKENIZER_NAME = "cl100k_base"

enc = tiktoken.get_encoding(TOKENIZER_NAME)


def token_count(text):
    return len(enc.encode(text))


def json_text(records):
    return json.dumps(
        records,
        ensure_ascii=False,
        separators=(",", ":")
    )


def normalize(value):
    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False
        )
    )


def benchmark_dataset(name, records):
    print()
    print("=" * 70)
    print(name)
    print("=" * 70)

    json_string = json_text(records)
    json_tokens = token_count(json_string)

    print(f"Records:              {len(records):,}")
    print(f"JSON tokens:          {json_tokens:,}")

    # --------------------------------------------------------
    # AIF 0.8
    # --------------------------------------------------------

    aif08 = None
    aif08_roundtrip = False

    try:
        aif08 = json_to_aif_v08(records)
        aif08_tokens = token_count(aif08)

        try:
            decoded08 = aif08_to_json(aif08)
            aif08_roundtrip = (
                normalize(decoded08)
                == normalize(records)
            )
        except Exception as e:
            print(
                f"AIF 0.8 decode error: "
                f"{repr(e)}"
            )

        reduction08 = (
            (json_tokens - aif08_tokens)
            / json_tokens
            * 100
        )

        print(
            f"AIF 0.8 tokens:       "
            f"{aif08_tokens:,}"
        )

        print(
            f"AIF 0.8 Reduction:    "
            f"{reduction08:.2f}%"
        )

    except Exception as e:
        aif08_tokens = None

        print(
            f"AIF 0.8 unsupported/error: "
            f"{repr(e)}"
        )

        print("AIF 0.8 tokens:       N/A")
        print("AIF 0.8 Reduction:    N/A")

    # --------------------------------------------------------
    # AIF 0.9
    # --------------------------------------------------------

    aif09 = None
    aif09_roundtrip = False

    try:
        aif09 = json_to_aif_v09(records)
        aif09_tokens = token_count(aif09)

        try:
            decoded09 = aif09_to_json(aif09)

            aif09_roundtrip = (
                normalize(decoded09)
                == normalize(records)
            )

        except Exception as e:
            print(
                f"AIF 0.9 decode error: "
                f"{repr(e)}"
            )

        reduction09 = (
            (json_tokens - aif09_tokens)
            / json_tokens
            * 100
        )

        print(
            f"AIF 0.9 tokens:       "
            f"{aif09_tokens:,}"
        )

        print(
            f"AIF 0.9 Reduction:    "
            f"{reduction09:.2f}%"
        )

    except Exception as e:
        aif09_tokens = None

        print(
            f"AIF 0.9 unsupported/error: "
            f"{repr(e)}"
        )

        print("AIF 0.9 tokens:       N/A")
        print("AIF 0.9 Reduction:    N/A")

    # --------------------------------------------------------
    # Compact
    #
    # Compact is kept as a secondary comparison.
    # It is not assumed to support every AIF/0.9 structure.
    # --------------------------------------------------------

    compact = None
    compact_roundtrip = False

    if json_to_aif_compact is not None:

        try:
            compact = json_to_aif_compact(records)
            compact_tokens = token_count(compact)

            reduction_compact = (
                (json_tokens - compact_tokens)
                / json_tokens
                * 100
            )

            print(
                f"Compact tokens:       "
                f"{compact_tokens:,}"
            )

            print(
                f"Compact Reduction:    "
                f"{reduction_compact:.2f}%"
            )

        except Exception as e:

            compact_tokens = None

            print(
                f"Compact unsupported/error: "
                f"{repr(e)}"
            )

            print("Compact tokens:       N/A")
            print("Compact Reduction:    N/A")

    else:

        compact_tokens = None

        print("Compact tokens:       N/A")
        print("Compact Reduction:    N/A")

    # --------------------------------------------------------
    # Round-trip status
    # --------------------------------------------------------

    print()
    print(
        f"AIF 0.8 Round-trip:   "
        f"{'PASS' if aif08_roundtrip else 'FAIL'}"
    )

    print(
        f"AIF 0.9 Round-trip:   "
        f"{'PASS' if aif09_roundtrip else 'FAIL'}"
    )

    if compact is not None:
        print(
            f"Compact Round-trip:   "
            f"{'N/A' if aif09 is None else 'CHECK'}"
        )

    return {
        "name": name,
        "records": len(records),
        "json_tokens": json_tokens,
        "aif08_tokens": aif08_tokens,
        "aif09_tokens": aif09_tokens,
        "compact_tokens": compact_tokens,
        "aif08_roundtrip": aif08_roundtrip,
        "aif09_roundtrip": aif09_roundtrip,
    }


# ============================================================
# DATASET 1
# Flat Agent Records
# ============================================================

def make_flat_agent_records(n):
    return [
        {
            "agent_id": f"agent_{i:06d}",
            "status": "active",
            "model": "gpt",
            "version": "5",
            "priority": i % 5,
            "temperature": 0.7,
            "region": "global",
        }
        for i in range(n)
    ]


# ============================================================
# DATASET 2
# Nested Agent State
# ============================================================

def make_nested_agent_state(n):
    return [
        {
            "agent_id": f"agent_{i:06d}",
            "state": {
                "session": {
                    "id": f"sess_{i:06d}",
                    "status": "active",
                },
                "user": {
                    "name": "User",
                    "locale": "en-US",
                },
                "runtime": {
                    "turn": i % 20,
                    "temperature": 0.7,
                },
            },
        }
        for i in range(n)
    ]


# ============================================================
# DATASET 3
# Tool Calls
# ============================================================

def make_tool_calls(n):
    return [
        {
            "agent_id": f"agent_{i:06d}",
            "tool": {
                "name": "web_search",
                "arguments": {
                    "query": "AI technology",
                    "limit": 10,
                },
                "result": {
                    "success": True,
                    "count": 10,
                },
            },
        }
        for i in range(n)
    ]


# ============================================================
# DATASET 4
# Multiple Tool Calls
# ============================================================

def make_multiple_tool_calls(n):
    return [
        {
            "agent_id": f"agent_{i:06d}",
            "tools": [
                {
                    "name": "web_search",
                    "arguments": {
                        "query": "AI technology",
                        "limit": 10,
                    },
                    "result": {
                        "success": True,
                        "count": 10,
                    },
                },
                {
                    "name": "calculator",
                    "arguments": {
                        "query": "1+1",
                        "limit": 1,
                    },
                },
            ],
        }
        for i in range(n)
    ]


# ============================================================
# DATASET 5
# Messages
# ============================================================

def make_messages(n):
    return [
        {
            "agent_id": f"agent_{i:06d}",
            "messages": [
                {
                    "role": "user",
                    "content": "Find the latest AI news.",
                },
                {
                    "role": "assistant",
                    "content": "I will search for current information.",
                },
            ],
        }
        for i in range(n)
    ]


# ============================================================
# DATASET 6
# Memory
# ============================================================

def make_memory(n):
    return [
        {
            "agent_id": f"agent_{i:06d}",
            "memory": {
                "preferences": {
                    "language": "English",
                    "style": "concise",
                },
                "facts": [
                    "AI",
                    "technology",
                    "agents",
                ],
                "importance": 0.8,
            },
        }
        for i in range(n)
    ]


# ============================================================
# DATASET 7
# Optional Tool Results
# ============================================================

def make_optional_tool_results(n):
    records = []

    for i in range(n):

        tool = {
            "name": "web_search",
            "arguments": {
                "query": "AI technology",
                "limit": 10,
            },
        }

        if i % 2 == 0:
            tool["result"] = {
                "success": True,
                "count": 10,
            }

        records.append(
            {
                "agent_id": f"agent_{i:06d}",
                "tool": tool,
            }
        )

    return records


# ============================================================
# DATASET 8
# Realistic Mixed Agent State
# ============================================================

def make_mixed_agent_state(n):
    records = []

    for i in range(n):

        record = {
            "agent_id": f"agent_{i:06d}",

            "session": {
                "id": f"sess_{i:06d}",
                "status": "active",
            },

            "messages": [
                {
                    "role": "user",
                    "content": "Search AI news",
                },
                {
                    "role": "assistant",
                    "content": "Searching now",
                },
            ],

            "tools": [
                {
                    "name": "web_search",
                    "arguments": {
                        "query": "AI technology",
                        "limit": 10,
                    },
                    "result": {
                        "success": True,
                        "count": 10,
                    },
                },
                {
                    "name": "calculator",
                    "arguments": {
                        "query": "1+1",
                        "limit": 1,
                    },
                },
            ],

            "memory": {
                "language": "English",
                "importance": 0.8,
            },
        }

        records.append(record)

    return records


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("AIF TOKEN BENCHMARK V7")
    print("=" * 70)
    print(
        f"Tokenizer: {TOKENIZER_NAME}"
    )
    print(
        f"Records per dataset: {RECORDS:,}"
    )
    print(
        "JSON: standard json.dumps"
    )
    print("=" * 70)

    datasets = [
        (
            "1. Flat Agent Records",
            make_flat_agent_records(RECORDS),
        ),

        (
            "2. Nested Agent State",
            make_nested_agent_state(RECORDS),
        ),

        (
            "3. Tool Calls",
            make_tool_calls(RECORDS),
        ),

        (
            "4. Multiple Tool Calls",
            make_multiple_tool_calls(RECORDS),
        ),

        (
            "5. Messages",
            make_messages(RECORDS),
        ),

        (
            "6. Memory",
            make_memory(RECORDS),
        ),

        (
            "7. Optional Tool Results",
            make_optional_tool_results(RECORDS),
        ),

        (
            "8. Mixed Agent State",
            make_mixed_agent_state(RECORDS),
        ),
    ]

    results = []

    for name, records in datasets:

        result = benchmark_dataset(
            name,
            records
        )

        results.append(result)

    print()
    print("=" * 70)
    print("AIF TOKEN BENCHMARK V7 COMPLETE")
    print("=" * 70)

    print()
    print("SUMMARY")
    print("-" * 70)

    for result in results:

        json_tokens = result["json_tokens"]
        aif09_tokens = result["aif09_tokens"]

        if aif09_tokens is not None:

            reduction = (
                (json_tokens - aif09_tokens)
                / json_tokens
                * 100
            )

            reduction_text = (
                f"{reduction:7.2f}%"
            )

        else:
            reduction_text = "    N/A"

        print(
            f'{result["name"]:<32} '
            f'JSON={json_tokens:>9,} '
            f'AIF0.9={str(aif09_tokens or "N/A"):>9} '
            f'Reduction={reduction_text}'
        )


if __name__ == "__main__":
    main()
