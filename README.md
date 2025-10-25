# Pylint_Helper

## Purpose

Parse Pylint-style output and produce a compact per-file summary:

* groups by file
* buckets messages into categories (e.g., **Unused import**, **Trailing whitespace**, **Missing type annotation**, etc.)
* lists line numbers for each category
* collects anything unclassified under **unreconcilable messages**

## Usage

1. Clone repository `git clone https://github.com/gwdio/Pylint_Helper.git`
2. make `input.txt` in the repository root.
3. Put your raw linter output into `input.txt` (or pass a file path).

```bash
# default: reads input.txt
python classify.py

# specify input file
python classify.py path/to/lint_output.txt
```

### Input

Plain text from a linter formatted like:

```
tests/foo.py: 3 errors:
12: Trailing whitespace
18: Unused import os
27: Function is missing a return type annotation
```

### Output (example)

```
tests/foo.py:
  - Unused import (1): 18
  - Trailing whitespace (1): 12
  - Missing type annotation (1): 27

unreconcilable messages:
- tests/bar.py @ 44: Some message we didn't match
```

## Requirements

* Python 3.8+
* No external dependencies.
