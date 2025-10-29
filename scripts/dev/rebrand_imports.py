#!/usr/bin/env python3
"""
Rebrand imports from mft.* to trade_engine.*

Updates all Python files to use the new package name.
"""

import re
from pathlib import Path


# Import mapping rules
IMPORT_MAPPINGS = [
    (r'from mft\.', r'from trade_engine.'),
    (r'import mft\.', r'import trade_engine.'),
    (r'import mft\s', r'import trade_engine '),
    (r'"mft\.', r'"trade_engine.'),
    (r"'mft\.", r"'trade_engine."),
]


def update_file(file_path: Path) -> bool:
    """Update imports in a single file. Returns True if file was modified."""
    try:
        content = file_path.read_text()
        original = content

        for pattern, replacement in IMPORT_MAPPINGS:
            content = re.sub(pattern, replacement, content)

        if content != original:
            file_path.write_text(content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Update all Python files."""
    root = Path(__file__).parent.parent.parent

    directories = [
        root / "src" / "trade_engine",
        root / "scripts",
        root / "tests",
    ]

    updated_files = []

    for directory in directories:
        if not directory.exists():
            continue

        for py_file in directory.rglob("*.py"):
            if py_file.name in ["rebrand_imports.py", "update_imports.py"]:
                continue  # Skip self

            if update_file(py_file):
                updated_files.append(py_file.relative_to(root))

    print(f"✓ Updated {len(updated_files)} files:")
    for f in updated_files:
        print(f"  - {f}")

    return len(updated_files)


if __name__ == "__main__":
    count = main()
    exit(0 if count > 0 else 1)
