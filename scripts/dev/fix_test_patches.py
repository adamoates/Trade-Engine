#!/usr/bin/env python3
"""Fix @patch() decorators in test files to use new mft.* paths."""

import re
from pathlib import Path

# Patch mapping rules (handle both single and double quotes)
PATCH_MAPPINGS = [
    # Double quotes
    (r'@patch\("app\.data\.', r'@patch("mft.services.data.'),
    (r'@patch\("app\.engine\.', r'@patch("mft.core.engine.'),
    (r'@patch\("app\.strategies\.', r'@patch("mft.services.strategies.'),
    (r'@patch\("app\.adapters\.', r'@patch("mft.services.adapters.'),
    (r'@patch\("app\.', r'@patch("mft.'),
    (r'patch\("app\.data\.', r'patch("mft.services.data.'),
    (r'patch\("app\.engine\.', r'patch("mft.core.engine.'),
    (r'patch\("app\.strategies\.', r'patch("mft.services.strategies.'),
    (r'patch\("app\.adapters\.', r'patch("mft.services.adapters.'),
    (r'patch\("app\.', r'patch("mft.'),
    # Single quotes
    (r"@patch\('app\.data\.", r"@patch('mft.services.data."),
    (r"@patch\('app\.engine\.", r"@patch('mft.core.engine."),
    (r"@patch\('app\.strategies\.", r"@patch('mft.services.strategies."),
    (r"@patch\('app\.adapters\.", r"@patch('mft.services.adapters."),
    (r"@patch\('app\.", r"@patch('mft."),
    (r"patch\('app\.data\.", r"patch('mft.services.data."),
    (r"patch\('app\.engine\.", r"patch('mft.core.engine."),
    (r"patch\('app\.strategies\.", r"patch('mft.services.strategies."),
    (r"patch\('app\.adapters\.", r"patch('mft.services.adapters."),
    (r"patch\('app\.", r"patch('mft."),
]


def update_file(file_path: Path) -> bool:
    """Update patch decorators in a single file."""
    content = file_path.read_text()
    original = content

    for pattern, replacement in PATCH_MAPPINGS:
        content = re.sub(pattern, replacement, content)

    if content != original:
        file_path.write_text(content)
        return True
    return False


def main():
    root = Path(__file__).parent.parent.parent
    tests_dir = root / "tests"

    updated_files = []
    for test_file in tests_dir.rglob("test_*.py"):
        if update_file(test_file):
            updated_files.append(test_file.relative_to(root))

    print(f"✓ Updated {len(updated_files)} test files:")
    for f in updated_files:
        print(f"  - {f}")


if __name__ == "__main__":
    main()
