#!/bin/bash

# Walter Bot VPS Setup Script
# For Ubuntu/Debian based systems

set -e

echo "==================================="
echo "Walter Bot VPS Setup Script"
echo "==================================="

# Update system
echo "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Python and required system packages
echo "Installing Python and dependencies..."
sudo apt install -y python3 python3-pip python3-venv git

# Create bot user (optional but recommended for security)
echo "Creating bot user..."
if ! id "botuser" &>/dev/null; then
    sudo adduser --disabled-password --gecos "" botuser
    echo "User 'botuser' created"
else
    echo "User 'botuser' already exists"
fi

# Clone or copy bot files
echo "Setting up bot directory..."
sudo mkdir -p /home/botuser/walter
sudo cp -r ./* /home/botuser/walter/
sudo chown -R botuser:botuser /home/botuser/walter

# Create virtual environment
echo "Creating Python virtual environment..."
cd /home/botuser/walter
sudo -u botuser python3 -m venv venv

# Install Python packages
echo "Installing Python packages..."
sudo -u botuser ./venv/bin/pip install --upgrade pip
sudo -u botuser ./venv/bin/pip install -r requirements.txt

# Check for .env file
if [ ! -f "/home/botuser/walter/.env" ]; then
    echo ""
    echo "WARNING: .env file not found!"
    echo "Please create /home/botuser/walter/.env with your tokens:"
    echo "  DISCORD_TOKEN=your_token"
    echo "  CHANNEL_ID=your_channel"
    echo "  OPENAI_API_KEY=your_key"
    echo "  TIMEZONE=America/New_York"
    echo ""
    
    # Copy example if it exists
    if [ -f "/home/botuser/walter/.env.example" ]; then
        sudo cp /home/botuser/walter/.env.example /home/botuser/walter/.env
        sudo chown botuser:botuser /home/botuser/walter/.env
        echo "Copied .env.example to .env - please edit it!"
    fi
fi

# Install PM2 for process management
echo "Installing PM2..."
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt install -y nodejs
sudo npm install -g pm2

# Create PM2 ecosystem file
cat << 'EOF' | sudo tee /home/botuser/walter/ecosystem.config.js
module.exports = {
  apps: [{
    name: 'walter',
    script: '/home/botuser/walter/venv/bin/python',
    args: 'bot.py',
    cwd: '/home/botuser/walter',
    interpreter: '/bin/bash',
    interpreter_args: '-c',
    error_file: '/home/botuser/walter/logs/pm2-error.log',
    out_file: '/home/botuser/walter/logs/pm2-out.log',
    log_file: '/home/botuser/walter/logs/pm2-combined.log',
    time: true,
    autorestart: true,
    max_restarts: 10,
    restart_delay: 5000,
    env: {
      NODE_ENV: 'production'
    }
  }]
}
EOF

# Create logs directory
sudo -u botuser mkdir -p /home/botuser/walter/logs

# Set up PM2 to run on startup
echo "Setting up PM2 startup..."
sudo pm2 startup systemd -u botuser --hp /home/botuser
sudo -u botuser pm2 start /home/botuser/walter/ecosystem.config.js
sudo -u botuser pm2 save

# Create systemd service as alternative
echo "Creating systemd service (alternative to PM2)..."
sudo tee /etc/systemd/system/walter.service << 'EOF'
[Unit]
Description=Walter Discord Bot
After=network.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/home/botuser/walter
ExecStart=/home/botuser/walter/venv/bin/python bot.py
Restart=always
RestartSec=10
StandardOutput=append:/home/botuser/walter/logs/systemd.log
StandardError=append:/home/botuser/walter/logs/systemd-error.log

[Install]
WantedBy=multi-user.target
EOF

echo ""
echo "==================================="
echo "Setup Complete!"
echo "==================================="
echo ""
echo "Next steps:"
echo "1. Edit the configuration file:"
echo "   sudo nano /home/botuser/walter/.env"
echo ""
echo "2. Start the bot with PM2:"
echo "   sudo -u botuser pm2 start /home/botuser/walter/ecosystem.config.js"
echo "   sudo -u botuser pm2 logs walter"
echo ""
echo "   OR with systemd:"
echo "   sudo systemctl enable walter"
echo "   sudo systemctl start walter"
echo "   sudo journalctl -u walter -f"
echo ""
echo "3. Check bot status:"
echo "   sudo -u botuser pm2 status"
echo ""
echo "Bot logs location: /home/botuser/walter/logs/"
echo ""
