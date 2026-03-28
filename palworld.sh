#!/bin/bash
#
# Palworld Dedicated Server - All-in-One Manager
# Repository: https://github.com/thinhngotony/palworldx
# Usage: sudo bash palworld.sh [command]
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

# Configuration
STEAM_USER="steam"
STEAM_HOME="/home/${STEAM_USER}"
STEAMCMD_DIR="${STEAM_HOME}/steamcmd"
PALWORLD_DIR="${STEAM_HOME}/palworld-server"
SCREEN_NAME="palworld"
APP_ID="2394010"

# Required ports
declare -A PORTS=(
    ["8211"]="udp,Palworld Game Port"
    ["27015"]="tcp,Palworld Query Port"
    ["27015udp"]="udp,Palworld Query UDP"
    ["25575"]="tcp,Palworld RCON"
)

# Banner
show_banner() {
    clear
    echo -e "${CYAN}╔════════════════════════════════════════════╗"
    echo -e "║   Palworld Server - All-in-One Manager    ║"
    echo -e "║   https://github.com/thinhngotony/palworldx║"
    echo -e "╚════════════════════════════════════════════╝${NC}"
    echo ""
}

# Check if running as root (for installation/setup)
check_root() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}ERROR: This operation requires root privileges${NC}"
        echo "Usage: sudo bash palworld.sh $1"
        exit 1
    fi
}

# Check if running as steam user (for server operations)
check_steam_user() {
    if [ "$(whoami)" != "$STEAM_USER" ]; then
        echo -e "${YELLOW}Switching to $STEAM_USER user...${NC}"
        su - $STEAM_USER -c "$(readlink -f "$0") $*"
        exit $?
    fi
}

# Detect OS
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        echo -e "${GREEN}✓ Detected: $PRETTY_NAME${NC}"
    else
        echo -e "${RED}✗ Cannot detect OS${NC}"
        exit 1
    fi
}

# Open ports automatically
auto_open_ports() {
    echo -e "${BLUE}⚡ Auto-configuring firewall ports...${NC}"

    # Try UFW first
    if command -v ufw > /dev/null 2>&1; then
        echo "  Using UFW..."
        for port_key in "${!PORTS[@]}"; do
            IFS=',' read -r protocol comment <<< "${PORTS[$port_key]}"
            port="${port_key//udp/}"  # Remove 'udp' suffix if present

            if ufw allow ${port}/${protocol} comment "$comment" 2>/dev/null; then
                echo -e "  ${GREEN}✓${NC} Opened ${port}/${protocol}"
            else
                echo -e "  ${YELLOW}⚠${NC} ${port}/${protocol} already configured"
            fi
        done
        return 0
    fi

    # Try iptables
    if command -v iptables > /dev/null 2>&1; then
        echo "  Using iptables..."

        # Check for 8211/UDP
        if ! iptables -C INPUT -p udp --dport 8211 -j ACCEPT 2>/dev/null; then
            iptables -A INPUT -p udp --dport 8211 -j ACCEPT
            echo -e "  ${GREEN}✓${NC} Opened 8211/udp"
        fi

        # Check for 27015/TCP
        if ! iptables -C INPUT -p tcp --dport 27015 -j ACCEPT 2>/dev/null; then
            iptables -A INPUT -p tcp --dport 27015 -j ACCEPT
            echo -e "  ${GREEN}✓${NC} Opened 27015/tcp"
        fi

        # Check for 27015/UDP
        if ! iptables -C INPUT -p udp --dport 27015 -j ACCEPT 2>/dev/null; then
            iptables -A INPUT -p udp --dport 27015 -j ACCEPT
            echo -e "  ${GREEN}✓${NC} Opened 27015/udp"
        fi

        # Check for 25575/TCP
        if ! iptables -C INPUT -p tcp --dport 25575 -j ACCEPT 2>/dev/null; then
            iptables -A INPUT -p tcp --dport 25575 -j ACCEPT
            echo -e "  ${GREEN}✓${NC} Opened 25575/tcp"
        fi

        # Save iptables rules
        if command -v iptables-save > /dev/null 2>&1; then
            iptables-save > /etc/iptables/rules.v4 2>/dev/null || true
        fi

        return 0
    fi

    # Try firewalld
    if command -v firewall-cmd > /dev/null 2>&1; then
        echo "  Using firewalld..."
        firewall-cmd --permanent --add-port=8211/udp
        firewall-cmd --permanent --add-port=27015/tcp
        firewall-cmd --permanent --add-port=27015/udp
        firewall-cmd --permanent --add-port=25575/tcp
        firewall-cmd --reload
        echo -e "  ${GREEN}✓${NC} Ports configured"
        return 0
    fi

    echo -e "  ${YELLOW}⚠ No firewall detected${NC}"
    echo -e "  ${YELLOW}⚠ Manually open these ports in your cloud provider:${NC}"
    echo "    • 8211/UDP (Game Port) - REQUIRED"
    echo "    • 27015/TCP+UDP (Query Port)"
    echo "    • 25575/TCP (RCON)"
}

# Install dependencies
install_dependencies() {
    echo -e "${BLUE}📦 Installing dependencies...${NC}"

    if ! dpkg --print-foreign-architectures | grep -q i386; then
        dpkg --add-architecture i386
    fi

    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
        lib32gcc-s1 lib32stdc++6 curl tar ca-certificates \
        wget screen git nano net-tools > /dev/null 2>&1

    echo -e "${GREEN}✓ Dependencies installed${NC}"
}

# Create steam user
create_steam_user() {
    if ! id -u $STEAM_USER > /dev/null 2>&1; then
        echo -e "${BLUE}👤 Creating '$STEAM_USER' user...${NC}"
        useradd -m -s /bin/bash $STEAM_USER
        echo -e "${GREEN}✓ User created${NC}"
    fi
}

# Install SteamCMD
install_steamcmd() {
    echo -e "${BLUE}⚙️  Installing SteamCMD...${NC}"

    su - $STEAM_USER -c "
        mkdir -p ${STEAMCMD_DIR}
        cd ${STEAMCMD_DIR}

        if [ ! -f steamcmd.sh ]; then
            curl -sqL 'https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz' -o steamcmd_linux.tar.gz
            tar -xzf steamcmd_linux.tar.gz
            rm steamcmd_linux.tar.gz
            ./steamcmd.sh +quit
        fi
    "

    if [ ! -f /usr/local/bin/steamcmd ]; then
        ln -s ${STEAMCMD_DIR}/steamcmd.sh /usr/local/bin/steamcmd
    fi

    echo -e "${GREEN}✓ SteamCMD installed${NC}"
}

# Install Palworld
install_palworld() {
    echo -e "${BLUE}🎮 Installing Palworld Dedicated Server...${NC}"
    echo -e "${YELLOW}   This may take 5-15 minutes...${NC}"

    su - $STEAM_USER -c "
        mkdir -p ${PALWORLD_DIR}
        cd ${STEAMCMD_DIR}
        ./steamcmd.sh +force_install_dir ${PALWORLD_DIR} +login anonymous +app_update ${APP_ID} validate +quit
    "

    echo -e "${GREEN}✓ Palworld server installed ($(du -sh ${PALWORLD_DIR} | cut -f1))${NC}"
}

# Full installation
do_install() {
    check_root
    show_banner
    echo -e "${CYAN}Starting full installation...${NC}"
    echo ""

    detect_os
    create_steam_user
    install_dependencies
    install_steamcmd
    install_palworld
    auto_open_ports

    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════╗"
    echo -e "║          Installation Complete! 🎉         ║"
    echo -e "╚════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "Start server: ${CYAN}sudo bash palworld.sh start${NC}"
    echo -e "Check status: ${CYAN}sudo bash palworld.sh status${NC}"
    echo -e "Show menu:    ${CYAN}sudo bash palworld.sh menu${NC}"
    echo ""
}

# Start server
do_start() {
    check_steam_user start

    if screen -list | grep -q "$SCREEN_NAME"; then
        echo -e "${YELLOW}⚠ Server is already running${NC}"
        exit 0
    fi

    if [ ! -d "$PALWORLD_DIR" ]; then
        echo -e "${RED}✗ Server not installed. Run: sudo bash palworld.sh install${NC}"
        exit 1
    fi

    echo -e "${BLUE}🚀 Starting Palworld server...${NC}"
    cd "$PALWORLD_DIR"
    screen -dmS "$SCREEN_NAME" ./PalServer.sh
    sleep 2

    if screen -list | grep -q "$SCREEN_NAME"; then
        echo -e "${GREEN}✓ Server started successfully!${NC}"
        echo ""
        echo -e "View console:  ${CYAN}screen -r $SCREEN_NAME${NC}"
        echo -e "Detach:        ${CYAN}Ctrl+A then D${NC}"
        echo -e "Stop server:   ${CYAN}sudo bash palworld.sh stop${NC}"
    else
        echo -e "${RED}✗ Failed to start server${NC}"
        exit 1
    fi
}

# Stop server
do_stop() {
    check_steam_user stop

    if ! screen -list | grep -q "$SCREEN_NAME"; then
        echo -e "${YELLOW}⚠ Server is not running${NC}"
        exit 0
    fi

    echo -e "${BLUE}🛑 Stopping Palworld server...${NC}"
    screen -S "$SCREEN_NAME" -X quit
    sleep 2

    if ! screen -list | grep -q "$SCREEN_NAME"; then
        echo -e "${GREEN}✓ Server stopped${NC}"
    else
        echo -e "${RED}✗ Failed to stop server${NC}"
        exit 1
    fi
}

# Restart server
do_restart() {
    echo -e "${BLUE}🔄 Restarting Palworld server...${NC}"
    do_stop
    sleep 3
    do_start
}

# Update server
do_update() {
    check_steam_user update

    echo -e "${BLUE}📥 Updating Palworld server...${NC}"

    # Stop if running
    if screen -list | grep -q "$SCREEN_NAME"; then
        echo "  Stopping server..."
        screen -S "$SCREEN_NAME" -X quit
        sleep 3
    fi

    cd "$STEAMCMD_DIR"
    ./steamcmd.sh +force_install_dir "$PALWORLD_DIR" +login anonymous +app_update "$APP_ID" validate +quit

    echo -e "${GREEN}✓ Update complete!${NC}"
    echo -e "Start server: ${CYAN}sudo bash palworld.sh start${NC}"
}

# Show status
do_status() {
    show_banner
    echo -e "${CYAN}Server Status:${NC}"
    echo ""

    # Check if installed
    if [ -d "$PALWORLD_DIR" ]; then
        echo -e "Installation: ${GREEN}✓ Installed${NC}"
        echo -e "Location:     ${PALWORLD_DIR}"
        echo -e "Size:         $(du -sh $PALWORLD_DIR 2>/dev/null | cut -f1)"
    else
        echo -e "Installation: ${RED}✗ Not installed${NC}"
        echo ""
        echo -e "Run: ${CYAN}sudo bash palworld.sh install${NC}"
        exit 1
    fi

    echo ""

    # Check if running
    if screen -list 2>/dev/null | grep -q "$SCREEN_NAME"; then
        echo -e "Server:       ${GREEN}✓ Running${NC}"
        echo -e "Screen:       ${SCREEN_NAME}"

        # Try to get process info
        PID=$(screen -list | grep "$SCREEN_NAME" | awk -F'[.]' '{print $1}' | tr -d '[:space:]')
        if [ -n "$PID" ]; then
            echo -e "PID:          ${PID}"
        fi
    else
        echo -e "Server:       ${RED}✗ Stopped${NC}"
    fi

    echo ""

    # Check ports
    echo -e "${CYAN}Network Ports:${NC}"
    if command -v netstat > /dev/null 2>&1; then
        if netstat -tuln 2>/dev/null | grep -q ":8211"; then
            echo -e "8211/UDP:     ${GREEN}✓ Listening${NC}"
        else
            echo -e "8211/UDP:     ${YELLOW}⚠ Not listening${NC}"
        fi
    else
        echo -e "Port check:   ${YELLOW}⚠ netstat not available${NC}"
    fi

    echo ""
    echo -e "${CYAN}Quick Commands:${NC}"
    if screen -list 2>/dev/null | grep -q "$SCREEN_NAME"; then
        echo -e "Stop:         ${CYAN}sudo bash palworld.sh stop${NC}"
        echo -e "Restart:      ${CYAN}sudo bash palworld.sh restart${NC}"
        echo -e "Console:      ${CYAN}screen -r $SCREEN_NAME${NC}"
    else
        echo -e "Start:        ${CYAN}sudo bash palworld.sh start${NC}"
        echo -e "Update:       ${CYAN}sudo bash palworld.sh update${NC}"
    fi
    echo ""
}

# Show logs
do_logs() {
    check_steam_user logs

    LOG_DIR="$PALWORLD_DIR/Pal/Saved/Logs"

    if [ ! -d "$LOG_DIR" ]; then
        echo -e "${RED}✗ Log directory not found${NC}"
        exit 1
    fi

    LATEST_LOG=$(ls -t "$LOG_DIR"/*.log 2>/dev/null | head -1)

    if [ -z "$LATEST_LOG" ]; then
        echo -e "${YELLOW}⚠ No logs found${NC}"
        exit 0
    fi

    echo -e "${BLUE}📄 Showing latest log (Ctrl+C to exit):${NC}"
    echo -e "${YELLOW}$LATEST_LOG${NC}"
    echo ""
    tail -f "$LATEST_LOG"
}

# Console access
do_console() {
    check_steam_user console

    if ! screen -list | grep -q "$SCREEN_NAME"; then
        echo -e "${RED}✗ Server is not running${NC}"
        exit 1
    fi

    echo -e "${GREEN}Attaching to server console...${NC}"
    echo -e "${YELLOW}Press Ctrl+A then D to detach${NC}"
    sleep 2
    screen -r "$SCREEN_NAME"
}

# Interactive menu
show_menu() {
    while true; do
        show_banner

        # Show current status
        if screen -list 2>/dev/null | grep -q "$SCREEN_NAME"; then
            echo -e "Status: ${GREEN}● Running${NC}"
        else
            echo -e "Status: ${RED}● Stopped${NC}"
        fi
        echo ""

        echo -e "${CYAN}╔════════════════════════════════════════════╗"
        echo -e "║              Main Menu                     ║"
        echo -e "╚════════════════════════════════════════════╝${NC}"
        echo ""
        echo -e "${GREEN}Server Management:${NC}"
        echo "  1) Start Server"
        echo "  2) Stop Server"
        echo "  3) Restart Server"
        echo "  4) Server Status"
        echo "  5) View Console (live)"
        echo "  6) View Logs (tail -f)"
        echo ""
        echo -e "${BLUE}Installation & Updates:${NC}"
        echo "  7) Install/Reinstall Server"
        echo "  8) Update Server"
        echo "  9) Open Firewall Ports"
        echo ""
        echo -e "${YELLOW}Configuration:${NC}"
        echo "  10) Edit Server Config"
        echo "  11) Show Server Info"
        echo ""
        echo -e "${RED}Other:${NC}"
        echo "  12) Uninstall Server"
        echo "  0) Exit"
        echo ""
        read -p "Enter your choice [0-12]: " choice

        case $choice in
            1) do_start; read -p "Press Enter to continue..." ;;
            2) do_stop; read -p "Press Enter to continue..." ;;
            3) do_restart; read -p "Press Enter to continue..." ;;
            4) do_status; read -p "Press Enter to continue..." ;;
            5) do_console ;;
            6) do_logs ;;
            7) do_install; read -p "Press Enter to continue..." ;;
            8) do_update; read -p "Press Enter to continue..." ;;
            9) check_root; auto_open_ports; read -p "Press Enter to continue..." ;;
            10)
                CONFIG="${PALWORLD_DIR}/Pal/Saved/Config/LinuxServer/PalWorldSettings.ini"
                if [ -f "$CONFIG" ]; then
                    nano "$CONFIG"
                else
                    echo -e "${YELLOW}Config not found. Server may need to run once first.${NC}"
                    read -p "Press Enter to continue..."
                fi
                ;;
            11) do_status; read -p "Press Enter to continue..." ;;
            12)
                echo -e "${RED}⚠ WARNING: This will delete the server!${NC}"
                read -p "Type 'yes' to confirm: " confirm
                if [ "$confirm" = "yes" ]; then
                    do_stop 2>/dev/null || true
                    rm -rf "$PALWORLD_DIR"
                    echo -e "${GREEN}✓ Server uninstalled${NC}"
                fi
                read -p "Press Enter to continue..."
                ;;
            0) echo -e "${GREEN}Goodbye!${NC}"; exit 0 ;;
            *) echo -e "${RED}Invalid option${NC}"; sleep 2 ;;
        esac
    done
}

# Show help
show_help() {
    echo "Palworld Dedicated Server - All-in-One Manager"
    echo ""
    echo "Usage: sudo bash palworld.sh [command]"
    echo ""
    echo "Commands:"
    echo "  install       Full installation (SteamCMD + Palworld)"
    echo "  start         Start the server"
    echo "  stop          Stop the server"
    echo "  restart       Restart the server"
    echo "  status        Show server status"
    echo "  update        Update server to latest version"
    echo "  console       Attach to server console"
    echo "  logs          View server logs (tail -f)"
    echo "  ports         Open firewall ports"
    echo "  menu          Show interactive menu (default)"
    echo "  help          Show this help"
    echo ""
    echo "Examples:"
    echo "  sudo bash palworld.sh install    # First time installation"
    echo "  sudo bash palworld.sh start      # Start server"
    echo "  sudo bash palworld.sh status     # Check if running"
    echo "  sudo bash palworld.sh menu       # Interactive menu"
    echo ""
}

# Main logic
main() {
    case "${1:-menu}" in
        install)
            do_install
            ;;
        start)
            do_start
            ;;
        stop)
            do_stop
            ;;
        restart)
            do_restart
            ;;
        status)
            do_status
            ;;
        update)
            do_update
            ;;
        console)
            do_console
            ;;
        logs)
            do_logs
            ;;
        ports)
            check_root
            auto_open_ports
            ;;
        menu)
            show_menu
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            echo -e "${RED}Unknown command: $1${NC}"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# Run main
main "$@"
