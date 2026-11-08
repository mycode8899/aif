import json
from aif_encoder_v09 import json_to_aif
from aif_decoder_v09 import aif_to_json

def main():
    cases = {
        "flat": {"id":"A1", "name":"Alice", "active":True, "score":9.5},
        "nested": {"id":"A2", "profile":{"city":"Shanghai", "age":30}},
        "scalar_arrays": {"id":"A3", "tags":["AI","technology"], "nums":[1,2,3]},
        "tools_optional": {"agent_id":"agent_001","tools":[
            {"name":"web_search","arguments":{"query":"AI technology","limit":10},
             "result":{"success":True,"count":10}},
            {"name":"calculator","arguments":{"query":"1+1","limit":1}}
        ]},
        "memory": {"agent_id":"agent_002","memory":{"language":"English",
            "facts":["AI","technology","agents"],"importance":0.8}},
        "mixed": {"agent_id":"agent_003","tools":[
            {"name":"web_search","result":{"success":True}},
            {"name":"calculator","arguments":{"query":"2+2"}}
        ],"memory":{"language":"English","facts":["AI","agents"]}}
    }
    passed = 0
    for name, original in cases.items():
        encoded = json_to_aif(original)
        decoded = aif_to_json(encoded)
        ok = decoded == original
        print(f"{name}: {'PASS' if ok else 'FAIL'}")
        if not ok:
            print("Original:", json.dumps(original, ensure_ascii=False))
            print("Decoded:", json.dumps(decoded, ensure_ascii=False))
            print(encoded)
        passed += int(ok)
    print(f"\nRound-trip: {passed}/{len(cases)}")
    if passed != len(cases):
        raise SystemExit(1)

if __name__ == "__main__":
    main()
