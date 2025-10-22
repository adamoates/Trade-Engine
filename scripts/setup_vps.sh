#!/bin/bash
#
# Phase 0 Week 1: VPS Setup Automation
#
# Automates initial VPS configuration for MFT trading bot.
# Run this on a fresh Ubuntu 22.04 LTS VPS.
#
# Usage:
#   1. SSH into VPS as root
#   2. Download this script: wget https://raw.githubusercontent.com/YOUR_REPO/main/scripts/setup_vps.sh
#   3. Make executable: chmod +x setup_vps.sh
#   4. Run: ./setup_vps.sh
#
# What this script does:
#   - Updates system packages
#   - Creates mftbot user
#   - Installs Python 3.11
#   - Installs Docker
#   - Configures basic firewall
#   - Tests latency to Binance
#   - Sets up project directory
#

set -e  # Exit on error
set -u  # Exit on undefined variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
MFT_USER="mftbot"
PROJECT_DIR="/home/${MFT_USER}/mft-trading-bot"

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
}

# Step 1: Update system
update_system() {
    log_info "Updating system packages..."
    apt update -y
    apt upgrade -y
    log_info "System updated ✅"
}

# Step 2: Create mftbot user
create_user() {
    log_info "Creating mftbot user..."

    if id "${MFT_USER}" &>/dev/null; then
        log_warn "User ${MFT_USER} already exists"
    else
        adduser --disabled-password --gecos "" ${MFT_USER}
        usermod -aG sudo ${MFT_USER}
        log_info "User ${MFT_USER} created ✅"
    fi

    # Copy SSH keys from root
    if [ -d /root/.ssh ]; then
        mkdir -p /home/${MFT_USER}/.ssh
        cp /root/.ssh/authorized_keys /home/${MFT_USER}/.ssh/ 2>/dev/null || true
        chown -R ${MFT_USER}:${MFT_USER} /home/${MFT_USER}/.ssh
        chmod 700 /home/${MFT_USER}/.ssh
        chmod 600 /home/${MFT_USER}/.ssh/authorized_keys 2>/dev/null || true
        log_info "SSH keys copied ✅"
    fi
}

# Step 3: Install Python 3.11
install_python() {
    log_info "Installing Python 3.11..."

    # Add deadsnakes PPA for Python 3.11
    apt install -y software-properties-common
    add-apt-repository -y ppa:deadsnakes/ppa
    apt update -y

    # Install Python 3.11 and tools
    apt install -y \
        python3.11 \
        python3.11-venv \
        python3.11-dev \
        python3-pip \
        build-essential

    # Verify installation
    python3.11 --version
    log_info "Python 3.11 installed ✅"
}

# Step 4: Install Docker
install_docker() {
    log_info "Installing Docker..."

    # Check if Docker already installed
    if command -v docker &> /dev/null; then
        log_warn "Docker already installed"
        return
    fi

    # Install Docker using official script
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh

    # Add mftbot user to docker group
    usermod -aG docker ${MFT_USER}

    # Start Docker service
    systemctl enable docker
    systemctl start docker

    # Verify installation
    docker --version
    log_info "Docker installed ✅"
}

# Step 5: Install essential tools
install_tools() {
    log_info "Installing essential tools..."

    apt install -y \
        git \
        curl \
        wget \
        vim \
        htop \
        net-tools \
        ufw \
        jq

    log_info "Tools installed ✅"
}

# Step 6: Configure firewall
configure_firewall() {
    log_info "Configuring firewall..."

    # Allow SSH (port 22)
    ufw allow 22/tcp

    # Allow HTTP/HTTPS (for future API)
    ufw allow 80/tcp
    ufw allow 443/tcp

    # Enable firewall (non-interactive)
    echo "y" | ufw enable

    ufw status
    log_info "Firewall configured ✅"
}

# Step 7: Test latency to Binance
test_latency() {
    log_info "Testing latency to Binance..."

    if ! command -v ping &> /dev/null; then
        apt install -y iputils-ping
    fi

    log_info "Pinging api.binance.com (10 packets)..."
    ping -c 10 api.binance.com | tail -1

    # Extract average latency
    avg_latency=$(ping -c 10 api.binance.com | tail -1 | awk -F '/' '{print $5}')

    if (( $(echo "$avg_latency < 50" | bc -l) )); then
        log_info "Latency: ${avg_latency}ms ✅ (Target: <50ms)"
    else
        log_warn "Latency: ${avg_latency}ms ⚠️  (Target: <50ms)"
        log_warn "Consider choosing a VPS closer to Binance servers (NYC recommended)"
    fi
}

# Step 8: Create project directory
create_project_dir() {
    log_info "Creating project directory..."

    # Create directory as mftbot user
    sudo -u ${MFT_USER} mkdir -p ${PROJECT_DIR}
    sudo -u ${MFT_USER} mkdir -p ${PROJECT_DIR}/data
    sudo -u ${MFT_USER} mkdir -p ${PROJECT_DIR}/logs

    log_info "Project directory created: ${PROJECT_DIR} ✅"
}

# Step 9: Install Python packages
install_python_packages() {
    log_info "Installing Python packages for Phase 0..."

    # Create virtual environment as mftbot user
    sudo -u ${MFT_USER} python3.11 -m venv ${PROJECT_DIR}/.venv

    # Install packages
    sudo -u ${MFT_USER} ${PROJECT_DIR}/.venv/bin/pip install --upgrade pip

    # Install Phase 0 requirements
    sudo -u ${MFT_USER} ${PROJECT_DIR}/.venv/bin/pip install \
        ccxt==4.2.0 \
        pandas==2.1.0 \
        python-dotenv==1.0.0 \
        loguru==0.7.2 \
        pytest==7.4.0 \
        black==23.12.0 \
        ruff==0.1.9

    log_info "Python packages installed ✅"
}

# Step 10: System optimizations for low-latency
optimize_system() {
    log_info "Applying low-latency optimizations..."

    # Disable swap (for consistent latency)
    swapoff -a
    sed -i '/swap/d' /etc/fstab

    # Increase network buffer sizes
    cat >> /etc/sysctl.conf << EOF

# MFT Trading Bot Optimizations
net.core.rmem_max=134217728
net.core.wmem_max=134217728
net.ipv4.tcp_rmem=4096 87380 67108864
net.ipv4.tcp_wmem=4096 65536 67108864
net.core.netdev_max_backlog=5000
EOF

    sysctl -p

    log_info "System optimizations applied ✅"
}

# Step 11: Create helpful aliases
create_aliases() {
    log_info "Creating helpful aliases..."

    cat >> /home/${MFT_USER}/.bashrc << 'EOF'

# MFT Trading Bot Aliases
alias mft='cd /home/mftbot/mft-trading-bot'
alias venv='source /home/mftbot/mft-trading-bot/.venv/bin/activate'
alias logs='cd /home/mftbot/mft-trading-bot/logs && tail -f *.log'
alias ll='ls -alh'
EOF

    log_info "Aliases created ✅"
}

# Step 12: Secure SSH
secure_ssh() {
    log_info "Securing SSH configuration..."

    # Backup original config
    cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup

    # Disable root login
    sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config

    # Disable password authentication (key-only)
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config

    # Restart SSH service
    systemctl restart sshd

    log_info "SSH secured (root login disabled, key-only auth) ✅"
    log_warn "Make sure you can SSH as ${MFT_USER} before logging out!"
}

# Main execution
main() {
    echo ""
    echo "======================================"
    echo "  MFT Trading Bot - VPS Setup"
    echo "  Phase 0 Week 1"
    echo "======================================"
    echo ""

    check_root

    log_info "Starting VPS setup..."
    echo ""

    update_system
    create_user
    install_python
    install_docker
    install_tools
    configure_firewall
    test_latency
    create_project_dir
    install_python_packages
    optimize_system
    create_aliases
    secure_ssh

    echo ""
    echo "======================================"
    echo "  ✅ VPS Setup Complete!"
    echo "======================================"
    echo ""
    log_info "Next steps:"
    echo "  1. Exit this SSH session"
    echo "  2. SSH back in as ${MFT_USER}: ssh ${MFT_USER}@YOUR_VPS_IP"
    echo "  3. Navigate to project: cd ${PROJECT_DIR}"
    echo "  4. Activate venv: source .venv/bin/activate"
    echo "  5. Copy your recording scripts to ${PROJECT_DIR}"
    echo "  6. Start recording: python record_l2_data.py --symbol BTC/USDT --duration 24"
    echo ""
    log_warn "IMPORTANT: Test SSH as ${MFT_USER} before closing this session!"
    echo ""
}

# Run main
main
