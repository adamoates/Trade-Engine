# Architecture

This directory contains system design documentation and architectural evolution.

## <× System Design

The Trade Engine follows **Clean Architecture** principles with clear separation of concerns across three layers:

### Layer 1: Domain Layer
Business logic, trading strategies, and domain models
- Location: `src/trade_engine/domain/`

### Layer 2: Application Layer
Application services orchestrating business logic
- Location: `src/trade_engine/services/`

### Layer 3: Infrastructure Layer
External integrations (brokers, feeds, database, API)
- Location: `src/trade_engine/adapters/`, `src/trade_engine/api/`, `src/trade_engine/db/`

## =Ë Available Documentation

- [Live Trading Evolution](live-trading-evolution.md) - Complete system evolution from concept to production
- [TDD Audit Strategy](tdd-audit-and-strategy.md) - Testing approach and quality gates
- [Trade Fingerprint System](trade-fingerprint-system.md) - Trade identification and tracking

## <¯ Design Principles

### Separation of Concerns
Each layer has distinct responsibilities:
- **Domain**: Core business rules (no external dependencies)
- **Application**: Workflow orchestration
- **Infrastructure**: External system integrations

### Dependency Rule
Dependencies point inward:
- Infrastructure ’ Application ’ Domain
- Domain never depends on outer layers

### Interface Segregation
Clean contracts between layers:
- [Broker Interface](../reference/adapters/broker-interface.md)
- [Feed Interface](../reference/adapters/feed-interface.md)
- [Data Source Interface](../reference/adapters/data-source-interface.md)

## = Related Documentation

- [CLAUDE.md](../../.claude/CLAUDE.md) - Three-layer architecture section
- [Adapter Interfaces](../reference/adapters/README.md) - Complete interface specifications
- [Development Setup](../development/setup.md) - Project structure walkthrough

## =Ê Key Components

### Trading Engine Core
- Risk management (kill switch, position limits)
- Signal generation (L2 imbalance, breakout detection)
- Order execution (multi-broker support)

### Data Pipeline
- Real-time L2 order book streaming
- Historical data recording and replay
- Market data validation

### Monitoring & Control
- FastAPI server for engine control
- Database logging (PostgreSQL)
- Real-time position tracking

---

**Last Updated**: 2025-10-31
