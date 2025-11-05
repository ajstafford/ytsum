#!/bin/bash
# Installation script for ytsum

set -e  # Exit on error

echo "=== YouTube Transcript Summarizer Installation ==="
echo

# Check if running on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo "Error: This script is designed for Linux systems"
    exit 1
fi

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found Python version: $python_version"

if ! python3 -c 'import sys; exit(0 if sys.version_info >= (3, 9) else 1)'; then
    echo "Error: Python 3.9 or higher is required"
    exit 1
fi

# Get installation directory
INSTALL_DIR="${1:-$(pwd)}"
echo "Installation directory: $INSTALL_DIR"
echo

# Create virtual environment
echo "Creating virtual environment..."
if [ ! -d "$INSTALL_DIR/venv" ]; then
    python3 -m venv "$INSTALL_DIR/venv"
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
source "$INSTALL_DIR/venv/bin/activate"

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip > /dev/null

# Install package in development mode
echo "Installing ytsum and dependencies..."
pip install -e "$INSTALL_DIR" > /dev/null
echo "✓ ytsum installed"

# Initialize configuration
echo
echo "Initializing configuration..."
"$INSTALL_DIR/venv/bin/ytsum" init

# Setup systemd service (optional)
echo
read -p "Do you want to set up systemd service for automatic daily runs? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    USER_NAME=$(whoami)
    SERVICE_FILE="/etc/systemd/system/ytsum@.service"
    TIMER_FILE="/etc/systemd/system/ytsum.timer"

    echo "Setting up systemd services..."

    # Copy service and timer files for scheduled processing
    sudo cp "$INSTALL_DIR/ytsum.service" "$SERVICE_FILE"
    echo "✓ Service file copied to $SERVICE_FILE"

    if [ -f "$INSTALL_DIR/ytsum.timer" ]; then
        sudo cp "$INSTALL_DIR/ytsum.timer" "$TIMER_FILE"
        echo "✓ Timer file copied to $TIMER_FILE"
    fi

    # Copy web service file
    WEB_SERVICE_FILE="/etc/systemd/system/ytsum-web@.service"
    if [ -f "$INSTALL_DIR/ytsum-web.service" ]; then
        sudo cp "$INSTALL_DIR/ytsum-web.service" "$WEB_SERVICE_FILE"
        echo "✓ Web service file copied to $WEB_SERVICE_FILE"
    fi

    # Reload systemd
    sudo systemctl daemon-reload

    # Setup web interface service
    echo
    read -p "Enable web interface to run 24/7? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo systemctl enable "ytsum-web@${USER_NAME}.service"
        sudo systemctl start "ytsum-web@${USER_NAME}.service"
        echo "✓ Web interface enabled and started"
        echo "  Access at: http://$(hostname -I | awk '{print $1}'):5000"
    fi

    # Enable service on boot
    echo
    read -p "Enable processing service to start on boot? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo systemctl enable "ytsum@${USER_NAME}.service"
        echo "✓ Processing service enabled on boot"
    fi

    # Enable and start timer for automatic daily runs
    echo
    read -p "Enable automatic daily checks with systemd timer? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo systemctl enable ytsum.timer
        sudo systemctl start ytsum.timer
        echo "✓ Timer enabled and started (runs daily at midnight)"
    fi

    echo
    echo "Systemd commands:"
    echo "  Web Interface:"
    echo "    Start:   sudo systemctl start ytsum-web@${USER_NAME}.service"
    echo "    Stop:    sudo systemctl stop ytsum-web@${USER_NAME}.service"
    echo "    Status:  sudo systemctl status ytsum-web@${USER_NAME}.service"
    echo "    Logs:    sudo journalctl -u ytsum-web@${USER_NAME}.service -f"
    echo
    echo "  Processing Service:"
    echo "    Start:   sudo systemctl start ytsum@${USER_NAME}.service"
    echo "    Stop:    sudo systemctl stop ytsum@${USER_NAME}.service"
    echo "    Status:  sudo systemctl status ytsum@${USER_NAME}.service"
    echo "    Logs:    sudo journalctl -u ytsum@${USER_NAME}.service -f"
    echo
    echo "  Timer (Daily Automation):"
    echo "    Status:  sudo systemctl status ytsum.timer"
    echo "    Logs:    sudo journalctl -u ytsum.timer -f"
    echo "    Enable:  sudo systemctl enable ytsum.timer"
    echo "    Start:   sudo systemctl start ytsum.timer"
fi

echo
echo "=== Installation Complete ==="
echo
echo "Next steps:"
echo "1. Edit your configuration file with API keys:"
echo "   nano ~/.config/ytsum/.env"
echo
echo "2. Get your API keys:"
echo "   - YouTube API: https://console.cloud.google.com/"
echo "   - OpenRouter API: https://openrouter.ai/"
echo
echo "3. Launch the interface:"
echo "   TUI:  $INSTALL_DIR/venv/bin/ytsum ui"
echo "   Web:  $INSTALL_DIR/venv/bin/ytsum web"
echo
echo "4. Or run a manual check:"
echo "   $INSTALL_DIR/venv/bin/ytsum run"
echo
echo "For more information, see README.md"
