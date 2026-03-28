# SteamCMD Auto-Installation Script

This script automatically installs SteamCMD on Debian/Ubuntu-based systems with all required dependencies.

## Quick Start

### On a fresh VPS:

```bash
# Download the script
wget https://your-server.com/install_steamcmd.sh
# OR use curl
curl -O https://your-server.com/install_steamcmd.sh

# Make it executable
chmod +x install_steamcmd.sh

# Run with sudo
sudo bash install_steamcmd.sh
```

## What the Script Does

1. **Checks OS compatibility** - Verifies you're running Debian/Ubuntu
2. **Creates steam user** - Creates a dedicated non-root user for safety
3. **Enables i386 architecture** - Adds 32-bit support (required for SteamCMD)
4. **Installs dependencies** - Installs lib32gcc-s1, lib32stdc++6, curl, tar
5. **Downloads SteamCMD** - Gets the latest version from Valve's CDN
6. **Extracts and sets up** - Unpacks and runs initial setup
7. **Creates convenience symlink** - Makes steamcmd accessible from anywhere

## System Requirements

- **OS**: Debian 10+, Ubuntu 18.04+, or compatible distros
- **Architecture**: x86_64 (64-bit)
- **Root access**: Required (script must run with sudo)
- **Internet connection**: Required to download packages

## After Installation

### Using SteamCMD

**Option 1: As steam user**
```bash
sudo su - steam
cd ~/steamcmd
./steamcmd.sh
```

**Option 2: Direct command (after symlink creation)**
```bash
steamcmd
```

### Common SteamCMD Commands

```bash
# Login anonymously (for free/public servers)
login anonymous

# Login with Steam account
login <username> <password>

# Set installation directory
force_install_dir /home/steam/game-server

# Download/update a game server (example: CS2)
app_update 730 validate

# Exit SteamCMD
quit
```

### Example: Installing a Game Server

```bash
# Switch to steam user
sudo su - steam

# Run SteamCMD
cd ~/steamcmd
./steamcmd.sh

# In SteamCMD prompt:
Steam> login anonymous
Steam> force_install_dir /home/steam/csgo-server
Steam> app_update 740 validate
Steam> quit
```

## Popular Game Server App IDs

| Game | App ID |
|------|--------|
| Counter-Strike 2 | 730 |
| CS:GO Dedicated Server | 740 |
| Team Fortress 2 | 232250 |
| Left 4 Dead 2 | 222860 |
| Garry's Mod | 4020 |
| Rust | 258550 |
| ARK: Survival Evolved | 376030 |
| Valheim | 896660 |

Full list: https://developer.valvesoftware.com/wiki/Dedicated_Servers_List

## Troubleshooting

### "cannot execute: required file not found"
- The script should handle this, but if you see this error, install 32-bit libraries:
  ```bash
  sudo dpkg --add-architecture i386
  sudo apt update
  sudo apt install lib32gcc-s1 lib32stdc++6
  ```

### Permission Issues
- Always run game servers as the 'steam' user, not root
- If you need to modify files: `sudo chown -R steam:steam /path/to/files`

### Firewall Configuration
- Don't forget to open required ports for your game server
- Example for CS:GO: `sudo ufw allow 27015/tcp` and `sudo ufw allow 27015/udp`

## Uninstallation

```bash
# Remove SteamCMD files
sudo rm -rf /home/steam/steamcmd

# Remove symlink
sudo rm /usr/local/bin/steamcmd

# Remove steam user (optional)
sudo userdel -r steam

# Remove 32-bit support (optional, may break other apps)
sudo dpkg --remove-architecture i386
```

## Security Best Practices

1. **Never run game servers as root** - Use the steam user
2. **Keep system updated** - Regular `apt update && apt upgrade`
3. **Configure firewall** - Only open necessary ports
4. **Use strong passwords** - If using Steam Guard/authentication
5. **Regular backups** - Backup your server configurations

## Support & Resources

- Official Documentation: https://developer.valvesoftware.com/wiki/SteamCMD
- Dedicated Servers List: https://developer.valvesoftware.com/wiki/Dedicated_Servers_List
- Steam Community: https://steamcommunity.com/

---

**Script Version**: 1.0
**Last Updated**: 2026-03-28
**Compatible with**: Debian 10+, Ubuntu 18.04+
