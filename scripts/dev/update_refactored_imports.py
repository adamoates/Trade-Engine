#!/usr/bin/env python3
"""
Automated Import Updater for Refactoring

Updates import statements in refactored files to use new module paths.
This script is idempotent - safe to run multiple times.

Usage:
    python scripts/dev/update_refactored_imports.py [--dry-run] [--verbose]
"""

import ast
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import argparse


# Import mapping: old_path -> new_path
IMPORT_MAPPINGS = {
    # Brokers: services/adapters/broker_X -> adapters/brokers/X
    "trade_engine.services.adapters.broker_binance": "trade_engine.adapters.brokers.binance",
    "trade_engine.services.adapters.broker_binance_us": "trade_engine.adapters.brokers.binance_us",
    "trade_engine.services.adapters.broker_kraken": "trade_engine.adapters.brokers.kraken",
    "trade_engine.services.adapters.broker_simulated": "trade_engine.adapters.brokers.simulated",

    # Feeds: services/adapters/feed_X -> adapters/feeds/X
    "trade_engine.services.adapters.feed_binance_l2": "trade_engine.adapters.feeds.binance_l2",

    # Data sources: services/data/source_X -> adapters/data_sources/X
    "trade_engine.services.data.source_binance": "trade_engine.adapters.data_sources.binance",
    "trade_engine.services.data.source_alphavantage": "trade_engine.adapters.data_sources.alphavantage",
    "trade_engine.services.data.source_coingecko": "trade_engine.adapters.data_sources.coingecko",
    "trade_engine.services.data.source_coinmarketcap": "trade_engine.adapters.data_sources.coinmarketcap",
    "trade_engine.services.data.source_yahoo": "trade_engine.adapters.data_sources.yahoo",

    # Strategies: services/strategies -> domain/strategies
    "trade_engine.services.strategies.alpha_bollinger": "trade_engine.domain.strategies.alpha_bollinger",
    "trade_engine.services.strategies.alpha_l2_imbalance": "trade_engine.domain.strategies.alpha_l2_imbalance",
    "trade_engine.services.strategies.alpha_ma_crossover": "trade_engine.domain.strategies.alpha_ma_crossover",
    "trade_engine.services.strategies.alpha_macd": "trade_engine.domain.strategies.alpha_macd",
    "trade_engine.services.strategies.alpha_rsi_divergence": "trade_engine.domain.strategies.alpha_rsi_divergence",
    "trade_engine.services.strategies.market_regime": "trade_engine.domain.strategies.market_regime",
    "trade_engine.services.strategies.signal_confirmation": "trade_engine.domain.strategies.signal_confirmation",
    "trade_engine.services.strategies.types": "trade_engine.domain.strategies.types",
    "trade_engine.services.strategies.asset_class_adapter": "trade_engine.domain.strategies.asset_class_adapter",
    "trade_engine.services.strategies.portfolio_equal_weight": "trade_engine.domain.strategies.portfolio_equal_weight",
    "trade_engine.services.strategies.risk_max_position_size": "trade_engine.domain.strategies.risk_max_position_size",
    "trade_engine.services.strategies.indicator_performance_tracker": "trade_engine.domain.strategies.indicator_performance_tracker",

    # Engine files
    "trade_engine.core.engine.risk_manager": "trade_engine.domain.risk.risk_manager",
    "trade_engine.core.engine.runner_live": "trade_engine.services.trading.engine",
    "trade_engine.core.engine.audit_logger": "trade_engine.services.audit.logger",
    "trade_engine.core.engine.types": "trade_engine.core.types",

    # Data service files (stay in services/data but might be imported)
    "trade_engine.services.data.aggregator": "trade_engine.services.data.aggregator",
    "trade_engine.services.data.signal_normalizer": "trade_engine.services.data.signal_normalizer",
    "trade_engine.services.data.types": "trade_engine.services.data.types",
    "trade_engine.services.data.types_microstructure": "trade_engine.services.data.types_microstructure",
    "trade_engine.services.data.web3_signals": "trade_engine.services.data.web3_signals",
}


def update_imports_in_file(file_path: Path, dry_run: bool = False, verbose: bool = False) -> Tuple[bool, int]:
    """Update imports in a single Python file.

    Args:
        file_path: Path to Python file
        dry_run: If True, don't write changes
        verbose: If True, print detailed info

    Returns:
        (was_modified, num_changes)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
    except Exception as e:
        print(f"❌ Error reading {file_path}: {e}")
        return False, 0

    modified_content = original_content
    changes_made = 0

    # Update imports using regex for each mapping
    for old_import, new_import in IMPORT_MAPPINGS.items():
        # Pattern 1: from X import Y
        pattern1 = rf'from\s+{re.escape(old_import)}\s+import'
        replacement1 = f'from {new_import} import'

        if re.search(pattern1, modified_content):
            modified_content = re.sub(pattern1, replacement1, modified_content)
            changes_made += modified_content.count(replacement1) - original_content.count(replacement1)
            if verbose:
                print(f"  ✓ Updated: from {old_import} import ...")

        # Pattern 2: import X
        pattern2 = rf'import\s+{re.escape(old_import)}\b'
        replacement2 = f'import {new_import}'

        if re.search(pattern2, modified_content):
            modified_content = re.sub(pattern2, replacement2, modified_content)
            changes_made += 1
            if verbose:
                print(f"  ✓ Updated: import {old_import}")

    # Check if file was modified
    if modified_content == original_content:
        return False, 0

    # Write changes if not dry run
    if not dry_run:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(modified_content)
            return True, changes_made
        except Exception as e:
            print(f"❌ Error writing {file_path}: {e}")
            return False, 0

    return True, changes_made


def process_directory(directory: Path, dry_run: bool = False, verbose: bool = False) -> Tuple[int, int]:
    """Process all Python files in a directory recursively.

    Args:
        directory: Directory to process
        dry_run: If True, don't write changes
        verbose: If True, print detailed info

    Returns:
        (files_modified, total_changes)
    """
    files_modified = 0
    total_changes = 0

    for py_file in directory.rglob("*.py"):
        # Skip __pycache__ and test files for now
        if "__pycache__" in str(py_file):
            continue

        was_modified, num_changes = update_imports_in_file(py_file, dry_run, verbose)

        if was_modified:
            files_modified += 1
            total_changes += num_changes
            status = "🔍 Would update" if dry_run else "✅ Updated"
            print(f"{status}: {py_file.relative_to(Path.cwd())} ({num_changes} changes)")
        elif verbose:
            print(f"  ⏭️  Skipped (no changes): {py_file.relative_to(Path.cwd())}")

    return files_modified, total_changes


def verify_syntax(file_path: Path) -> bool:
    """Verify Python file has valid syntax.

    Args:
        file_path: Path to Python file

    Returns:
        True if syntax is valid
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            ast.parse(f.read())
        return True
    except SyntaxError as e:
        print(f"❌ Syntax error in {file_path}: {e}")
        return False
    except Exception as e:
        print(f"❌ Error checking {file_path}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Update imports in refactored code")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    parser.add_argument("--verify", action="store_true", help="Verify syntax after update")
    args = parser.parse_args()

    # Get project root
    project_root = Path(__file__).parent.parent.parent
    src_root = project_root / "src" / "trade_engine"

    if not src_root.exists():
        print(f"❌ Source directory not found: {src_root}")
        sys.exit(1)

    print("=" * 80)
    print("🔧 Trade Engine Import Updater")
    print("=" * 80)

    if args.dry_run:
        print("🔍 DRY RUN MODE - No files will be modified")

    print()

    # Directories to process
    directories = [
        ("Adapters (Brokers)", src_root / "adapters" / "brokers"),
        ("Adapters (Data Sources)", src_root / "adapters" / "data_sources"),
        ("Adapters (Feeds)", src_root / "adapters" / "feeds"),
        ("Domain (Strategies)", src_root / "domain" / "strategies"),
        ("Domain (Risk)", src_root / "domain" / "risk"),
        ("Services (Trading)", src_root / "services" / "trading"),
        ("Services (Audit)", src_root / "services" / "audit"),
        ("Tests (Unit)", project_root / "tests" / "unit"),
        ("Tests (Integration)", project_root / "tests" / "integration"),
    ]

    total_files = 0
    total_changes = 0

    for name, directory in directories:
        if not directory.exists():
            print(f"⏭️  Skipping {name} (not found)")
            continue

        print(f"\n📁 Processing {name}...")
        print("-" * 80)

        files_modified, changes = process_directory(directory, args.dry_run, args.verbose)
        total_files += files_modified
        total_changes += changes

        if files_modified == 0:
            print(f"  ℹ️  No changes needed")

    print("\n" + "=" * 80)
    print("📊 Summary")
    print("=" * 80)
    print(f"Files modified: {total_files}")
    print(f"Total changes: {total_changes}")

    if args.dry_run:
        print("\n💡 Run without --dry-run to apply changes")

    # Verify syntax if requested
    if args.verify and not args.dry_run:
        print("\n🔍 Verifying syntax...")
        all_valid = True
        for name, directory in directories:
            if directory.exists():
                for py_file in directory.rglob("*.py"):
                    if "__pycache__" not in str(py_file):
                        if not verify_syntax(py_file):
                            all_valid = False

        if all_valid:
            print("✅ All files have valid syntax")
        else:
            print("❌ Some files have syntax errors")
            sys.exit(1)

    print("\n✅ Done!")


if __name__ == "__main__":
    main()
