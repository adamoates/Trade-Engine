#!/usr/bin/env python3
"""
L2 Data Collection Diagnostic Tool

Analyzes the current state of L2 data collection to determine:
1. Which files exist and their sizes
2. Time ranges covered by each file
3. Whether there are gaps or overlaps
4. If the recording process is still active
5. Overall data quality assessment

Usage:
    python diagnose_l2_collection.py [--data-dir data/l2_snapshots]
"""

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

from loguru import logger


class L2CollectionDiagnostic:
    """Diagnoses L2 data collection status and quality"""

    def __init__(self, data_dir: Path):
        """
        Initialize diagnostic tool.

        Args:
            data_dir: Path to directory containing L2 snapshot files
        """
        self.data_dir = Path(data_dir)
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {data_dir}")

        logger.info(f"Analyzing data directory: {self.data_dir}")

    def find_snapshot_files(self) -> List[Path]:
        """
        Find all L2 snapshot files.

        Returns:
            List of snapshot file paths, sorted by modification time
        """
        files = sorted(
            self.data_dir.glob('l2_*.jsonl'),
            key=lambda p: p.stat().st_mtime
        )
        logger.info(f"Found {len(files)} snapshot files")
        return files

    def analyze_file(self, file_path: Path) -> Dict:
        """
        Analyze a single snapshot file.

        Args:
            file_path: Path to snapshot file

        Returns:
            dict: File analysis results
        """
        logger.info(f"Analyzing: {file_path.name}")

        file_stat = file_path.stat()
        file_info = {
            'filename': file_path.name,
            'size_bytes': file_stat.st_size,
            'size_mb': file_stat.st_size / (1024 * 1024),
            'modified': datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
            'created': datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
            'snapshot_count': 0,
            'first_timestamp': None,
            'last_timestamp': None,
            'duration_hours': None,
            'symbols': set(),
            'has_errors': False
        }

        # Skip empty files
        if file_stat.st_size == 0:
            logger.warning(f"  ⚠️  Empty file")
            return file_info

        # Read and analyze snapshots
        try:
            with open(file_path, 'r') as f:
                first_line = None
                last_line = None
                line_count = 0

                for line in f:
                    line_count += 1

                    if first_line is None:
                        first_line = line
                    last_line = line

                    # Parse snapshot
                    try:
                        snapshot = json.loads(line.strip())
                        file_info['symbols'].add(snapshot.get('symbol', 'unknown'))
                    except json.JSONDecodeError:
                        file_info['has_errors'] = True

                file_info['snapshot_count'] = line_count

                # Parse first and last timestamps
                if first_line:
                    first_snapshot = json.loads(first_line.strip())
                    file_info['first_timestamp'] = first_snapshot.get('timestamp')

                if last_line:
                    last_snapshot = json.loads(last_line.strip())
                    file_info['last_timestamp'] = last_snapshot.get('timestamp')

                # Calculate duration
                if file_info['first_timestamp'] and file_info['last_timestamp']:
                    start = datetime.fromisoformat(file_info['first_timestamp'].replace('Z', '+00:00'))
                    end = datetime.fromisoformat(file_info['last_timestamp'].replace('Z', '+00:00'))
                    duration = end - start
                    file_info['duration_hours'] = duration.total_seconds() / 3600

                # Convert set to list for JSON serialization
                file_info['symbols'] = list(file_info['symbols'])

                logger.info(f"  ✅ {line_count} snapshots | "
                           f"{file_info['duration_hours']:.2f}h duration | "
                           f"{file_info['size_mb']:.2f} MB")

        except Exception as e:
            logger.error(f"  ❌ Error reading file: {e}")
            file_info['has_errors'] = True
            file_info['error_message'] = str(e)

        return file_info

    def check_for_gaps(self, file_analyses: List[Dict]) -> List[Dict]:
        """
        Check for time gaps between files.

        Args:
            file_analyses: List of file analysis results

        Returns:
            List of gaps found
        """
        gaps = []

        for i in range(len(file_analyses) - 1):
            current_file = file_analyses[i]
            next_file = file_analyses[i + 1]

            if not current_file['last_timestamp'] or not next_file['first_timestamp']:
                continue

            current_end = datetime.fromisoformat(current_file['last_timestamp'].replace('Z', '+00:00'))
            next_start = datetime.fromisoformat(next_file['first_timestamp'].replace('Z', '+00:00'))

            gap_duration = next_start - current_end

            if gap_duration.total_seconds() > 10:  # More than 10 seconds
                gaps.append({
                    'after_file': current_file['filename'],
                    'before_file': next_file['filename'],
                    'gap_seconds': gap_duration.total_seconds(),
                    'gap_minutes': gap_duration.total_seconds() / 60
                })

        return gaps

    def check_recording_active(self, latest_file: Dict) -> Dict:
        """
        Check if recording is currently active.

        Args:
            latest_file: Analysis of most recent file

        Returns:
            dict: Active recording status
        """
        status = {
            'is_active': False,
            'last_update_age_seconds': None,
            'conclusion': 'Unknown'
        }

        if not latest_file['last_timestamp']:
            status['conclusion'] = 'No valid timestamps found'
            return status

        # Check how old the last snapshot is
        last_snapshot = datetime.fromisoformat(latest_file['last_timestamp'].replace('Z', '+00:00'))
        now = datetime.utcnow()
        age = now - last_snapshot

        status['last_update_age_seconds'] = age.total_seconds()

        # If last update was within 5 seconds, probably still active
        if age.total_seconds() < 5:
            status['is_active'] = True
            status['conclusion'] = 'Recording appears to be ACTIVE'
        elif age.total_seconds() < 300:  # 5 minutes
            status['is_active'] = False
            status['conclusion'] = 'Recording recently STOPPED or PAUSED'
        else:
            status['is_active'] = False
            status['conclusion'] = 'Recording is NOT ACTIVE (stale data)'

        return status

    def generate_report(self) -> Dict:
        """
        Generate comprehensive diagnostic report.

        Returns:
            dict: Complete diagnostic report
        """
        logger.info("=" * 70)
        logger.info("L2 DATA COLLECTION DIAGNOSTIC REPORT")
        logger.info("=" * 70)

        # Find all files
        files = self.find_snapshot_files()

        if not files:
            logger.warning("⚠️  No snapshot files found!")
            return {'error': 'No snapshot files found', 'files': []}

        # Analyze each file
        file_analyses = []
        for file_path in files:
            analysis = self.analyze_file(file_path)
            file_analyses.append(analysis)

        # Check for gaps
        gaps = self.check_for_gaps(file_analyses)

        # Check if recording is active
        latest_file = file_analyses[-1] if file_analyses else None
        recording_status = self.check_recording_active(latest_file) if latest_file else None

        # Calculate totals
        total_snapshots = sum(f['snapshot_count'] for f in file_analyses)
        total_size_mb = sum(f['size_mb'] for f in file_analyses)
        total_duration_hours = sum(f['duration_hours'] or 0 for f in file_analyses)

        # Generate report
        report = {
            'timestamp': datetime.utcnow().isoformat(),
            'data_directory': str(self.data_dir),
            'summary': {
                'total_files': len(files),
                'total_snapshots': total_snapshots,
                'total_size_mb': total_size_mb,
                'total_duration_hours': total_duration_hours,
                'gaps_found': len(gaps)
            },
            'files': file_analyses,
            'gaps': gaps,
            'recording_status': recording_status,
            'data_quality': self._assess_data_quality(file_analyses, gaps, recording_status)
        }

        # Print summary
        logger.info("")
        logger.info("📊 SUMMARY")
        logger.info(f"  Files: {len(files)}")
        logger.info(f"  Total snapshots: {total_snapshots:,}")
        logger.info(f"  Total size: {total_size_mb:.2f} MB")
        logger.info(f"  Total duration: {total_duration_hours:.2f} hours")
        logger.info(f"  Gaps found: {len(gaps)}")

        if recording_status:
            logger.info("")
            logger.info("🔍 RECORDING STATUS")
            logger.info(f"  {recording_status['conclusion']}")
            if recording_status['last_update_age_seconds'] is not None:
                logger.info(f"  Last update: {recording_status['last_update_age_seconds']:.0f} seconds ago")

        if gaps:
            logger.info("")
            logger.info("⚠️  GAPS DETECTED")
            for gap in gaps:
                logger.warning(f"  Gap of {gap['gap_minutes']:.1f} minutes between files")

        logger.info("")
        logger.info("💡 DATA QUALITY ASSESSMENT")
        logger.info(f"  {report['data_quality']['assessment']}")
        logger.info(f"  {report['data_quality']['recommendation']}")

        logger.info("=" * 70)

        return report

    def _assess_data_quality(self, files: List[Dict], gaps: List[Dict],
                            recording_status: Optional[Dict]) -> Dict:
        """
        Assess overall data quality.

        Args:
            files: File analyses
            gaps: Detected gaps
            recording_status: Recording status

        Returns:
            dict: Quality assessment
        """
        issues = []

        # Check for multiple files (potential restarts)
        if len(files) > 1:
            issues.append(f"Multiple files detected ({len(files)}) - suggests script restarts")

        # Check for gaps
        if gaps:
            issues.append(f"{len(gaps)} time gap(s) detected between files")

        # Check for empty files
        empty_files = [f for f in files if f['snapshot_count'] == 0]
        if empty_files:
            issues.append(f"{len(empty_files)} empty file(s)")

        # Check total duration
        total_duration = sum(f['duration_hours'] or 0 for f in files)
        if total_duration < 24:
            issues.append(f"Total duration ({total_duration:.2f}h) is less than target 24h")

        # Check if recording stopped prematurely
        if recording_status and not recording_status['is_active'] and total_duration < 24:
            issues.append("Recording stopped before reaching 24h target")

        # Determine assessment
        if not issues:
            assessment = "✅ EXCELLENT - Clean 24h continuous recording"
            recommendation = "Data is ready for validation"
        elif len(issues) == 1 and "Multiple files" in issues[0]:
            assessment = "⚠️  ACCEPTABLE - Script restarted but data may be continuous"
            recommendation = "Verify if data is continuous across files or if there are gaps"
        else:
            assessment = "❌ PROBLEMATIC - Data quality issues detected"
            recommendation = "Review issues and consider re-running the recording"

        return {
            'assessment': assessment,
            'recommendation': recommendation,
            'issues': issues
        }


def main():
    """Parse arguments and run diagnostic."""
    parser = argparse.ArgumentParser(
        description='Diagnose L2 data collection status'
    )
    parser.add_argument(
        '--data-dir',
        type=str,
        default='data/l2_snapshots',
        help='Path to L2 snapshots directory (default: data/l2_snapshots)'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Save report to JSON file (optional)'
    )

    args = parser.parse_args()

    try:
        diagnostic = L2CollectionDiagnostic(args.data_dir)
        report = diagnostic.generate_report()

        # Save report if requested
        if args.output:
            output_path = Path(args.output)
            with open(output_path, 'w') as f:
                json.dump(report, indent=2, default=str, fp=f)
            logger.info(f"Report saved to: {output_path}")

    except Exception as e:
        logger.error(f"Diagnostic error: {e}")
        raise


if __name__ == '__main__':
    main()
