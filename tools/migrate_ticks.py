"""Double `ticks` and `warmup` values in all integration-mode JSONC cases."""

import glob, re
import json5

for path in sorted(glob.glob("tests/units/**/*.jsonc", recursive=True)):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    data = json5.loads(text)

    changes: dict[str, dict[str, int]] = {}
    for key, case in data.items():
        if not isinstance(case, dict) or case.get("mode") != "integration":
            continue
        d: dict[str, int] = {}
        if "ticks" in case:
            d["ticks"] = case["ticks"] * 2
        if "warmup" in case:
            d["warmup"] = case["warmup"] * 2
        if d:
            changes[key] = d
    if not changes:
        continue

    lines = text.split("\n")
    new_lines: list[str] = []
    i = 0
    current_key: str | None = None
    brace_depth = 0
    while i < len(lines):
        line = lines[i]
        key_match = re.match(r'^(\s*)"([^"]+)"\s*:\s*\{', line)
        if key_match:
            current_key = key_match.group(2)
            brace_depth = 0
        m = re.match(r'^(\s*)"(ticks|warmup)"\s*:\s*(\d+)', line)
        if m and current_key in changes:
            field = m.group(2)
            if field in changes[current_key]:
                indent = m.group(1)
                new_val = changes[current_key][field]
                line = f'{indent}"{field}": {new_val}'
                print(f"{path} :: {current_key} : {field} {m.group(3)} -> {new_val}")
        new_lines.append(line)
        i += 1
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines) + "\n")
