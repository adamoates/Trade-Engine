# Live Server Update Guide: MFT → Trade-Engine

This guide covers updating a live production server from the old MFT branding to the new Trade-Engine branding.

## Quick Start (Automated)

```bash
# SSH into your live server
ssh user@your-server.com

# Navigate to repository
cd ~/MFT  # or wherever your repo is

# Download and run the automated update script
./scripts/update_live_server.sh --dry-run  # Test first
./scripts/update_live_server.sh            # Actual update
```

## Manual Update Steps

If you prefer manual control or the automated script doesn't work:

### 1. Pre-Update Checklist

```bash
# Check current status
git status
git remote -v
ps aux | grep python  # Check for running processes

# Verify you're on the correct branch
git branch --show-current
```

### 2. Stop Running Processes

```bash
# If using systemd
sudo systemctl stop mft-trading  # Replace with your service name

# Or kill processes manually
pkill -f "python.*mft"

# Verify stopped
ps aux | grep mft
```

### 3. Create Backup

```bash
# Create backup directory
BACKUP_DIR=~/backups/$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Backup repository (excluding venv and cache)
rsync -a --exclude='.venv' --exclude='__pycache__' \
      --exclude='*.pyc' --exclude='htmlcov' \
      ~/MFT/ $BACKUP_DIR/

# Backup installed packages
source .venv/bin/activate
pip freeze > $BACKUP_DIR/requirements_backup.txt

echo "Backup created at: $BACKUP_DIR"
```

### 4. Update Git Repository

```bash
cd ~/MFT  # Your current location

# Fetch latest changes
git fetch --all

# Update remote URLs
git remote set-url origin https://github.com/adamoates/Trade-Engine.git
git remote set-url main https://github.com/adamoates/Trade-Engine.git

# Pull latest changes (should include rebrand commits)
git pull origin main  # or your branch name

# Verify remote is updated
git remote -v
```

### 5. Update Python Package

```bash
# Activate virtual environment
source .venv/bin/activate

# Uninstall old package
pip uninstall -y mft

# Install new package
pip install -e .

# Verify installation
python -c "import trade_engine; print('✓ Package works!')"
python -m trade_engine.core.engine.runner_live --help
```

### 6. Update Configuration Files

Check and update any config files that reference old paths:

```bash
# Search for old package references
grep -r "mft\." --include="*.yaml" --include="*.yml" --include="*.env" .

# Update manually if found
# Example: src/mft/core/config/live.yaml → src/trade_engine/core/config/live.yaml
```

**Common files to check:**
- `.env` - Environment variables
- `*.yaml` / `*.yml` - Configuration files
- Systemd service files (see next section)
- Cron jobs
- Monitoring/alerting configs

### 7. Update Systemd Services (if applicable)

If you're running as a systemd service:

```bash
# Check for existing services
systemctl list-units --type=service | grep -i mft

# Edit service file
sudo nano /etc/systemd/system/mft-trading.service

# Update the following:
# [Service]
# WorkingDirectory=/home/user/Trade-Engine  # Updated path
# ExecStart=/home/user/Trade-Engine/.venv/bin/python -m trade_engine.core.engine.runner_live
```

**Example service file update:**

```ini
[Unit]
Description=Trade-Engine Trading Bot
After=network.target

[Service]
Type=simple
User=trader
WorkingDirectory=/home/trader/Trade-Engine
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/trader/Trade-Engine/.venv/bin/python -m trade_engine.core.engine.runner_live --config src/trade_engine/core/config/live.yaml
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Reload systemd
sudo systemctl daemon-reload

# Optionally rename the service file
sudo mv /etc/systemd/system/mft-trading.service /etc/systemd/system/trade-engine.service
sudo systemctl daemon-reload
sudo systemctl enable trade-engine.service
```

### 8. Rename Directory

```bash
# Move to parent directory
cd ~

# Rename directory
mv MFT Trade-Engine

# Navigate into renamed directory
cd Trade-Engine

# Verify git still works
git status
```

### 9. Update Docker (if using)

If running with Docker:

```bash
cd ~/Trade-Engine

# Rebuild Docker image
docker-compose build trade-engine

# Update any running containers
docker-compose down
docker-compose up -d trade-engine
```

### 10. Test & Restart

```bash
# Test the installation
python -m trade_engine.core.engine.runner_live --help

# If using systemd
sudo systemctl start trade-engine
sudo systemctl status trade-engine

# Check logs
journalctl -u trade-engine -f

# Or run manually for testing
python -m trade_engine.core.engine.runner_live --config src/trade_engine/core/config/paper.yaml
```

## Rollback Procedure

If something goes wrong:

```bash
# Stop new processes
sudo systemctl stop trade-engine  # or pkill -f trade_engine

# Restore from backup
BACKUP_DIR=~/backups/YYYYMMDD_HHMMSS  # Your backup timestamp
rsync -a $BACKUP_DIR/ ~/Trade-Engine/

# Reinstall old package
cd ~/Trade-Engine
source .venv/bin/activate
pip uninstall -y trade-engine
pip install -e .

# Restart old service
sudo systemctl start mft-trading  # Your old service name
```

## Verification Checklist

After update, verify:

- [ ] Git remote points to `github.com/adamoates/Trade-Engine`
- [ ] Package `trade-engine` imports successfully
- [ ] Configuration files point to correct paths
- [ ] Systemd service (if used) starts successfully
- [ ] Logs show no import errors
- [ ] Directory is named `Trade-Engine`
- [ ] Backup exists and is accessible

## Common Issues

### Issue: Import errors after update

**Solution:**
```bash
pip uninstall -y mft trade-engine
pip install -e .
```

### Issue: Old package still being used

**Check:**
```bash
pip list | grep -E "mft|trade-engine"
which python
python -c "import sys; print(sys.path)"
```

**Fix:**
```bash
# Make sure you're in the right venv
source .venv/bin/activate
pip install -e . --force-reinstall
```

### Issue: Systemd service won't start

**Debug:**
```bash
sudo systemctl status trade-engine
sudo journalctl -u trade-engine -n 50
```

Common causes:
- Wrong paths in service file
- Old import paths in Python code
- Wrong user/permissions

### Issue: "Module not found" errors

Ensure paths are updated everywhere:
```bash
# Find all references to old package
grep -r "from mft\." --include="*.py" .
grep -r "import mft\." --include="*.py" .

# Should return no results from your code (only venv is OK)
```

## Support

If you encounter issues:

1. Check the rollback procedure above
2. Review backup at `~/backups/TIMESTAMP/`
3. Check logs for specific error messages
4. Verify all steps were completed

## Post-Update Monitoring

For first 24 hours after update:

```bash
# Monitor logs continuously
journalctl -u trade-engine -f

# Or if running manually
tail -f logs/*.log

# Check system resources
htop

# Verify trading is working
# Check positions, orders, P&L
```

## Summary

The update process:
1. ✅ Stop processes
2. ✅ Create backup
3. ✅ Update git repo & remotes
4. ✅ Update Python package
5. ✅ Update config files
6. ✅ Update systemd services
7. ✅ Rename directory
8. ✅ Test & restart
9. ✅ Monitor for issues

Estimated downtime: **5-10 minutes** (with automated script)
