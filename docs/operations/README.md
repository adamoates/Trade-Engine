# Operations

This directory contains documentation for running and deploying the Trade Engine in production.

## =€ Overview

Operational guides for deploying, monitoring, and maintaining the Trade Engine in live trading environments.

## =Ë Available Documentation

- [Deployment Guide](deployment.md) - Production deployment procedures
- [Data Recording](data-recording.md) - Real-time market data capture
- [Docker Performance](docker-performance.md) - Container optimization
- [Live Server Guide](live-server-quick-reference.md) - Server management commands
- [Live Server Updates](live-server-update.md) - Update and maintenance procedures

### Coming Soon
- Database Operations - PostgreSQL management and backup
- Monitoring Guide - System health and alerting
- Troubleshooting Guide - Common issues and solutions

## =¥ Production Setup

### Prerequisites
- Linux VPS with <50ms latency to exchange
- Docker and Docker Compose installed
- PostgreSQL database configured
- API keys securely stored (environment variables)

### Deployment Steps
1. Clone repository to server
2. Configure environment variables (`.env`)
3. Start PostgreSQL container
4. Run data recording (24h minimum)
5. Validate data quality
6. Start trading engine (paper trading first!)

## =Ê Monitoring

### Health Checks
- WebSocket connection stability
- Database connectivity
- Risk limit compliance
- Kill switch status

### Key Metrics
- Win rate (target: 55%+)
- Daily P&L (target: $50-100)
- Sharpe ratio (target: >0.5)
- Max drawdown (limit: -$1,000)

### Alert Conditions
- =¨ Kill switch triggered
-   Daily loss limit approaching (-$400)
-   WebSocket disconnections (>3/day)
-   Test failures in CI pipeline

## = Security

### API Key Management
- Never commit keys to git
- Use environment variables only
- Rotate keys quarterly
- Use testnet keys for development

### Database Security
- Strong passwords (20+ characters)
- Network isolation (firewall rules)
- Regular backups (daily minimum)
- Encrypted connections (SSL/TLS)

## = Related Documentation

- [CI/CD Setup](../ci-cd/setup.md) - Automated deployment
- [Docker Performance](docker-performance.md) - Container optimization
- [Data Recording](data-recording.md) - Market data capture

## =È Performance Targets

### Latency
- Message processing: <5ms
- Order placement: <20ms
- Signal-to-execution: <50ms

### Reliability
- Uptime: 99.9% during market hours
- Data loss: 0 trades
- Order success rate: >98%

### Capacity
- L2 updates: 1000/sec sustained
- Concurrent strategies: 5+
- Database writes: 100/sec

---

**Last Updated**: 2025-10-31
