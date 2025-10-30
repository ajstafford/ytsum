#!/bin/bash
# Installation script for ytsum on Raspberry Pi

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

    echo "Setting up systemd service..."

    # Copy service file
    sudo cp "$INSTALL_DIR/ytsum.service" "$SERVICE_FILE"
    echo "✓ Service file copied to $SERVICE_FILE"

    # Copy timer file (optional)
    if [ -f "$INSTALL_DIR/ytsum.timer" ]; then
        sudo cp "$INSTALL_DIR/ytsum.timer" "$TIMER_FILE"
        echo "✓ Timer file copied to $TIMER_FILE"
    fi

    # Reload systemd
    sudo systemctl daemon-reload

    # Enable and start service
    read -p "Enable service to start on boot? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo systemctl enable "ytsum@${USER_NAME}.service"
        echo "✓ Service enabled"
    fi

    echo
    echo "Systemd service commands:"
    echo "  Start:   sudo systemctl start ytsum@${USER_NAME}.service"
    echo "  Stop:    sudo systemctl stop ytsum@${USER_NAME}.service"
    echo "  Status:  sudo systemctl status ytsum@${USER_NAME}.service"
    echo "  Logs:    sudo journalctl -u ytsum@${USER_NAME}.service -f"
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
echo "   $INSTALL_DIR/venv/bin/ytsum ui"
echo
echo "4. Or run a manual check:"
echo "   $INSTALL_DIR/venv/bin/ytsum run"
echo
echo "For more information, see README.md"
