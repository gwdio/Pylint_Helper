"""
Pylint digestor for when pylint output is extremely long
Classifies most issues via pattern matching and outputs a much more readable summary
"""
import re
import sys
from collections import defaultdict, OrderedDict

# Classification rules
# Each entry is (compiled_regex, canonical_category_name)
RULES = [
    # Whitespace & formatting
    (re.compile(r"\bTrailing whitespace\b", re.I), "Trailing whitespace"),
    (re.compile(r"\bLine too long \(\d+/\d+\)", re.I), "Line too long"),
    (re.compile(r"\bunnecessary pass\b", re.I), "Unnecessary pass statement"),

    # Imports
    (re.compile(r"\bUnused (?:[\w\.]+ )?import(?:ed)?\b", re.I), "Unused import"),

    (re.compile(
        r'\bimport\s+["\'][^"\']+["\']\s+should\s+be\s+placed\s+at\s+the\s+top\s+of\s+the\s+module',
        re.I
    ), "Import order"),

    (re.compile(
        r'\b(?:standard|third\s+party|first\s+party)\s+import'
        r'\s+["\'][^"\']+["\'](?:\s*,\s*["\'][^"\']+["\'])*'
        r'\s+should\s+be\s+placed\s+before\s+'
        r'(?:standard|third\s+party|first\s+party)\s+imports?'
        r'\s+["\'][^"\']+["\'](?:\s*,\s*["\'][^"\']+["\'])*',
        re.I
    ), "Import order"),

    # Docs
    (re.compile(r"Missing (?:function or method|module) docstring", re.I), "Missing docstring"),

    # Typing / annotations
    (re.compile(r"\bFunction is missing a return type annotation\b", re.I), "Missing type annotation"),
    (re.compile(r"\bFunction is missing a type annotation\b", re.I), "Missing type annotation"),
    (re.compile(r"\bCall to untyped function\b", re.I), "Missing type annotation"),
    (re.compile(r"\bIncompatible .* type", re.I), "Type error"),
    (re.compile(r'"None" has no attribute', re.I), "Type error"),
    (re.compile(r"Incompatible return value type", re.I), "Type error"),

    # Unresolved / missing modules
    (re.compile(r"Cannot find implementation or library stub for module named", re.I), "Unresolved module"),

    # Unused vars/args (keep separate from imports)
    (re.compile(r"\bUnused variable\b", re.I), "Unused variable/argument"),
    (re.compile(r"\bUnused argument\b", re.I), "Unused variable/argument"),

    # TODOs (match "TODO", "TODO:", "TODO -", etc.)
    (re.compile(r"\bTODO\b[:\-]?", re.I), "TODO"),


    # Complexity limits (too many X)
    (re.compile(
        r"\bToo many (?:local variables|branches|arguments|instance attributes|public methods|statements)\b",
        re.I
    ), "Complexity limit"),
    
    # Naming style
    (re.compile(
        r'\b(?:constant|variable|function|method|class)\s+name\s+["\']?[^"\']+["\']?\s+'
        r'doesn[’\']t\s+conform\s+to\s+(?:upper_case|\{[^}]+\})\s+naming\s+style',
        re.I
    ), "Naming style"),
    
    # Reassigned Variable
    (re.compile(r'\bredefining name\s+["\']?[^"\']+["\']?\s+from outer scope\s*\(line\s*\d+\)', re.I), "Redefined name"),


    # Style / logic smells (grab-bag)
    (re.compile(r"Using an f-string that does not have any interpolated variables", re.I), "Bad code logic"),
    (re.compile(r"Consider explicitly re-raising", re.I), "Bad code logic"),
    (re.compile(r"\bunnecessary else\b", re.I), "Bad code logic"),
]

# File block header: "path: N errors:"
HEADER_RE = re.compile(r"^\s*(?P<file>[^:\n]+):\s*\d+\s+errors?:\s*$", re.I)
# Entry: "LINE: message"
ENTRY_RE  = re.compile(r"^\s*(?P<line>\d+):\s*(?P<msg>.+?)\s*$")

# Grouping of issue reports
PREFERRED_ORDER = [
        "Unused import",
        "Import order",
        "Trailing whitespace",
        "Line too long",
        "Missing docstring",
        "Missing type annotation",
        "Type error",
        "Unresolved module",
        "Unused variable/argument",
        "Unnecessary pass statement",
        "TODO",
        "Naming style",
        "Complexity limit",
        "Redefined name"
        "Bad code logic",
    ]

def classify(msg: str) -> str | None:
    for rx, cat in RULES:
        if rx.search(msg):
            return cat
    return None

def trim_optional_header(lines: list[str]) -> list[str]:
    """
    Drop any leading header noise (e.g., "Lint Output", "Total errors: 151", blank lines)
    until the first file block header line is found.
    """
    i = 0
    n = len(lines)
    while i < n and not HEADER_RE.match(lines[i]):
        i += 1
    return lines[i:] if i < n else lines  # if no header found, return as-is

def parse_blocks(lines):
    """
    Yields (filepath, [(line:int, message:str), ...]) for each block.
    Accepts indented lines and ignores non-matching fluff.
    """
    i = 0
    n = len(lines)
    while i < n:
        m = HEADER_RE.match(lines[i])
        if not m:
            i += 1
            continue
        filepath = m.group("file").strip()
        i += 1
        entries = []
        while i < n and not HEADER_RE.match(lines[i]):
            e = ENTRY_RE.match(lines[i])
            if e:
                entries.append((int(e.group("line")), e.group("msg").strip()))
            i += 1
        yield filepath, entries

def summarize_entries(entries):
    """Return (cat -> set(lines), unreconcilables[list of (line,msg)])."""
    cat_lines = defaultdict(set)
    unreconcilable = []
    for line, msg in entries:
        cat = classify(msg)
        if cat is None:
            unreconcilable.append((line, msg))
        else:
            cat_lines[cat].add(line)
    return cat_lines, unreconcilable

def order_categories(cat_lines_map: dict[str, set[int]]) -> OrderedDict:
    ordered = OrderedDict()
    for cat in PREFERRED_ORDER:
        if cat in cat_lines_map:
            ordered[cat] = sorted(cat_lines_map[cat])
    # include any categories not in preferred list
    for cat in sorted(cat_lines_map.keys()):
        if cat not in ordered:
            ordered[cat] = sorted(cat_lines_map[cat])
    return ordered


def summarize(entries):
    """
    Returns: (summary_dict, unreconcilables_list)
    summary_dict: {category -> sorted set of line numbers}
    unreconcilables_list: [(line, msg), ...]
    """
    cat_lines = defaultdict(set)
    unreconcilable = []
    for line, msg in entries:
        cat = classify(msg)
        if cat is None:
            unreconcilable.append((line, msg))
        else:
            cat_lines[cat].add(line)
    cat_lines = {k: sorted(v) for k, v in cat_lines.items()}
    ordered = OrderedDict()
    for cat in PREFERRED_ORDER:
        if cat in cat_lines:
            ordered[cat] = cat_lines[cat]
    for cat in sorted(cat_lines.keys()):
        if cat not in ordered:
            ordered[cat] = cat_lines[cat]
    return ordered, unreconcilable

def format_lines(nums):
    return ", ".join(str(x) for x in nums)

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "input.txt"
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = [line.rstrip("\n") for line in f]
    except FileNotFoundError:
        print(f"ERROR: Could not find '{path}'. Put your lint output there or pass a path.")
        sys.exit(1)

    # Trim any optional header first
    raw = trim_optional_header(raw)

    # Aggregate across duplicate file blocks
    per_file_cats: dict[str, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
    per_file_unrec: dict[str, list[tuple[int, str]]] = defaultdict(list)

    any_blocks = False
    for filepath, entries in parse_blocks(raw):
        any_blocks = True
        cat_lines, unrec = summarize_entries(entries)
        for cat, lines in cat_lines.items():
            per_file_cats[filepath][cat].update(lines)        # union by category
        per_file_unrec[filepath].extend(unrec)                # keep evidence

    if not any_blocks:
        print("No file blocks found. Input should contain lines like: 'path/to/file.py: N errors:'")
        sys.exit(0)

    # Print one merged block per file
    outputs = []
    for filepath in sorted(per_file_cats.keys()):
        ordered = order_categories(per_file_cats[filepath])
        out = [f"{filepath}:"]
        for cat, lines in ordered.items():
            out.append(f"  - {cat} ({len(lines)}): {', '.join(map(str, lines))}")
        outputs.append("\n".join(out))

    print("\n\n".join(outputs))

    # Print unreconcilables (grouped by file) if any
    if any(per_file_unrec.values()):
        print("\n\nunreconcilable messages:")
        for filepath in sorted(per_file_unrec.keys()):
            for line, msg in per_file_unrec[filepath]:
                print(f"- {filepath} @ {line}: {msg}")


if __name__ == "__main__":
    main()
