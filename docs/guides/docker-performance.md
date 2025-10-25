# Docker Performance Considerations for MFT Trading Bot

**Quick Answer**: Docker is **optional** for this project. It adds 1-5ms latency which is negligible for medium-frequency trading (5-60 second holds) but can be avoided if needed.

## Performance Impact Summary

| Metric | Bare Metal | Docker (bridge) | Docker (host network) |
|--------|------------|-----------------|----------------------|
| Network Latency | 0ms | +1-5ms | 0ms |
| CPU Overhead | 0% | 2-5% | 2-5% |
| Memory Overhead | 0% | ~0% | ~0% |
| Disk I/O | Baseline | ~Same | ~Same |

## When to Use Each Approach

### 1. Bare Metal (Maximum Performance)
**Use when**:
- Latency is absolutely critical
- Running locally for development
- VPS with full control

**How to run**:
```bash
source .venv/bin/activate
python -m mft.core.engine.runner_live --config src/mft/core/config/paper.yaml
```

**Pros**: Zero container overhead
**Cons**: Environment inconsistency, harder to deploy

---

### 2. Docker with Bridge Networking (Isolation + Portability)
**Use when**:
- Deploying to VPS/cloud
- Need multiple services (DB, API, Redis)
- Want easy rollback and version control

**How to run**:
```bash
docker-compose up mft-engine
```

**Pros**: Isolated, portable, reproducible
**Cons**: +1-5ms network latency

---

### 3. Docker with Host Networking (Best of Both)
**Use when**:
- Need Docker benefits but minimal overhead
- Running on Linux (macOS/Windows not supported)
- Production trading on dedicated VPS

**How to run**:
```yaml
# docker-compose.yml
services:
  mft-engine:
    network_mode: "host"  # Bypass Docker network stack
```

**Pros**: Docker isolation + near-zero network overhead
**Cons**: Linux only, loses some isolation

---

## Latency Budget Analysis

For MFT Bot (from CLAUDE.md):

```
Target Latency Budget:
├── Message processing: <5ms
├── Order placement: <20ms
├── Total latency: <50ms sustained
└── Hold time: 5,000-60,000ms

Docker Impact:
├── Network overhead: 1-5ms (10% of budget, 0.01% of hold time)
├── CPU overhead: 2-5% (negligible for I/O-bound trading)
└── Verdict: NEGLIGIBLE for MFT strategy
```

## Real-World Bottlenecks (Bigger Than Docker)

What actually matters for latency:

| Bottleneck | Latency Impact |
|------------|----------------|
| Exchange API latency | 20-100ms |
| WebSocket processing | 10-50ms |
| Order book parsing | 1-10ms |
| Internet connection | 5-50ms |
| **Docker overhead** | **1-5ms** ⬅️ Smallest factor |

## Benchmarking Your Setup

Test actual performance with both approaches:

```bash
# Test 1: Bare metal
time python -m mft.core.engine.runner_live --test-latency

# Test 2: Docker
time docker-compose run mft-engine python -m mft.core.engine.runner_live --test-latency

# Compare results
```

## Recommendations by Phase

### Phase 0-2: Development
**Use bare metal** - Faster iteration, easier debugging

### Phase 3-4: Paper Trading
**Use Docker** - Test production environment early

### Phase 5: Live Trading (Micro-Capital)
**Use Docker with host networking** - Production-like with minimal overhead

### Phase 6-7: Full Production
**Use bare metal on dedicated VPS** - Maximum performance, fully optimized

## When Docker Actually Hurts

**Avoid Docker if**:
- Migrating to HFT (microsecond trading)
- Latency arbitrage strategy
- Co-located with exchange servers
- <100ms target latency

**For MFT with 5-60s holds**: Docker is totally fine ✅

## Optimization Checklist

If using Docker in production:

- [ ] Use `network_mode: host` (Linux only)
- [ ] Mount volumes with `:cached` on macOS
- [ ] Use `--cpuset-cpus` to pin to specific cores
- [ ] Disable swap: `--memory-swappiness=0`
- [ ] Use minimal base image (alpine or slim)
- [ ] Pre-compile Python bytecode
- [ ] Use Docker BuildKit for faster builds

## Bottom Line

For your L2 imbalance strategy with 5-60 second holds:

**Docker overhead is irrelevant** - The 1-5ms latency is 100-1000x smaller than your hold times and will be dwarfed by exchange API latency (20-100ms).

Use Docker for **deployment convenience**, not because you have to. If you later move to microsecond trading, revisit this decision.
