#!/usr/bin/env python3
"""Quick demo with $500 capital."""
import sys
sys.path.insert(0, '/Users/adamoates/Code/Python/MFT')

from tools.demo_full_system_simple import IntegratedSystem, run_demo
import asyncio

# Monkey-patch the capital amount
original_init = IntegratedSystem.__init__

def new_init(self):
    original_init(self)
    self.state.capital = 500.0
    self.state.equity = 500.0

IntegratedSystem.__init__ = new_init

if __name__ == "__main__":
    asyncio.run(run_demo(cycles=50, delay=0.1))
