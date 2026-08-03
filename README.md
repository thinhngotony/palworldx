# Palworld Dedicated Server - All-in-One Manager

🎮 **One script to rule them all!** Complete Palworld Dedicated Server management with automatic port forwarding.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Platform](https://img.shields.io/badge/platform-Linux-lightgrey.svg)
![Shell](https://img.shields.io/badge/shell-bash-green.svg)

## ⚡ Quick Start

### One-Line Installation

```bash
curl -sSL https://raw.githubusercontent.com/thinhngotony/palworldx/main/palworld.sh | sudo bash -s -- install
```

Or download and use interactively:

```bash
wget https://raw.githubusercontent.com/thinhngotony/palworldx/main/palworld.sh
sudo bash palworld.sh
```

## 🚀 Features

- ✅ **Single Script** - One file does everything (install, start, stop, update, manage)
- ✅ **Auto Port Forwarding** - Automatically opens firewall ports (UFW/iptables/firewalld)
- ✅ **Interactive Menu** - Easy-to-use CLI interface
- ✅ **Command Line Mode** - Perfect for automation and SSH
- ✅ **Zero Dependencies** - Downloads and installs everything automatically
- ✅ **Steam User Management** - Secure, runs as non-root user
- ✅ **Live Console** - Attach to running server
- ✅ **Real-time Logs** - Monitor server activity
- ✅ **Status Monitoring** - Check server health and ports

## 📋 All-in-One Commands

```bash
# Installation
sudo bash palworld.sh install    # Install everything (first time)
sudo bash palworld.sh ports       # Configure firewall ports only

# Server Control
sudo bash palworld.sh start       # Start server
sudo bash palworld.sh stop        # Stop server
sudo bash palworld.sh restart     # Restart server
sudo bash palworld.sh status      # Check status

# Management
sudo bash palworld.sh update      # Update to latest version
sudo bash palworld.sh console     # Attach to live console
sudo bash palworld.sh logs        # View real-time logs

# Interactive
sudo bash palworld.sh menu        # Show interactive menu (default)
sudo bash palworld.sh help        # Show all commands
```

## 🎯 Interactive Menu

Run without arguments for an interactive menu:

```bash
sudo bash palworld.sh
```

```
╔════════════════════════════════════════════╗
║              Main Menu                     ║
╚════════════════════════════════════════════╝

Server Management:
  1) Start Server
  2) Stop Server
  3) Restart Server
  4) Server Status
  5) View Console (live)
  6) View Logs (tail -f)

Installation & Updates:
  7) Install/Reinstall Server
  8) Update Server
  9) Open Firewall Ports

Configuration:
  10) Edit Server Config
  11) Show Server Info

Other:
  12) Uninstall Server
  0) Exit
```

## 🔥 Automatic Port Forwarding

The script **automatically detects and configures** your firewall:

- **UFW** - Ubuntu/Debian default
- **iptables** - Traditional Linux firewall
- **firewalld** - RedHat/CentOS/Fedora

Ports opened automatically:
- `8211/UDP` - Game traffic (required)
- `27015/TCP+UDP` - Steam query
- `25575/TCP` - RCON admin

No manual port configuration needed! ✨

## 📦 What Gets Installed

| Component | Location | Size |
|-----------|----------|------|
| SteamCMD | `/home/steam/steamcmd` | ~175 MB |
| Palworld Server | `/home/steam/palworld-server` | ~3.6 GB |
| Management Script | `palworld.sh` | 17 KB |

**Total:** One script manages everything. No clutter!

## 💻 Usage Examples

### First Time Setup

```bash
# Download the script
wget https://raw.githubusercontent.com/thinhngotony/palworldx/main/palworld.sh

# Install everything
sudo bash palworld.sh install

# Start playing!
sudo bash palworld.sh start
```

### Daily Operations

```bash
# Start server
sudo bash palworld.sh start

# Check if running
sudo bash palworld.sh status

# View live logs
sudo bash palworld.sh logs

# Stop server
sudo bash palworld.sh stop
```

### Updates & Maintenance

```bash
# Update to latest version
sudo bash palworld.sh update

# Restart after update
sudo bash palworld.sh start

# Edit configuration
sudo bash palworld.sh menu
# Then select option 10
```

### Troubleshooting

```bash
# Check detailed status
sudo bash palworld.sh status

# View live console
sudo bash palworld.sh console
# Press Ctrl+A then D to detach

# View logs
sudo bash palworld.sh logs

# Manually open ports
sudo bash palworld.sh ports
```

## 🌐 Network & Connectivity

### Ports (Auto-Configured)

| Port | Protocol | Purpose | Auto-Opened |
|------|----------|---------|-------------|
| 8211 | UDP | Game traffic | ✅ Yes |
| 27015 | TCP+UDP | Steam query | ✅ Yes |
| 25575 | TCP | RCON admin | ✅ Yes |

### Cloud Provider Setup

**Important:** Also open ports in your VPS provider's firewall/security groups:

**AWS EC2:** Security Groups → Inbound Rules
**Google Cloud:** VPC Firewall Rules
**Azure:** Network Security Groups
**DigitalOcean:** Firewalls
**Linode:** Cloud Firewall

The script handles **local firewall**, you handle **cloud firewall**.

### Connecting to Your Server

Players connect using:
```
YOUR_SERVER_IP:8211
```

## ⚙️ Server Configuration

Edit settings anytime:

```bash
sudo bash palworld.sh menu
# Select option 10: Edit Server Config
```

Or manually edit:
```bash
nano /home/steam/palworld-server/Pal/Saved/Config/LinuxServer/PalWorldSettings.ini
```

Common settings:

```ini
[/Script/Pal.PalGameWorldSettings]
ServerName="My Palworld Server"
ServerDescription="Welcome!"
ServerPassword=""
AdminPassword="admin123"
PublicPort=8211
ServerPlayerMaxNum=32
RCONEnabled=True
RCONPort=25575
```

Restart after changes:
```bash
sudo bash palworld.sh restart
```

## Production Configuration and Discovery

The manager preserves the defaults below while allowing a root-owned configuration file at `/etc/palworld/palworld.conf` (override with `PALWORLD_CONFIG_FILE`) or validated one-off environment overrides:

```ini
STEAM_USER=steam
STEAM_HOME=/home/steam
STEAMCMD_DIR=/home/steam/steamcmd
PALWORLD_DIR=/home/steam/palworld-server
SCREEN_NAME=palworld
DASHBOARD_PORT=8080
DASHBOARD_FILE=/home/steam/dashboard.py
LIFECYCLE_LOCK_FILE=/home/steam/.palworld-lifecycle.lock
```

Values are parsed as `KEY=value`, not evaluated as shell code. Paths must be absolute; the deployment file must be a regular root-owned file. Use `sudo bash palworld.sh discover` for read-only resolved configuration and installation/running state. `status` is also read-only and uses the configured server root, screen name, and runtime paths.

## Production Safety


Lifecycle operations (stop, restart, update) always require explicit confirmation when the server is running.

**Interactive confirmations:**
- Typing `yes` at the prompt permits the operation.
- Any other input cancels it.
- Non-interactive invocations (pipelines, cron) are refused unless `--yes` is supplied.

**Automation:** Pass `--yes` only after you have independently verified the interruption is safe:
```bash
0 4 * * * /bin/bash /path/to/palworld.sh restart --yes
```

**Concurrency guard:** A file lock (`/home/steam/.palworld-lifecycle.lock`) prevents overlapping stop/restart/update operations. A second concurrent call will wait or fail instead of racing the server.

## 📊 System Requirements

### Minimum
- **OS:** Debian 10+ or Ubuntu 18.04+
- **CPU:** 4 cores
- **RAM:** 8 GB
- **Storage:** 30 GB
- **Network:** 10 Mbps upload

### Recommended
- **OS:** Ubuntu 22.04 LTS
- **CPU:** 6+ cores
- **RAM:** 16 GB
- **Storage:** 50 GB SSD
- **Network:** 50 Mbps upload

## Mods Integration

The dashboard Mods page (`/mods`) is a catalog and inventory surface, not a mod downloader. The authoritative metadata is [`mods/catalog.json`](mods/catalog.json); its URLs, scope, dependencies, installation method, verification state, client instructions, and server-install gate must be reviewed before any action. An unknown or unverified entry is not verified and is never permission to install.

### Upload, inspect, preview, apply

Use this workflow for a mod archive supplied by an operator. It stages and inspects the upload before touching the live server:

1. **Upload** the original archive to a staging location outside the live server tree (for example `/home/steam/palworld-staging/incoming/`). Record the catalog ID, source URL, release/file version, SHA-256, and operator.
2. **Inspect** the archive without extracting over production. Confirm the expected file layout, loader/runtime, dependencies, game/server version, permissions, and whether it contains client-only files. Reject archives that are unidentified, altered, or inconsistent with the catalog.
3. **Preview** the proposed file operations and conflicts against the server tree. A preview must list additions, replacements, deletions, dependency failures, and the backup/rollback plan. Preview is read-only and must not stop the server.
4. **Apply** only after a tested backup and an explicit maintenance approval immediately before the change. Apply the minimum validated files, record the resulting hash/manifest, and verify startup and logs. Client-only files never belong in the server upload.

Do not confuse an upload with an install: staging, inspection, and preview may happen online; applying server files is a production mutation.

### Production downtime rules

- Treat every server-side mod apply, replacement, removal, or rollback as downtime-risking, even when a package claims hot reload.
- Announce the maintenance window, stop admitting players, take a save/config/mod backup, and use the lifecycle lock. Stop the server cleanly before changing loaded files; never force-kill it to make an install proceed.
- If stop, backup, validation, apply, or restart fails, stop the procedure and restore/rollback only through the same confirmed maintenance window. Never silently continue.
- Keep the server online for upload, inspection, dependency checks, and preview. A client-only mod requires no server downtime, but each player installs it locally and the catalog gate still applies.

### Catalog policy

The catalog defaults every server install to **blocked unless explicitly approved**. Client/both/unknown scope is classification, not a safety claim. Unknown or unsupported mods—including Nexus references 550, 3915, 214, and 190—must remain unverified, require manual review, and cannot be automatically downloaded, preview-applied, or installed on the dedicated server. Duplicate references #4 and #7 resolve to the single canonical `dungeon-boss-respawn-map-timer` entry.

See `mods/catalog.json` for the per-mod client instructions and explicit server-install gate.

## 🔧 Advanced Usage

### Automation / Cron Jobs

```bash
# Auto-restart at 4 AM daily (requires --yes for non-interactive runs)
0 4 * * * /bin/bash /path/to/palworld.sh restart --yes

# Auto-update and restart weekly (requires --yes for non-interactive runs)
0 3 * * 0 /bin/bash /path/to/palworld.sh update --yes && /bin/bash /path/to/palworld.sh start
```

### Systemd Service (Optional)

Create `/etc/systemd/system/palworld.service`:

```ini
[Unit]
Description=Palworld Dedicated Server
After=network.target

[Service]
Type=forking
User=steam
ExecStart=/bin/bash /home/steam/palworld.sh start
ExecStop=/bin/bash /home/steam/palworld.sh stop
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable:
```bash
sudo systemctl daemon-reload
sudo systemctl enable palworld
sudo systemctl start palworld
```

### Multiple Servers

Run multiple instances on different ports:

```bash
# Copy script and modify PALWORLD_DIR and port
cp palworld.sh palworld2.sh
nano palworld2.sh
# Change: PALWORLD_DIR="/home/steam/palworld-server2"
# Edit config to use different port

sudo bash palworld2.sh install
```

## 🔍 Troubleshooting

### Server Won't Start

```bash
# Check status
sudo bash palworld.sh status

# View logs
sudo bash palworld.sh logs

# View console
sudo bash palworld.sh console
```

### Can't Connect

1. Check server is running: `sudo bash palworld.sh status`
2. Check port is listening: `sudo netstat -tulpn | grep 8211`
3. Verify cloud provider firewall
4. Test direct connection: `YOUR_IP:8211`

### Port Issues

```bash
# Re-run port configuration
sudo bash palworld.sh ports

# Check if ports are open
sudo iptables -L -n | grep 8211
sudo ufw status | grep 8211
```

### Installation Fails

```bash
# Check if running as root
whoami  # Must show 'root'

# Check disk space
df -h

# Check internet
ping -c 3 google.com

# Retry installation
sudo bash palworld.sh install
```

## 🗑️ Uninstallation

### From Interactive Menu

```bash
sudo bash palworld.sh menu
# Select option 12: Uninstall Server
```

### Manual Removal

```bash
# Stop server
sudo bash palworld.sh stop

# Remove server files
sudo rm -rf /home/steam/palworld-server
sudo rm -rf /home/steam/steamcmd

# Remove script
rm palworld.sh

# Remove steam user (optional)
sudo userdel -r steam
```

## 🤝 Contributing

Contributions welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

## 📜 License

This project is licensed under the MIT License.

## 🔗 Resources

- **Official Docs:** [Palworld Server Guide](https://docs.palworldgame.com/)
- **SteamCMD:** [Valve Developer Wiki](https://developer.valvesoftware.com/wiki/SteamCMD)
- **Discord:** [Palworld Community](https://discord.gg/palworld)
- **Issues:** [Report Problems](https://github.com/thinhngotony/palworldx/issues)

## ⭐ Support This Project

If this script helped you, please:
- ⭐ Star the repository
- 🐛 Report bugs
- 💡 Suggest features
- 📢 Share with others

## 📝 Changelog

### v2.0.0 (2026-03-28)
- 🎉 **All-in-One Script** - Single file for everything
- ⚡ **Auto Port Forwarding** - Detects and configures firewall automatically
- 🎮 **Enhanced Menu** - Better interactive experience
- 📊 **Status Monitoring** - Real-time server info
- 🔧 **Improved Commands** - More intuitive CLI
- 📝 **Live Logs** - Real-time log viewing
- 🖥️ **Console Access** - Direct server console attachment

### v1.0.0 (2026-03-28)
- Initial release with separate scripts

---

**Made with ❤️ for the Palworld community**

**Repository:** https://github.com/thinhngotony/palworldx
**App ID:** 2394010
**Maintainer:** [@thinhngotony](https://github.com/thinhngotony)
