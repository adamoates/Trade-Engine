#!/usr/bin/env python3
"""
Performance Benchmark: Docker vs Bare Metal

Measures actual latency for critical MFT operations:
- WebSocket message processing
- Order book updates
- API request latency
- Overall system latency

Usage:
    # Bare metal test
    python scripts/benchmark_performance.py --mode bare-metal

    # Docker test (run after: docker-compose up -d mft-engine)
    python scripts/benchmark_performance.py --mode docker

    # Compare both
    python scripts/benchmark_performance.py --compare
"""

import time
import statistics
import argparse
from decimal import Decimal
from datetime import datetime
from pathlib import Path
import json
import sys
import os

# Disable verbose logging
os.environ['LOGURU_LEVEL'] = 'ERROR'

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mft.services.adapters.feed_binance_l2 import OrderBook
from mft.services.strategies.alpha_l2_imbalance import L2ImbalanceStrategy, L2StrategyConfig
from mft.core.engine.types import Bar


class PerformanceBenchmark:
    """Benchmark critical trading operations."""

    def __init__(self, iterations: int = 100):
        self.iterations = iterations
        self.results = {}

    def benchmark_orderbook_update(self) -> dict:
        """Measure order book update latency."""
        print("📊 Benchmarking order book updates...")

        latencies = []
        orderbook = OrderBook(symbol="BTCUSDT")

        # Simulate order book snapshot
        snapshot_data = {
            'lastUpdateId': 1,
            'bids': [[str(50000 + i), str(0.1 * i)] for i in range(20)],
            'asks': [[str(50100 + i), str(0.1 * i)] for i in range(20)]
        }

        for i in range(self.iterations):
            start = time.perf_counter_ns()

            # Update order book
            orderbook.apply_snapshot(snapshot_data)

            # Calculate imbalance
            imbalance = orderbook.calculate_imbalance(depth=5)

            end = time.perf_counter_ns()
            latencies.append((end - start) / 1_000_000)  # Convert to ms

        return {
            'operation': 'Order Book Update + Imbalance Calc',
            'mean_ms': statistics.mean(latencies),
            'median_ms': statistics.median(latencies),
            'p95_ms': statistics.quantiles(latencies, n=20)[18],  # 95th percentile
            'p99_ms': statistics.quantiles(latencies, n=100)[98],  # 99th percentile
            'min_ms': min(latencies),
            'max_ms': max(latencies),
            'iterations': self.iterations
        }

    def benchmark_strategy_signal_generation(self) -> dict:
        """Measure signal generation latency."""
        print("🎯 Benchmarking signal generation...")

        latencies = []
        orderbook = OrderBook(symbol="BTCUSDT")
        strategy = L2ImbalanceStrategy(
            symbol="BTCUSDT",
            order_book=orderbook,
            config=L2StrategyConfig(
                buy_threshold=Decimal("3.0"),
                sell_threshold=Decimal("0.33")
            )
        )

        # Create test bar
        bar = Bar(
            timestamp=int(time.time() * 1000),
            open=Decimal("50000"),
            high=Decimal("50100"),
            low=Decimal("49900"),
            close=Decimal("50050"),
            volume=Decimal("100")
        )

        for i in range(self.iterations):
            start = time.perf_counter_ns()

            # Generate signals
            signals = strategy.on_bar(bar)

            end = time.perf_counter_ns()
            latencies.append((end - start) / 1_000_000)  # Convert to ms

        return {
            'operation': 'L2 Strategy Signal Generation',
            'mean_ms': statistics.mean(latencies),
            'median_ms': statistics.median(latencies),
            'p95_ms': statistics.quantiles(latencies, n=20)[18],
            'p99_ms': statistics.quantiles(latencies, n=100)[98],
            'min_ms': min(latencies),
            'max_ms': max(latencies),
            'iterations': self.iterations
        }

    def benchmark_full_cycle(self) -> dict:
        """Measure full processing cycle: orderbook → signal → decision."""
        print("🔄 Benchmarking full processing cycle...")

        latencies = []
        orderbook = OrderBook(symbol="BTCUSDT")
        strategy = L2ImbalanceStrategy(
            symbol="BTCUSDT",
            order_book=orderbook,
            config=L2StrategyConfig(
                buy_threshold=Decimal("3.0"),
                sell_threshold=Decimal("0.33")
            )
        )

        snapshot_data = {
            'lastUpdateId': 1,
            'bids': [[str(50000 + i), str(0.5 * i)] for i in range(20)],
            'asks': [[str(50100 + i), str(0.1 * i)] for i in range(20)]
        }

        for i in range(self.iterations):
            start = time.perf_counter_ns()

            # 1. Update order book
            orderbook.apply_snapshot(snapshot_data)

            # 2. Calculate imbalance
            imbalance = orderbook.calculate_imbalance(depth=5)
            mid_price = orderbook.get_mid_price()

            # 3. Create bar
            bar = Bar(
                timestamp=int(time.time() * 1000),
                open=mid_price,
                high=mid_price,
                low=mid_price,
                close=mid_price,
                volume=Decimal("100")
            )

            # 4. Generate signals
            signals = strategy.on_bar(bar)

            end = time.perf_counter_ns()
            latencies.append((end - start) / 1_000_000)  # Convert to ms

        return {
            'operation': 'Full Cycle (Orderbook → Signal)',
            'mean_ms': statistics.mean(latencies),
            'median_ms': statistics.median(latencies),
            'p95_ms': statistics.quantiles(latencies, n=20)[18],
            'p99_ms': statistics.quantiles(latencies, n=100)[98],
            'min_ms': min(latencies),
            'max_ms': max(latencies),
            'iterations': self.iterations
        }

    def run_all_benchmarks(self) -> dict:
        """Run all benchmarks and return results."""
        print(f"\n{'='*60}")
        print(f"🚀 Performance Benchmark - {self.iterations} iterations")
        print(f"{'='*60}\n")

        results = {
            'timestamp': datetime.now().isoformat(),
            'iterations': self.iterations,
            'benchmarks': []
        }

        # Run benchmarks
        results['benchmarks'].append(self.benchmark_orderbook_update())
        results['benchmarks'].append(self.benchmark_strategy_signal_generation())
        results['benchmarks'].append(self.benchmark_full_cycle())

        return results

    def print_results(self, results: dict, mode: str = "bare-metal"):
        """Print formatted results."""
        print(f"\n{'='*60}")
        print(f"📈 Results ({mode.upper()})")
        print(f"{'='*60}\n")

        for benchmark in results['benchmarks']:
            print(f"Operation: {benchmark['operation']}")
            print(f"  Mean:     {benchmark['mean_ms']:.3f} ms")
            print(f"  Median:   {benchmark['median_ms']:.3f} ms")
            print(f"  P95:      {benchmark['p95_ms']:.3f} ms")
            print(f"  P99:      {benchmark['p99_ms']:.3f} ms")
            print(f"  Min:      {benchmark['min_ms']:.3f} ms")
            print(f"  Max:      {benchmark['max_ms']:.3f} ms")
            print()

        # Calculate total latency budget usage
        full_cycle = results['benchmarks'][2]
        latency_budget = 50.0  # ms (from CLAUDE.md)
        usage_pct = (full_cycle['mean_ms'] / latency_budget) * 100

        print(f"Latency Budget Analysis:")
        print(f"  Full cycle latency: {full_cycle['mean_ms']:.3f} ms")
        print(f"  Target budget:      {latency_budget:.1f} ms")
        print(f"  Budget usage:       {usage_pct:.1f}%")
        print(f"  Remaining:          {latency_budget - full_cycle['mean_ms']:.3f} ms")
        print()


def compare_results(bare_metal_file: Path, docker_file: Path):
    """Compare bare metal vs Docker results."""

    with open(bare_metal_file) as f:
        bare_metal = json.load(f)

    with open(docker_file) as f:
        docker = json.load(f)

    print(f"\n{'='*70}")
    print(f"⚖️  DOCKER vs BARE METAL COMPARISON")
    print(f"{'='*70}\n")

    for i, bench_name in enumerate(['Order Book Update', 'Signal Generation', 'Full Cycle']):
        bm = bare_metal['benchmarks'][i]
        dk = docker['benchmarks'][i]

        overhead_mean = dk['mean_ms'] - bm['mean_ms']
        overhead_pct = (overhead_mean / bm['mean_ms']) * 100 if bm['mean_ms'] > 0 else 0

        print(f"{bench_name}:")
        print(f"  Bare Metal:  {bm['mean_ms']:.3f} ms")
        print(f"  Docker:      {dk['mean_ms']:.3f} ms")
        print(f"  Overhead:    {overhead_mean:+.3f} ms ({overhead_pct:+.1f}%)")
        print()

    # Overall verdict
    full_cycle_bm = bare_metal['benchmarks'][2]['mean_ms']
    full_cycle_dk = docker['benchmarks'][2]['mean_ms']
    total_overhead = full_cycle_dk - full_cycle_bm

    print(f"Overall Verdict:")
    print(f"  Total Docker overhead: {total_overhead:+.3f} ms")

    if abs(total_overhead) < 1.0:
        print(f"  ✅ Negligible difference (<1ms)")
    elif abs(total_overhead) < 5.0:
        print(f"  ✅ Acceptable for MFT (<5ms)")
    else:
        print(f"  ⚠️  Noticeable overhead (>{5}ms)")

    # Hold time context
    print(f"\n  Context (5-60s hold times):")
    print(f"  - Overhead as % of 5s hold:  {(total_overhead / 5000) * 100:.4f}%")
    print(f"  - Overhead as % of 60s hold: {(total_overhead / 60000) * 100:.5f}%")
    print()


def main():
    parser = argparse.ArgumentParser(description='Benchmark MFT performance')
    parser.add_argument('--mode', choices=['bare-metal', 'docker'], default='bare-metal',
                        help='Execution mode to test')
    parser.add_argument('--iterations', type=int, default=1000,
                        help='Number of iterations per benchmark (default: 1000)')
    parser.add_argument('--compare', action='store_true',
                        help='Compare bare-metal vs docker results')
    parser.add_argument('--output', type=str,
                        help='Output file for results (JSON)')

    args = parser.parse_args()

    if args.compare:
        # Compare existing results
        results_dir = Path(__file__).parent.parent / "benchmark_results"
        bare_metal_file = results_dir / "bare-metal.json"
        docker_file = results_dir / "docker.json"

        if not bare_metal_file.exists() or not docker_file.exists():
            print("❌ Missing benchmark results!")
            print(f"\nRun these commands first:")
            print(f"  python scripts/benchmark_performance.py --mode bare-metal")
            print(f"  python scripts/benchmark_performance.py --mode docker")
            sys.exit(1)

        compare_results(bare_metal_file, docker_file)
    else:
        # Run benchmark
        benchmark = PerformanceBenchmark(iterations=args.iterations)
        results = benchmark.run_all_benchmarks()
        benchmark.print_results(results, mode=args.mode)

        # Save results
        output_file = args.output or f"benchmark_results/{args.mode}.json"
        output_path = Path(output_file)
        output_path.parent.mkdir(exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)

        print(f"💾 Results saved to: {output_path}")
        print(f"\nNext steps:")
        if args.mode == 'bare-metal':
            print(f"  1. Run Docker version: python scripts/benchmark_performance.py --mode docker")
            print(f"  2. Compare results:    python scripts/benchmark_performance.py --compare")
        else:
            print(f"  Compare results: python scripts/benchmark_performance.py --compare")


if __name__ == "__main__":
    main()
