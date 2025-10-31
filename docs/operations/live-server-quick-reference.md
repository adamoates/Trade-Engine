# 🚀 Live Server Update: Quick Reference

**BEFORE YOU START**: Create a backup!

## Automated Update (Recommended)

```bash
ssh user@your-server.com
cd ~/MFT
./scripts/update_live_server.sh --dry-run  # Test first
./scripts/update_live_server.sh            # Real update
```

## Manual Update (5 Steps)

### 1️⃣ Stop & Backup
```bash
sudo systemctl stop mft-trading  # or pkill -f "python.*mft"
BACKUP=~/backups/$(date +%Y%m%d_%H%M%S)
rsync -a --exclude='.venv' --exclude='__pycache__' ~/MFT/ $BACKUP/
```

### 2️⃣ Update Git
```bash
cd ~/MFT
git remote set-url origin https://github.com/adamoates/Trade-Engine.git
git pull origin main
```

### 3️⃣ Update Package
```bash
source .venv/bin/activate
pip uninstall -y mft
pip install -e .
python -c "import trade_engine; print('✓ Works!')"
```

### 4️⃣ Update Service (if using systemd)
```bash
sudo nano /etc/systemd/system/mft-trading.service
# Change: WorkingDirectory=/home/user/Trade-Engine
# Change: ExecStart=...python -m trade_engine.core.engine.runner_live
sudo systemctl daemon-reload
```

### 5️⃣ Rename & Restart
```bash
cd ~ && mv MFT Trade-Engine && cd Trade-Engine
sudo systemctl start trade-engine  # or your service name
```

## Verify
```bash
✓ git remote -v  # Points to Trade-Engine
✓ python -c "import trade_engine"
✓ sudo systemctl status trade-engine
✓ tail -f logs/*.log  # Check for errors
```

## Rollback (if needed)
```bash
sudo systemctl stop trade-engine
rsync -a $BACKUP/ ~/Trade-Engine/
pip install -e .
sudo systemctl start mft-trading
```

## Full Guide
See `docs/guides/live-server-update.md` for detailed instructions.

---

**Estimated Downtime:** 5-10 minutes
**Backup Location:** `~/backups/YYYYMMDD_HHMMSS/`
