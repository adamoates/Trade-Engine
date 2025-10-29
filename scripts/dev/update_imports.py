#!/usr/bin/env python3
"""
Update all imports from app.* to mft.* following new directory structure.

Mapping:
- app.constants → mft.core.constants
- app.engine → mft.core.engine
- app.config → mft.core.config
- app.strategies → mft.services.strategies
- app.adapters → mft.services.adapters
- app.data → mft.services.data
- app.backtest → mft.services.backtest
"""

import re
from pathlib import Path
import sys

# Import mapping rules (order matters - most specific first)
IMPORT_MAPPINGS = [
    (r'from app\.constants(\s+import|\s*$)', r'from mft.core.constants\1'),
    (r'from app\.engine\.([^\s]+)', r'from mft.core.engine.\1'),
    (r'from app\.engine(\s+import|\s*$)', r'from mft.core.engine\1'),
    (r'from app\.config\.([^\s]+)', r'from mft.core.config.\1'),
    (r'from app\.config(\s+import|\s*$)', r'from mft.core.config\1'),
    (r'from app\.strategies\.([^\s]+)', r'from mft.services.strategies.\1'),
    (r'from app\.strategies(\s+import|\s*$)', r'from mft.services.strategies\1'),
    (r'from app\.adapters\.([^\s]+)', r'from mft.services.adapters.\1'),
    (r'from app\.adapters(\s+import|\s*$)', r'from mft.services.adapters\1'),
    (r'from app\.data\.([^\s]+)', r'from mft.services.data.\1'),
    (r'from app\.data(\s+import|\s*$)', r'from mft.services.data\1'),
    (r'from app\.backtest\.([^\s]+)', r'from mft.services.backtest.\1'),
    (r'from app\.backtest(\s+import|\s*$)', r'from mft.services.backtest\1'),
    (r'from app\.([^\s]+)', r'from mft.\1'),  # Catch-all
    (r'import app\.([^\s]+)', r'import mft.\1'),
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
        print(f"Error processing {file_path}: {e}", file=sys.stderr)
        return False


def main():
    """Update all Python files in src/mft/, scripts/, and tests/."""
    root = Path(__file__).parent.parent.parent

    directories = [
        root / "src" / "mft",
        root / "scripts",
        root / "tests",
    ]

    updated_files = []

    for directory in directories:
        if not directory.exists():
            continue

        for py_file in directory.rglob("*.py"):
            if py_file.name == "update_imports.py":
                continue  # Skip self

            if update_file(py_file):
                updated_files.append(py_file.relative_to(root))

    print(f"✓ Updated {len(updated_files)} files:")
    for f in updated_files:
        print(f"  - {f}")


if __name__ == "__main__":
    main()
