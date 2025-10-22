#!/usr/bin/env python3
"""
Phase 0 Week 1: L2 Data Quality Validator

Validates recorded L2 order book data to ensure quality and completeness.
Checks for gaps, anomalies, and calculates basic statistics.

Usage:
    python validate_data.py data/l2_snapshots/l2_BTCUSDT_20250122_120000.jsonl

Validation Checks:
    - Data completeness (no large time gaps)
    - Price sanity (no absurd prices)
    - Volume sanity (no zero/negative volumes)
    - Imbalance distribution
    - Snapshot frequency consistency
"""

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict

import pandas as pd
from loguru import logger


class L2DataValidator:
    """Validates L2 order book recording quality"""

    def __init__(self, data_file: Path):
        """
        Initialize validator with data file.

        Args:
            data_file: Path to .jsonl file with L2 snapshots
        """
        self.data_file = Path(data_file)
        self.snapshots: List[Dict] = []
        self.df: pd.DataFrame = None

        if not self.data_file.exists():
            raise FileNotFoundError(f"Data file not found: {data_file}")

        logger.info(f"Validating: {self.data_file}")

    def load_data(self):
        """Load snapshots from JSONL file."""
        logger.info("Loading snapshots...")

        with open(self.data_file, 'r') as f:
            for line in f:
                try:
                    snapshot = json.loads(line.strip())
                    self.snapshots.append(snapshot)
                except json.JSONDecodeError as e:
                    logger.warning(f"Skipping invalid JSON line: {e}")

        logger.info(f"Loaded {len(self.snapshots)} snapshots")

        if len(self.snapshots) == 0:
            raise ValueError("No valid snapshots found in file")

        # Convert to DataFrame for analysis
        self._create_dataframe()

    def _create_dataframe(self):
        """Convert snapshots to pandas DataFrame."""
        records = []

        for snap in self.snapshots:
            record = {
                'timestamp': pd.to_datetime(snap['timestamp']),
                'symbol': snap['symbol'],
                'imbalance_ratio': snap['imbalance']['ratio'],
                'bid_volume': snap['imbalance']['bid_volume'],
                'ask_volume': snap['imbalance']['ask_volume'],
                'bid_levels': len(snap.get('bids', [])),
                'ask_levels': len(snap.get('asks', []))
            }

            # Get best bid/ask prices
            if snap.get('bids'):
                record['best_bid'] = snap['bids'][0][0]
            if snap.get('asks'):
                record['best_ask'] = snap['asks'][0][0]

            records.append(record)

        self.df = pd.DataFrame(records)
        self.df = self.df.sort_values('timestamp').reset_index(drop=True)

    def check_completeness(self) -> Dict:
        """
        Check for time gaps in recording.

        Returns:
            dict: Completeness metrics
        """
        logger.info("Checking completeness...")

        # Calculate time deltas between snapshots
        self.df['time_delta'] = self.df['timestamp'].diff().dt.total_seconds()

        # Expected: ~1 second between snapshots
        expected_interval = 1.0
        tolerance = 2.0  # Allow up to 2 seconds

        gaps = self.df[self.df['time_delta'] > tolerance]

        results = {
            'total_snapshots': len(self.df),
            'start_time': self.df['timestamp'].min(),
            'end_time': self.df['timestamp'].max(),
            'duration_hours': (self.df['timestamp'].max() - self.df['timestamp'].min()).total_seconds() / 3600,
            'expected_snapshots': int((self.df['timestamp'].max() - self.df['timestamp'].min()).total_seconds()),
            'gaps_found': len(gaps),
            'max_gap_seconds': self.df['time_delta'].max() if len(self.df) > 1 else 0,
            'avg_interval': self.df['time_delta'].mean() if len(self.df) > 1 else 0
        }

        logger.info(f"Duration: {results['duration_hours']:.2f} hours")
        logger.info(f"Total snapshots: {results['total_snapshots']}")
        logger.info(f"Expected snapshots: {results['expected_snapshots']}")
        logger.info(f"Gaps > {tolerance}s: {results['gaps_found']}")

        if results['gaps_found'] > 0:
            logger.warning(f"Max gap: {results['max_gap_seconds']:.1f} seconds")

        return results

    def check_price_sanity(self) -> Dict:
        """
        Check for absurd prices that indicate data errors.

        Returns:
            dict: Price sanity metrics
        """
        logger.info("Checking price sanity...")

        results = {
            'min_bid': self.df['best_bid'].min(),
            'max_bid': self.df['best_bid'].max(),
            'min_ask': self.df['best_ask'].min(),
            'max_ask': self.df['best_ask'].max(),
            'avg_spread': (self.df['best_ask'] - self.df['best_bid']).mean(),
            'max_spread': (self.df['best_ask'] - self.df['best_bid']).max(),
            'negative_spreads': len(self.df[self.df['best_ask'] < self.df['best_bid']])
        }

        logger.info(f"Price range: ${results['min_bid']:.2f} - ${results['max_ask']:.2f}")
        logger.info(f"Avg spread: ${results['avg_spread']:.4f}")

        # Check for anomalies
        if results['negative_spreads'] > 0:
            logger.error(f"Found {results['negative_spreads']} snapshots with negative spread!")

        # Check for absurd price jumps (>10% in 1 second)
        self.df['price_change'] = self.df['best_bid'].pct_change().abs()
        large_jumps = self.df[self.df['price_change'] > 0.10]

        if len(large_jumps) > 0:
            logger.warning(f"Found {len(large_jumps)} snapshots with >10% price jump")

        results['large_price_jumps'] = len(large_jumps)

        return results

    def check_volume_sanity(self) -> Dict:
        """
        Check for volume anomalies.

        Returns:
            dict: Volume sanity metrics
        """
        logger.info("Checking volume sanity...")

        results = {
            'zero_bid_volume': len(self.df[self.df['bid_volume'] == 0]),
            'zero_ask_volume': len(self.df[self.df['ask_volume'] == 0]),
            'avg_bid_volume': self.df['bid_volume'].mean(),
            'avg_ask_volume': self.df['ask_volume'].mean(),
            'min_bid_volume': self.df['bid_volume'].min(),
            'min_ask_volume': self.df['ask_volume'].min()
        }

        logger.info(f"Avg bid volume: ${results['avg_bid_volume']:.2f}")
        logger.info(f"Avg ask volume: ${results['avg_ask_volume']:.2f}")

        if results['zero_bid_volume'] > 0:
            logger.warning(f"Found {results['zero_bid_volume']} snapshots with zero bid volume")

        if results['zero_ask_volume'] > 0:
            logger.warning(f"Found {results['zero_ask_volume']} snapshots with zero ask volume")

        return results

    def analyze_imbalance(self) -> Dict:
        """
        Analyze imbalance ratio distribution.

        Returns:
            dict: Imbalance statistics
        """
        logger.info("Analyzing imbalance distribution...")

        # Filter out None values
        valid_ratios = self.df[self.df['imbalance_ratio'].notna()]['imbalance_ratio']

        results = {
            'total_valid': len(valid_ratios),
            'total_invalid': len(self.df) - len(valid_ratios),
            'min_ratio': valid_ratios.min() if len(valid_ratios) > 0 else None,
            'max_ratio': valid_ratios.max() if len(valid_ratios) > 0 else None,
            'mean_ratio': valid_ratios.mean() if len(valid_ratios) > 0 else None,
            'median_ratio': valid_ratios.median() if len(valid_ratios) > 0 else None,

            # Buy/Sell signal counts (based on strategy thresholds)
            'buy_signals': len(valid_ratios[valid_ratios > 3.0]),
            'sell_signals': len(valid_ratios[valid_ratios < 0.33]),
            'neutral': len(valid_ratios[(valid_ratios >= 0.33) & (valid_ratios <= 3.0)])
        }

        logger.info(f"Valid ratios: {results['total_valid']}/{len(self.df)}")
        logger.info(f"Mean ratio: {results['mean_ratio']:.3f}")
        logger.info(f"Buy signals (>3.0x): {results['buy_signals']}")
        logger.info(f"Sell signals (<0.33x): {results['sell_signals']}")
        logger.info(f"Neutral: {results['neutral']}")

        # Calculate signal frequency
        if results['total_valid'] > 0:
            results['buy_signal_pct'] = (results['buy_signals'] / results['total_valid']) * 100
            results['sell_signal_pct'] = (results['sell_signals'] / results['total_valid']) * 100
            logger.info(f"Buy signal frequency: {results['buy_signal_pct']:.2f}%")
            logger.info(f"Sell signal frequency: {results['sell_signal_pct']:.2f}%")

        return results

    def generate_report(self) -> Dict:
        """
        Generate comprehensive validation report.

        Returns:
            dict: Complete validation results
        """
        logger.info("=" * 60)
        logger.info("L2 DATA VALIDATION REPORT")
        logger.info("=" * 60)

        report = {
            'file': str(self.data_file),
            'file_size_mb': self.data_file.stat().st_size / 1024 / 1024,
            'completeness': self.check_completeness(),
            'price_sanity': self.check_price_sanity(),
            'volume_sanity': self.check_volume_sanity(),
            'imbalance_analysis': self.analyze_imbalance()
        }

        # Overall quality score
        quality_score = self._calculate_quality_score(report)
        report['quality_score'] = quality_score

        logger.info("=" * 60)
        logger.info(f"OVERALL QUALITY SCORE: {quality_score}/100")
        logger.info("=" * 60)

        if quality_score >= 90:
            logger.info("✅ Data quality: EXCELLENT - Ready for analysis")
        elif quality_score >= 70:
            logger.warning("⚠️  Data quality: GOOD - Minor issues detected")
        else:
            logger.error("❌ Data quality: POOR - Major issues found")

        return report

    def _calculate_quality_score(self, report: Dict) -> int:
        """
        Calculate overall quality score (0-100).

        Args:
            report: Validation report

        Returns:
            int: Quality score
        """
        score = 100

        # Deduct for completeness issues
        completeness = report['completeness']
        coverage = completeness['total_snapshots'] / max(completeness['expected_snapshots'], 1)
        if coverage < 0.95:
            score -= 20
        elif coverage < 0.98:
            score -= 10

        # Deduct for gaps
        if completeness['gaps_found'] > 10:
            score -= 15
        elif completeness['gaps_found'] > 5:
            score -= 5

        # Deduct for price issues
        price = report['price_sanity']
        if price['negative_spreads'] > 0:
            score -= 30
        if price['large_price_jumps'] > 10:
            score -= 10

        # Deduct for volume issues
        volume = report['volume_sanity']
        zero_volume_pct = (volume['zero_bid_volume'] + volume['zero_ask_volume']) / (completeness['total_snapshots'] * 2) * 100
        if zero_volume_pct > 5:
            score -= 20
        elif zero_volume_pct > 1:
            score -= 10

        # Deduct for invalid imbalance ratios
        imbalance = report['imbalance_analysis']
        invalid_pct = (imbalance['total_invalid'] / completeness['total_snapshots']) * 100
        if invalid_pct > 10:
            score -= 15
        elif invalid_pct > 5:
            score -= 5

        return max(0, score)

    def validate(self) -> Dict:
        """
        Run full validation suite.

        Returns:
            dict: Validation report
        """
        self.load_data()
        report = self.generate_report()

        # Save report to JSON
        report_file = self.data_file.parent / f"{self.data_file.stem}_validation.json"
        with open(report_file, 'w') as f:
            f.write(json.dumps(report, indent=2, default=str))

        logger.info(f"Validation report saved: {report_file}")

        return report


def main():
    """Parse arguments and validate data."""
    parser = argparse.ArgumentParser(
        description='Validate L2 order book data quality'
    )
    parser.add_argument(
        'data_file',
        type=str,
        help='Path to .jsonl data file'
    )

    args = parser.parse_args()

    try:
        validator = L2DataValidator(args.data_file)
        report = validator.validate()

        # Exit with error code if quality is poor
        if report['quality_score'] < 70:
            logger.error("Validation failed - quality score too low")
            exit(1)
        else:
            logger.info("Validation passed ✅")
            exit(0)

    except Exception as e:
        logger.error(f"Validation error: {e}")
        raise


if __name__ == '__main__':
    main()
