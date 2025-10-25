"""
Pylint digestor for when pyline output is extremely long
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
    (re.compile(r"standard import .* should be placed before third party imports", re.I), "Import order"),

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

    # Style / logic smells (roll into 'Bad code logic' bucket)
    (re.compile(r"Using an f-string that does not have any interpolated variables", re.I), "Bad code logic"),
    (re.compile(r"Consider explicitly re-raising", re.I), "Bad code logic"),
    (re.compile(r"\bunnecessary else\b", re.I), "Bad code logic"),
]

HEADER_RE = re.compile(r"^(?P<file>[^:]+):\s*\d+\s+errors?:\s*$", re.I)
ENTRY_RE  = re.compile(r"^(?P<line>\d+):\s*(?P<msg>.+?)\s*$")

def classify(msg: str) -> str | None:
    for rx, cat in RULES:
        if rx.search(msg):
            return cat
    return None

def parse_blocks(lines):
    """
    Yields (filepath, [(line:int, message:str), ...]) for each block.
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
                entries.append((int(e.group("line")), e.group("msg")))
            i += 1
        yield filepath, entries

def summarize(filepath, entries):
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
    # sort lines for consistent output
    cat_lines = {k: sorted(v) for k, v in cat_lines.items()}
    # stable category ordering (nice to read)
    preferred_order = [
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
        "Bad code logic",
    ]
    ordered = OrderedDict()
    for cat in preferred_order:
        if cat in cat_lines:
            ordered[cat] = cat_lines[cat]
    # any extra categories (if rules extended later)
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

    all_unrec = []  # (filepath, line, msg)
    outputs = []

    for filepath, entries in parse_blocks(raw):
        categories, unrec = summarize(filepath, entries)
        out = [f"{filepath}:"]
        for cat, lines in categories.items():
            out.append(f"  - {cat} ({len(lines)}): {format_lines(lines)}")
        outputs.append("\n".join(out))
        for line, msg in unrec:
            all_unrec.append((filepath, line, msg))

    print("\n\n".join(outputs))

    if all_unrec:
        print("\n\nunreconcilable messages:")
        for fp, line, msg in all_unrec:
            print(f"- {fp} @ {line}: {msg}")

if __name__ == "__main__":
    main()
