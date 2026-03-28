# Palworld Dedicated Server Installation Guide

Complete guide for installing and managing a Palworld dedicated server on Linux (Debian/Ubuntu).

## Quick Start - One Command Installation

### Install SteamCMD + Palworld Server Together:
```bash
sudo bash install_steamcmd_and_palworld.sh --with-palworld
```

### Install Only SteamCMD (no game server):
```bash
sudo bash install_steamcmd_and_palworld.sh
```

### Install Only Palworld (if SteamCMD already installed):
```bash
sudo bash install_steamcmd_and_palworld.sh --palworld-only
```

## What Gets Installed

### Automatic Installation Includes:
1. **SteamCMD** - Steam's command-line tool
2. **32-bit libraries** - Required dependencies (lib32gcc-s1, lib32stdc++6)
3. **Palworld Dedicated Server** - Latest version (App ID: 2394010)
4. **Management scripts** - Start, stop, update, and status scripts
5. **Firewall rules** - Configured automatically if UFW is available
6. **Screen** - For running server in background

### Directory Structure:
```
/home/steam/
├── steamcmd/                    # SteamCMD installation
├── palworld-server/             # Palworld server files
│   ├── PalServer.sh            # Server executable
│   └── Pal/Saved/Config/       # Configuration files
├── start-palworld.sh           # Start server script
├── stop-palworld.sh            # Stop server script
├── update-palworld.sh          # Update server script
└── status-palworld.sh          # Check server status
```

## Server Management

### Starting the Server
```bash
sudo su - steam
./start-palworld.sh
```

The server runs in a `screen` session named "palworld".

### Viewing Server Console
```bash
sudo su - steam
screen -r palworld
```
Press `Ctrl+A` then `D` to detach without stopping the server.

### Stopping the Server
```bash
sudo su - steam
./stop-palworld.sh
```

### Checking Server Status
```bash
sudo su - steam
./status-palworld.sh
```

### Updating the Server
```bash
sudo su - steam
./update-palworld.sh
```
This will stop the server, download updates, and prepare for restart.

## Configuration

### Server Settings File
```
/home/steam/palworld-server/Pal/Saved/Config/LinuxServer/PalWorldSettings.ini
```

### Common Settings to Modify:
```ini
[/Script/Pal.PalGameWorldSettings]
ServerName="My Palworld Server"
ServerDescription="Welcome to my server!"
ServerPassword=""
AdminPassword="YourAdminPassword"
PublicPort=8211
PublicIP=""
RCONEnabled=True
RCONPort=25575
ServerPlayerMaxNum=32
```

After editing configuration, restart the server:
```bash
./stop-palworld.sh
./start-palworld.sh
```

## Network Configuration

### Required Ports

| Port | Protocol | Purpose | Required |
|------|----------|---------|----------|
| 8211 | UDP | Game traffic | Yes |
| 27015 | TCP+UDP | Steam query | Recommended |
| 25575 | TCP | RCON admin | Optional |

### Firewall Configuration

**UFW (automatically configured by script):**
```bash
sudo ufw allow 8211/udp
sudo ufw allow 27015/tcp
sudo ufw allow 27015/udp
sudo ufw allow 25575/tcp
```

**iptables:**
```bash
sudo iptables -A INPUT -p udp --dport 8211 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 27015 -j ACCEPT
sudo iptables -A INPUT -p udp --dport 27015 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 25575 -j ACCEPT
```

**Cloud/VPS Provider:**
Don't forget to also open these ports in your cloud provider's security groups/firewall settings.

### Changing the Default Port

To run on a different port (recommended for security):

Edit the server start script or use the `-port=` argument:
```bash
cd ~/palworld-server
./PalServer.sh -port=8000
```

Or modify `PalWorldSettings.ini`:
```ini
PublicPort=8000
```

## System Requirements

### Minimum Specifications:
- **OS**: Debian 10+, Ubuntu 18.04+ (Ubuntu 22.04 LTS recommended)
- **CPU**: 4 cores
- **RAM**: 8 GB
- **Storage**: 30 GB free space
- **Network**: 10 Mbps upload

### Recommended Specifications:
- **CPU**: 6+ cores
- **RAM**: 16 GB
- **Storage**: 50 GB SSD
- **Network**: 50 Mbps upload

## Connecting to Your Server

### Direct Connection:
1. Launch Palworld
2. Multiplayer → Join Multiplayer Game
3. Enter: `YOUR_SERVER_IP:8211`

### With Password:
Players will be prompted to enter the server password after connecting.

## Troubleshooting

### Server Won't Start
```bash
# Check if port is already in use
sudo netstat -tulpn | grep 8211

# Check server logs
sudo su - steam
cd ~/palworld-server/Pal/Saved/Logs
tail -f latest.log
```

### Can't Connect to Server
1. Verify server is running: `./status-palworld.sh`
2. Check firewall rules are applied
3. Verify cloud provider security groups
4. Check server logs for errors
5. Try direct IP connection instead of hostname

### Server Crashes
```bash
# View crash logs
cd ~/palworld-server/Pal/Saved/Logs
cat latest.log
```

Common causes:
- Insufficient RAM (needs 8+ GB)
- Corrupted world save
- Outdated server version

### High CPU/Memory Usage
```bash
# Monitor resource usage
top -u steam

# Restart server periodically (add to crontab)
0 4 * * * /home/steam/stop-palworld.sh && sleep 10 && /home/steam/start-palworld.sh
```

## Backup Your Server

### Manual Backup:
```bash
sudo su - steam
cd ~
tar -czf palworld-backup-$(date +%Y%m%d).tar.gz palworld-server/Pal/Saved
```

### Automated Daily Backup Script:
```bash
#!/bin/bash
# Add to crontab: 0 3 * * * /home/steam/backup-palworld.sh

BACKUP_DIR="/home/steam/backups"
SAVE_DIR="/home/steam/palworld-server/Pal/Saved"
DATE=$(date +%Y%m%d-%H%M%S)

mkdir -p $BACKUP_DIR
tar -czf "$BACKUP_DIR/palworld-$DATE.tar.gz" -C "$SAVE_DIR" .

# Keep only last 7 days of backups
find $BACKUP_DIR -name "palworld-*.tar.gz" -mtime +7 -delete

echo "Backup completed: palworld-$DATE.tar.gz"
```

### Restore Backup:
```bash
sudo su - steam
./stop-palworld.sh
cd ~/palworld-server/Pal/Saved
rm -rf *
tar -xzf ~/backups/palworld-YYYYMMDD-HHMMSS.tar.gz
./start-palworld.sh
```

## Performance Optimization

### Adjust Server Settings:
```ini
# In PalWorldSettings.ini
ServerPlayerMaxNum=20          # Reduce max players
DayTimeSpeedRate=1.000000      # Default day speed
NightTimeSpeedRate=1.000000    # Default night speed
WorkSpeedRate=1.000000         # Adjust work speed
```

### Linux System Optimization:
```bash
# Increase file descriptor limits
sudo nano /etc/security/limits.conf
# Add:
steam soft nofile 100000
steam hard nofile 100000

# Increase network buffer sizes
sudo nano /etc/sysctl.conf
# Add:
net.core.rmem_max = 134217728
net.core.wmem_max = 134217728
net.ipv4.tcp_rmem = 4096 87380 67108864
net.ipv4.tcp_wmem = 4096 65536 67108864

# Apply changes
sudo sysctl -p
```

## Advanced: Auto-Start on Boot

### Create systemd service:
```bash
sudo nano /etc/systemd/system/palworld.service
```

```ini
[Unit]
Description=Palworld Dedicated Server
After=network.target

[Service]
Type=forking
User=steam
Group=steam
WorkingDirectory=/home/steam/palworld-server
ExecStart=/usr/bin/screen -dmS palworld /home/steam/palworld-server/PalServer.sh
ExecStop=/usr/bin/screen -S palworld -X quit
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable palworld
sudo systemctl start palworld
sudo systemctl status palworld
```

## Uninstallation

### Remove Palworld Server Only:
```bash
sudo su - steam
./stop-palworld.sh
rm -rf ~/palworld-server
rm ~/start-palworld.sh ~/stop-palworld.sh ~/update-palworld.sh ~/status-palworld.sh
```

### Complete Removal (including SteamCMD):
```bash
sudo systemctl stop palworld 2>/dev/null
sudo systemctl disable palworld 2>/dev/null
sudo rm /etc/systemd/system/palworld.service
sudo rm -rf /home/steam/steamcmd /home/steam/palworld-server
sudo rm /usr/local/bin/steamcmd
sudo userdel -r steam
```

## Additional Resources

- **Official Documentation**: https://docs.palworldgame.com/getting-started/deploy-dedicated-server/
- **Server Requirements**: https://docs.palworldgame.com/getting-started/requirements/
- **Configuration Guide**: https://docs.palworldgame.com/0.1.5.1/settings-and-operation/arguments/
- **Palworld Discord**: https://discord.gg/palworld
- **Steam Community**: https://steamcommunity.com/app/1623730

## FAQ

**Q: How much does it cost to run a Palworld server?**
A: The server software is free. You only pay for VPS hosting (typically $10-30/month).

**Q: Can I run multiple servers on one machine?**
A: Yes, use different ports for each server instance with the `-port=` argument.

**Q: How many players can join?**
A: Default is 32, configurable up to higher limits (resource dependent).

**Q: Do I need a Steam account?**
A: No, the server can be installed and run anonymously.

**Q: Can I mod the server?**
A: Modding support depends on the game's current version. Check official documentation.

---

**Script Version**: 1.0
**Last Updated**: 2026-03-28
**Palworld Server App ID**: 2394010
**Compatible with**: Debian 10+, Ubuntu 18.04+
