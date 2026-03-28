# Palworld Dedicated Server Installer

🎮 Interactive CLI installer for Palworld Dedicated Server on Linux (Debian/Ubuntu)

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Platform](https://img.shields.io/badge/platform-Linux-lightgrey.svg)
![Shell](https://img.shields.io/badge/shell-bash-green.svg)

## 🚀 Quick Start

### One-Command Installation

```bash
curl -sSL https://raw.githubusercontent.com/thinhngotony/palworldx/main/palworld-installer.sh | sudo bash -s -- --full
```

Or download and run interactively:

```bash
wget https://raw.githubusercontent.com/thinhngotony/palworldx/main/palworld-installer.sh
sudo bash palworld-installer.sh
```

## 📋 Features

- ✅ **Interactive CLI Menu** - Easy-to-use interface with numbered options
- ✅ **Automated Installation** - Installs all dependencies automatically
- ✅ **SteamCMD Setup** - Downloads and configures SteamCMD
- ✅ **Palworld Server** - Installs Palworld Dedicated Server (App ID: 2394010)
- ✅ **Management Scripts** - Start, stop, update, and status commands
- ✅ **Firewall Configuration** - Optional automatic firewall setup
- ✅ **Non-Interactive Mode** - Command-line options for automation
- ✅ **Reusable** - Use on multiple VPS servers

## 📦 What Gets Installed

| Component | Location | Size | Description |
|-----------|----------|------|-------------|
| SteamCMD | `/home/steam/steamcmd` | ~175 MB | Steam command-line tool |
| Palworld Server | `/home/steam/palworld-server` | ~3.6 GB | Game server files |
| Management Scripts | `/home/steam/*.sh` | ~2 KB | Server control scripts |

## 🎯 Interactive Menu

The installer provides an easy-to-use menu with the following options:

1. **Full Installation** - Install everything (SteamCMD + Palworld Server)
2. **Install SteamCMD Only** - Just install SteamCMD
3. **Install Palworld Server Only** - Requires SteamCMD to be installed first
4. **Update Palworld Server** - Update to the latest version
5. **Create/Update Management Scripts** - Recreate control scripts
6. **Configure Firewall** - Set up firewall rules
7. **Show Server Status** - Check if server is running
8. **Exit** - Close the installer

## 💻 Usage

### Interactive Mode (Recommended)

```bash
sudo bash palworld-installer.sh
```

Navigate through the menu using numbers 1-8.

### Non-Interactive Mode

```bash
# Full installation
sudo bash palworld-installer.sh --full

# Install SteamCMD only
sudo bash palworld-installer.sh --steamcmd

# Install Palworld Server only (requires SteamCMD)
sudo bash palworld-installer.sh --palworld

# Show help
sudo bash palworld-installer.sh --help
```

## 🎮 Server Management

After installation, use these commands as the `steam` user:

```bash
# Switch to steam user
sudo su - steam

# Start server
./start-palworld.sh

# Stop server
./stop-palworld.sh

# Update server
./update-palworld.sh

# Check status
./status-palworld.sh

# View live console
screen -r palworld
# Press Ctrl+A then D to detach
```

## 🌐 Network Configuration

### Required Ports

| Port | Protocol | Purpose | Required |
|------|----------|---------|----------|
| 8211 | UDP | Game traffic | ✅ Yes |
| 27015 | TCP+UDP | Steam query | ⚠️ Recommended |
| 25575 | TCP | RCON admin | ❌ Optional |

### Firewall Setup

The installer can automatically configure UFW firewall. Alternatively, set up manually:

```bash
# UFW
sudo ufw allow 8211/udp
sudo ufw allow 27015/tcp
sudo ufw allow 27015/udp
sudo ufw allow 25575/tcp

# iptables
sudo iptables -A INPUT -p udp --dport 8211 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 27015 -j ACCEPT
sudo iptables -A INPUT -p udp --dport 27015 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 25575 -j ACCEPT
```

**Important:** Also open these ports in your cloud provider's security groups/firewall.

## ⚙️ Server Configuration

Configuration file location:
```
/home/steam/palworld-server/Pal/Saved/Config/LinuxServer/PalWorldSettings.ini
```

Common settings:

```ini
[/Script/Pal.PalGameWorldSettings]
ServerName="My Palworld Server"
ServerDescription="Welcome to my server!"
ServerPassword=""
AdminPassword="YourAdminPassword"
PublicPort=8211
ServerPlayerMaxNum=32
RCONEnabled=True
RCONPort=25575
```

After changing settings, restart the server:
```bash
./stop-palworld.sh
./start-palworld.sh
```

## 📊 System Requirements

### Minimum

- **OS:** Debian 10+ or Ubuntu 18.04+
- **CPU:** 4 cores
- **RAM:** 8 GB
- **Storage:** 30 GB free space
- **Network:** 10 Mbps upload

### Recommended

- **OS:** Ubuntu 22.04 LTS
- **CPU:** 6+ cores
- **RAM:** 16 GB
- **Storage:** 50 GB SSD
- **Network:** 50 Mbps upload

## 🔧 Troubleshooting

### Server Won't Start

```bash
# Check logs
cd ~/palworld-server/Pal/Saved/Logs
tail -f latest.log

# Check if port is in use
sudo netstat -tulpn | grep 8211
```

### Can't Connect to Server

1. Verify server is running: `./status-palworld.sh`
2. Check local firewall rules
3. Verify cloud provider security groups
4. Try direct IP connection: `YOUR_IP:8211`

### Installation Fails

```bash
# Check if running as root
whoami  # Should show 'root'

# Check internet connectivity
ping -c 3 google.com

# Check disk space
df -h
```

## 🔄 Updating

### Update Palworld Server

```bash
sudo su - steam
./update-palworld.sh
```

### Update Installer Script

```bash
wget https://raw.githubusercontent.com/thinhngotony/palworldx/main/palworld-installer.sh -O palworld-installer.sh
chmod +x palworld-installer.sh
```

## 🗑️ Uninstallation

### Remove Palworld Server Only

```bash
sudo su - steam
./stop-palworld.sh
rm -rf ~/palworld-server
rm ~/*.sh
```

### Complete Removal

```bash
sudo systemctl stop palworld 2>/dev/null
sudo rm -rf /home/steam/steamcmd /home/steam/palworld-server
sudo rm /usr/local/bin/steamcmd
sudo userdel -r steam
```

## 📖 Additional Documentation

- [PALWORLD_SERVER_GUIDE.md](PALWORLD_SERVER_GUIDE.md) - Comprehensive server management guide
- [QUICK_START.md](QUICK_START.md) - Quick reference guide

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📜 License

This project is licensed under the MIT License.

## 🔗 Resources

- [Official Palworld Server Documentation](https://docs.palworldgame.com/getting-started/deploy-dedicated-server/)
- [SteamCMD Wiki](https://developer.valvesoftware.com/wiki/SteamCMD)
- [Palworld Discord](https://discord.gg/palworld)

## ⭐ Support

If this helped you, please star the repository!

## 📝 Changelog

### v1.0.0 (2026-03-28)
- Initial release
- Interactive CLI menu
- Full automated installation
- Management scripts
- Firewall configuration
- Non-interactive mode

---

**Repository:** https://github.com/thinhngotony/palworldx
**App ID:** 2394010
**Maintained by:** thinhngotony
