# Quick Start Guide

## Installation Scripts Created

I've created automated installation scripts for SteamCMD and Palworld Dedicated Server that you can use on this VPS or any other Debian/Ubuntu server.

### Files Created:

1. **install_steamcmd_and_palworld.sh** - Main installation script with Palworld support
2. **install_steamcmd.sh** - Original SteamCMD-only installation script
3. **PALWORLD_SERVER_GUIDE.md** - Complete Palworld server management guide
4. **STEAMCMD_INSTALL_README.md** - SteamCMD documentation

## Installation Commands

### Option 1: Install SteamCMD + Palworld Server (Recommended)
```bash
sudo bash /home/steam/install_steamcmd_and_palworld.sh --with-palworld
```

This will:
- Install SteamCMD with all dependencies
- Download and install Palworld Dedicated Server
- Create management scripts (start, stop, update, status)
- Configure firewall rules automatically
- Set up everything ready to use

**Estimated time**: 5-15 minutes (depending on download speed)

### Option 2: Install Only SteamCMD
```bash
sudo bash /home/steam/install_steamcmd_and_palworld.sh
```

Install Palworld later with:
```bash
sudo bash /home/steam/install_steamcmd_and_palworld.sh --palworld-only
```

## After Installation

### Starting Palworld Server
```bash
# Switch to steam user
sudo su - steam

# Start the server
./start-palworld.sh

# Check if running
./status-palworld.sh
```

### Server Access
Your server will be accessible at:
```
YOUR_SERVER_IP:8211
```

Players connect via:
1. Launch Palworld
2. Multiplayer → Join Multiplayer Game
3. Enter your server IP and port

### Server Management Commands
```bash
./start-palworld.sh    # Start server in background
./stop-palworld.sh     # Stop server
./update-palworld.sh   # Update to latest version
./status-palworld.sh   # Check if running
screen -r palworld     # View live console
```

### Configuration File
Edit server settings:
```bash
nano ~/palworld-server/Pal/Saved/Config/LinuxServer/PalWorldSettings.ini
```

Important settings:
- ServerName
- ServerPassword
- AdminPassword
- ServerPlayerMaxNum (max players)
- PublicPort (default 8211)

## Required Ports

Make sure these ports are open in your VPS firewall/security groups:

| Port | Protocol | Purpose |
|------|----------|---------|
| 8211 | UDP | Game traffic (required) |
| 27015 | TCP+UDP | Query port (optional) |
| 25575 | TCP | RCON admin (optional) |

## Using on Another VPS

### Method 1: Copy Script Directly
```bash
# On new VPS, copy the script file
scp steam@current-server:/home/steam/install_steamcmd_and_palworld.sh .

# Run it
sudo bash install_steamcmd_and_palworld.sh --with-palworld
```

### Method 2: Host and Download
```bash
# Host the script on a web server, then on new VPS:
wget https://your-domain.com/install_steamcmd_and_palworld.sh
sudo bash install_steamcmd_and_palworld.sh --with-palworld
```

### Method 3: Copy-Paste
Simply copy the contents of `install_steamcmd_and_palworld.sh` to the new server and run it.

## System Requirements

**Minimum:**
- Debian 10+ or Ubuntu 18.04+
- 4 CPU cores
- 8 GB RAM
- 30 GB disk space
- Root/sudo access

**Recommended:**
- Ubuntu 22.04 LTS
- 6+ CPU cores
- 16 GB RAM
- 50 GB SSD storage

## Troubleshooting

### Script requires password
The installation script needs sudo/root privileges. Run with:
```bash
sudo bash install_steamcmd_and_palworld.sh --with-palworld
```

### 32-bit library errors
The script automatically installs required 32-bit libraries (lib32gcc-s1, lib32stdc++6).

### Server won't start
Check logs:
```bash
cd ~/palworld-server/Pal/Saved/Logs
tail -f latest.log
```

### Can't connect to server
1. Verify server is running: `./status-palworld.sh`
2. Check firewall is allowing port 8211/UDP
3. Check VPS security groups/firewall settings
4. Try connecting with direct IP:PORT format

## Documentation

For complete details, see:
- **PALWORLD_SERVER_GUIDE.md** - Full Palworld server management guide
- **STEAMCMD_INSTALL_README.md** - SteamCMD usage guide

## Support Resources

- Palworld Server Docs: https://docs.palworldgame.com/
- SteamCMD Wiki: https://developer.valvesoftware.com/wiki/SteamCMD
- Palworld Discord: https://discord.gg/palworld

---

**Ready to install?** Run the command above and your Palworld server will be ready in minutes!
