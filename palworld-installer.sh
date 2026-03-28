#!/bin/bash
#
# Interactive Palworld Server Installer
# Repository: https://github.com/thinhngotony/palworldx
#

set -e

# Colors for better UX
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Banner
show_banner() {
    clear
    echo -e "${CYAN}=============================================="
    echo "  Palworld Dedicated Server Installer"
    echo "  Interactive CLI Menu"
    echo -e "==============================================${NC}"
    echo ""
}

# Check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}ERROR: This script must be run as root${NC}"
        echo "Usage: sudo bash palworld-installer.sh"
        exit 1
    fi
}

# Detect OS
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VERSION=$VERSION_ID
        echo -e "${GREEN}Detected OS: $PRETTY_NAME${NC}"
    else
        echo -e "${RED}ERROR: Cannot detect OS version${NC}"
        exit 1
    fi

    if [[ "$OS" != "debian" && "$OS" != "ubuntu" ]]; then
        echo -e "${YELLOW}WARNING: This script is designed for Debian/Ubuntu.${NC}"
        echo -e "Your OS: $OS"
        read -p "Do you want to continue anyway? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Install dependencies
install_dependencies() {
    echo -e "${BLUE}Installing dependencies...${NC}"

    # Enable i386 architecture
    if ! dpkg --print-foreign-architectures | grep -q i386; then
        echo "Adding i386 architecture..."
        dpkg --add-architecture i386
    fi

    # Update package lists
    echo "Updating package lists..."
    apt-get update -qq

    # Install packages
    echo "Installing required packages..."
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
        lib32gcc-s1 \
        lib32stdc++6 \
        curl \
        tar \
        ca-certificates \
        wget \
        screen \
        git \
        nano

    echo -e "${GREEN}Dependencies installed successfully!${NC}"
}

# Create steam user
create_steam_user() {
    if ! id -u steam > /dev/null 2>&1; then
        echo -e "${BLUE}Creating 'steam' user...${NC}"
        useradd -m -s /bin/bash steam
        echo -e "${GREEN}User 'steam' created successfully${NC}"
    else
        echo -e "${GREEN}User 'steam' already exists${NC}"
    fi
}

# Install SteamCMD
install_steamcmd() {
    echo -e "${BLUE}Installing SteamCMD...${NC}"

    su - steam -c '
        mkdir -p ~/steamcmd
        cd ~/steamcmd

        if [ ! -f steamcmd.sh ]; then
            echo "Downloading SteamCMD..."
            curl -sqL "https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz" -o steamcmd_linux.tar.gz

            echo "Extracting SteamCMD..."
            tar -xzf steamcmd_linux.tar.gz
            rm steamcmd_linux.tar.gz

            echo "Running initial setup..."
            ./steamcmd.sh +quit
        else
            echo "SteamCMD already installed"
        fi
    '

    # Create symlink
    if [ ! -f /usr/local/bin/steamcmd ]; then
        ln -s /home/steam/steamcmd/steamcmd.sh /usr/local/bin/steamcmd
    fi

    echo -e "${GREEN}SteamCMD installed successfully!${NC}"
}

# Install Palworld Server
install_palworld() {
    echo -e "${BLUE}Installing Palworld Dedicated Server...${NC}"
    echo "This may take 5-15 minutes depending on your connection..."
    echo ""

    su - steam -c '
        mkdir -p ~/palworld-server
        cd ~/steamcmd
        ./steamcmd.sh +force_install_dir /home/steam/palworld-server +login anonymous +app_update 2394010 validate +quit
    '

    echo -e "${GREEN}Palworld Server installed successfully!${NC}"
}

# Create management scripts
create_management_scripts() {
    echo -e "${BLUE}Creating management scripts...${NC}"

    # Start script
    cat > /home/steam/start-palworld.sh << 'EOFSTART'
#!/bin/bash
cd ~/palworld-server
screen -dmS palworld ./PalServer.sh
echo "Palworld server started in screen session 'palworld'"
echo "To view console: screen -r palworld"
echo "To detach: Press Ctrl+A then D"
EOFSTART

    # Stop script
    cat > /home/steam/stop-palworld.sh << 'EOFSTOP'
#!/bin/bash
screen -S palworld -X quit 2>/dev/null
echo "Palworld server stopped"
EOFSTOP

    # Update script
    cat > /home/steam/update-palworld.sh << 'EOFUPDATE'
#!/bin/bash
echo "Stopping Palworld server..."
screen -S palworld -X quit 2>/dev/null
sleep 3

echo "Updating Palworld server..."
cd ~/steamcmd
./steamcmd.sh +force_install_dir /home/steam/palworld-server +login anonymous +app_update 2394010 validate +quit

echo "Update complete! Start the server with: ./start-palworld.sh"
EOFUPDATE

    # Status script
    cat > /home/steam/status-palworld.sh << 'EOFSTATUS'
#!/bin/bash
if screen -list | grep -q "palworld"; then
    echo "Palworld server is RUNNING"
    echo ""
    screen -list | grep palworld
else
    echo "Palworld server is NOT running"
fi
EOFSTATUS

    # Set permissions
    chown steam:steam /home/steam/*.sh
    chmod +x /home/steam/*.sh

    echo -e "${GREEN}Management scripts created!${NC}"
}

# Configure firewall
configure_firewall() {
    echo -e "${BLUE}Checking firewall configuration...${NC}"

    if command -v ufw > /dev/null 2>&1; then
        echo "Configuring UFW firewall..."
        ufw allow 8211/udp comment 'Palworld Game Port'
        ufw allow 27015/tcp comment 'Palworld Query Port'
        ufw allow 27015/udp comment 'Palworld Query UDP'
        ufw allow 25575/tcp comment 'Palworld RCON'
        echo -e "${GREEN}Firewall rules added${NC}"
    else
        echo -e "${YELLOW}UFW not found. Please manually open these ports:${NC}"
        echo "  - 8211/UDP (Game Port)"
        echo "  - 27015/TCP+UDP (Query Port)"
        echo "  - 25575/TCP (RCON Port)"
    fi
}

# Show completion message
show_completion() {
    echo ""
    echo -e "${GREEN}=============================================="
    echo "  Installation Complete!"
    echo -e "==============================================${NC}"
    echo ""
    echo "Palworld Server Location: /home/steam/palworld-server"
    echo ""
    echo "Management Commands (run as steam user):"
    echo "  sudo su - steam"
    echo "  ./start-palworld.sh    # Start server"
    echo "  ./stop-palworld.sh     # Stop server"
    echo "  ./update-palworld.sh   # Update server"
    echo "  ./status-palworld.sh   # Check status"
    echo ""
    echo "Server Access: YOUR_SERVER_IP:8211"
    echo ""
    echo -e "${YELLOW}Important: Open these ports in your cloud provider:${NC}"
    echo "  - 8211/UDP (required)"
    echo "  - 27015/TCP+UDP (optional)"
    echo "  - 25575/TCP (optional)"
    echo ""
}

# Main Menu
main_menu() {
    while true; do
        show_banner
        echo "Select installation option:"
        echo ""
        echo -e "${CYAN}1)${NC} Full Installation (SteamCMD + Palworld Server)"
        echo -e "${CYAN}2)${NC} Install SteamCMD Only"
        echo -e "${CYAN}3)${NC} Install Palworld Server Only (requires SteamCMD)"
        echo -e "${CYAN}4)${NC} Update Palworld Server"
        echo -e "${CYAN}5)${NC} Create/Update Management Scripts"
        echo -e "${CYAN}6)${NC} Configure Firewall"
        echo -e "${CYAN}7)${NC} Show Server Status"
        echo -e "${CYAN}8)${NC} Exit"
        echo ""
        read -p "Enter your choice [1-8]: " choice

        case $choice in
            1)
                show_banner
                echo -e "${CYAN}Starting Full Installation...${NC}"
                echo ""
                detect_os
                create_steam_user
                install_dependencies
                install_steamcmd
                install_palworld
                create_management_scripts
                configure_firewall
                show_completion
                read -p "Press Enter to continue..."
                ;;
            2)
                show_banner
                echo -e "${CYAN}Installing SteamCMD...${NC}"
                echo ""
                detect_os
                create_steam_user
                install_dependencies
                install_steamcmd
                echo -e "${GREEN}SteamCMD installation complete!${NC}"
                read -p "Press Enter to continue..."
                ;;
            3)
                show_banner
                if [ ! -f /home/steam/steamcmd/steamcmd.sh ]; then
                    echo -e "${RED}ERROR: SteamCMD not found. Install SteamCMD first (Option 2)${NC}"
                    read -p "Press Enter to continue..."
                    continue
                fi
                echo -e "${CYAN}Installing Palworld Server...${NC}"
                echo ""
                install_palworld
                create_management_scripts
                echo -e "${GREEN}Palworld Server installation complete!${NC}"
                read -p "Press Enter to continue..."
                ;;
            4)
                show_banner
                echo -e "${CYAN}Updating Palworld Server...${NC}"
                if [ -f /home/steam/update-palworld.sh ]; then
                    su - steam -c './update-palworld.sh'
                else
                    echo -e "${RED}Update script not found. Run option 5 to create scripts.${NC}"
                fi
                read -p "Press Enter to continue..."
                ;;
            5)
                show_banner
                echo -e "${CYAN}Creating Management Scripts...${NC}"
                create_management_scripts
                read -p "Press Enter to continue..."
                ;;
            6)
                show_banner
                echo -e "${CYAN}Configuring Firewall...${NC}"
                configure_firewall
                read -p "Press Enter to continue..."
                ;;
            7)
                show_banner
                echo -e "${CYAN}Server Status:${NC}"
                echo ""
                if [ -f /home/steam/status-palworld.sh ]; then
                    su - steam -c './status-palworld.sh'
                    echo ""
                    if [ -d /home/steam/palworld-server ]; then
                        echo "Installation Size:"
                        du -sh /home/steam/palworld-server /home/steam/steamcmd 2>/dev/null || echo "Not installed"
                    fi
                else
                    echo -e "${RED}Status script not found${NC}"
                fi
                echo ""
                read -p "Press Enter to continue..."
                ;;
            8)
                echo -e "${GREEN}Thank you for using Palworld Installer!${NC}"
                echo "Repository: https://github.com/thinhngotony/palworldx"
                exit 0
                ;;
            *)
                echo -e "${RED}Invalid option. Please try again.${NC}"
                sleep 2
                ;;
        esac
    done
}

# Run the installer
if [ "$#" -eq 0 ]; then
    # Interactive mode
    check_root
    main_menu
else
    # Command line mode
    case "$1" in
        --full)
            check_root
            show_banner
            echo -e "${CYAN}Starting Full Installation (Non-Interactive)...${NC}"
            detect_os
            create_steam_user
            install_dependencies
            install_steamcmd
            install_palworld
            create_management_scripts
            configure_firewall
            show_completion
            ;;
        --steamcmd)
            check_root
            show_banner
            detect_os
            create_steam_user
            install_dependencies
            install_steamcmd
            echo -e "${GREEN}SteamCMD installation complete!${NC}"
            ;;
        --palworld)
            check_root
            show_banner
            install_palworld
            create_management_scripts
            echo -e "${GREEN}Palworld Server installation complete!${NC}"
            ;;
        --help)
            echo "Usage: sudo bash palworld-installer.sh [option]"
            echo ""
            echo "Options:"
            echo "  (no option)   Interactive menu"
            echo "  --full        Full installation (non-interactive)"
            echo "  --steamcmd    Install SteamCMD only"
            echo "  --palworld    Install Palworld Server only"
            echo "  --help        Show this help"
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
fi
