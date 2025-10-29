#!/bin/bash
#
# Live Server Update Script: MFT → Trade-Engine Rebrand
#
# This script updates a live production server from the old MFT branding
# to the new Trade-Engine branding with minimal downtime.
#
# Usage:
#   ./scripts/update_live_server.sh [--dry-run]
#
# Safety Features:
#   - Creates backup before changes
#   - Validates environment
#   - Provides rollback capability
#   - Checks for running processes

set -e  # Exit on error
set -u  # Exit on undefined variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
OLD_REPO_NAME="MFT"
NEW_REPO_NAME="Trade-Engine"
OLD_PACKAGE_NAME="mft"
NEW_PACKAGE_NAME="trade-engine"
BACKUP_DIR="${HOME}/backups/$(date +%Y%m%d_%H%M%S)"
DRY_RUN=false

# Parse arguments
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
    echo -e "${BLUE}Running in DRY-RUN mode - no changes will be made${NC}\n"
fi

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

run_command() {
    if [[ "$DRY_RUN" == true ]]; then
        echo -e "${BLUE}[DRY-RUN]${NC} Would run: $*"
    else
        "$@"
    fi
}

# Step 1: Environment validation
echo "=========================================="
echo "  Trade-Engine Live Server Update"
echo "=========================================="
echo ""

log_info "Step 1: Validating environment..."

# Check if we're in the MFT directory
CURRENT_DIR=$(basename "$PWD")
if [[ "$CURRENT_DIR" != "$OLD_REPO_NAME" ]] && [[ "$CURRENT_DIR" != "$NEW_REPO_NAME" ]]; then
    log_error "Not in $OLD_REPO_NAME or $NEW_REPO_NAME directory. Current: $CURRENT_DIR"
    exit 1
fi

# Check if git repository
if [[ ! -d .git ]]; then
    log_error "Not a git repository!"
    exit 1
fi

# Check for uncommitted changes
if [[ -n $(git status --porcelain) ]]; then
    log_warning "Uncommitted changes detected!"
    git status --short
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_error "Aborted by user"
        exit 1
    fi
fi

log_success "Environment validation passed"
echo ""

# Step 2: Check for running processes
log_info "Step 2: Checking for running processes..."

RUNNING_PROCESSES=$(ps aux | grep -E "python.*($OLD_PACKAGE_NAME|$NEW_PACKAGE_NAME)" | grep -v grep || true)
if [[ -n "$RUNNING_PROCESSES" ]]; then
    log_warning "Found running trading processes:"
    echo "$RUNNING_PROCESSES"
    echo ""

    if [[ "$DRY_RUN" == false ]]; then
        read -p "Stop these processes? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "Stopping trading processes..."
            pkill -f "python.*$OLD_PACKAGE_NAME" || true
            sleep 2
            log_success "Processes stopped"
        else
            log_warning "Continuing with processes running (not recommended)"
        fi
    fi
else
    log_success "No running trading processes found"
fi
echo ""

# Step 3: Create backup
log_info "Step 3: Creating backup..."

if [[ "$DRY_RUN" == false ]]; then
    mkdir -p "$BACKUP_DIR"

    # Backup current directory
    log_info "Backing up repository to $BACKUP_DIR"
    rsync -a --exclude='.git' --exclude='.venv' --exclude='__pycache__' \
          --exclude='*.pyc' --exclude='htmlcov' --exclude='.pytest_cache' \
          ./ "$BACKUP_DIR/repo/"

    # Backup virtual environment list
    if [[ -d .venv ]]; then
        .venv/bin/pip freeze > "$BACKUP_DIR/requirements_backup.txt"
    fi

    # Backup any running service configurations
    if command -v systemctl &> /dev/null; then
        systemctl list-units --type=service | grep -i "$OLD_PACKAGE_NAME\|$NEW_PACKAGE_NAME" > "$BACKUP_DIR/services.txt" || true
    fi

    log_success "Backup created at $BACKUP_DIR"
else
    log_info "Would create backup at $BACKUP_DIR"
fi
echo ""

# Step 4: Update git repository
log_info "Step 4: Updating git repository..."

CURRENT_BRANCH=$(git branch --show-current)
log_info "Current branch: $CURRENT_BRANCH"

# Fetch latest changes
log_info "Fetching latest changes from remote..."
run_command git fetch --all

# Check remote URL
CURRENT_REMOTE=$(git remote get-url origin)
log_info "Current remote: $CURRENT_REMOTE"

if [[ "$CURRENT_REMOTE" == *"$OLD_REPO_NAME"* ]]; then
    NEW_REMOTE="${CURRENT_REMOTE/$OLD_REPO_NAME/$NEW_REPO_NAME}"
    log_info "Updating remote URL to: $NEW_REMOTE"
    run_command git remote set-url origin "$NEW_REMOTE"
    run_command git remote set-url main "$NEW_REMOTE" 2>/dev/null || true
    log_success "Remote URL updated"
else
    log_success "Remote URL already points to $NEW_REPO_NAME"
fi

# Pull latest changes
log_info "Pulling latest changes..."
run_command git pull origin "$CURRENT_BRANCH"

log_success "Git repository updated"
echo ""

# Step 5: Update Python package
log_info "Step 5: Updating Python package..."

if [[ -d .venv ]]; then
    log_info "Activating virtual environment..."
    source .venv/bin/activate

    # Uninstall old package
    log_info "Uninstalling old package: $OLD_PACKAGE_NAME"
    run_command pip uninstall -y "$OLD_PACKAGE_NAME" 2>/dev/null || true

    # Install new package
    log_info "Installing new package: $NEW_PACKAGE_NAME"
    run_command pip install -e .

    # Verify installation
    if [[ "$DRY_RUN" == false ]]; then
        if python -c "import trade_engine" 2>/dev/null; then
            log_success "Package $NEW_PACKAGE_NAME installed successfully"
        else
            log_error "Failed to import $NEW_PACKAGE_NAME"
            exit 1
        fi
    fi
else
    log_warning "No virtual environment found (.venv)"
    log_info "You'll need to manually reinstall the package"
fi
echo ""

# Step 6: Update configuration files
log_info "Step 6: Checking configuration files..."

# Check for any config files that might reference old paths
OLD_CONFIGS=$(grep -r "$OLD_PACKAGE_NAME" --include="*.yaml" --include="*.yml" --include="*.env" --include="*.conf" . 2>/dev/null || true)
if [[ -n "$OLD_CONFIGS" ]]; then
    log_warning "Found references to old package name in config files:"
    echo "$OLD_CONFIGS"
    echo ""
    log_warning "Please manually update these configuration files!"
else
    log_success "No config file updates needed"
fi
echo ""

# Step 7: Update systemd services (if applicable)
log_info "Step 7: Checking systemd services..."

if command -v systemctl &> /dev/null; then
    SERVICES=$(systemctl list-units --type=service --all | grep -i "$OLD_PACKAGE_NAME" | awk '{print $1}' || true)

    if [[ -n "$SERVICES" ]]; then
        log_warning "Found systemd services with old naming:"
        echo "$SERVICES"
        echo ""
        log_info "Service files are typically in /etc/systemd/system/"
        log_warning "You'll need to manually update service files with:"
        echo "  - New package name: $NEW_PACKAGE_NAME"
        echo "  - New import paths: trade_engine.*"
        echo "  - Then run: sudo systemctl daemon-reload"
    else
        log_success "No systemd services need updating"
    fi
else
    log_info "systemctl not available, skipping service check"
fi
echo ""

# Step 8: Rename directory (if needed)
log_info "Step 8: Checking directory name..."

PARENT_DIR=$(dirname "$PWD")
if [[ "$CURRENT_DIR" == "$OLD_REPO_NAME" ]]; then
    NEW_PATH="$PARENT_DIR/$NEW_REPO_NAME"

    if [[ "$DRY_RUN" == false ]]; then
        echo ""
        log_warning "Current directory: $PWD"
        log_warning "Will rename to: $NEW_PATH"
        echo ""
        read -p "Rename directory now? (y/N): " -n 1 -r
        echo

        if [[ $REPLY =~ ^[Yy]$ ]]; then
            cd "$PARENT_DIR"
            mv "$OLD_REPO_NAME" "$NEW_REPO_NAME"
            cd "$NEW_REPO_NAME"
            log_success "Directory renamed to $NEW_REPO_NAME"
            echo ""
            log_info "You are now in: $PWD"
        else
            log_warning "Directory not renamed - you should rename manually later"
            log_info "Run: cd .. && mv $OLD_REPO_NAME $NEW_REPO_NAME"
        fi
    else
        log_info "Would rename: $PWD → $NEW_PATH"
    fi
else
    log_success "Directory already named $NEW_REPO_NAME"
fi
echo ""

# Step 9: Summary and next steps
echo "=========================================="
echo "  Update Summary"
echo "=========================================="
echo ""

if [[ "$DRY_RUN" == false ]]; then
    log_success "Live server update complete!"
    echo ""
    echo "Backup location: $BACKUP_DIR"
    echo ""
    echo "Next steps:"
    echo "  1. Review any warnings above"
    echo "  2. Update any configuration files manually"
    echo "  3. Update systemd service files (if applicable)"
    echo "  4. Test the updated system:"
    echo "     python -m trade_engine.core.engine.runner_live --help"
    echo "  5. Restart your trading processes"
    echo ""
    echo "To rollback if needed:"
    echo "  rsync -a $BACKUP_DIR/repo/ ./"
    echo "  pip install -e ."
    echo ""
else
    log_info "Dry-run complete. No changes were made."
    echo ""
    echo "To perform actual update, run:"
    echo "  ./scripts/update_live_server.sh"
    echo ""
fi

log_success "Done!"
