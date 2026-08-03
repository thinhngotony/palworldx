#!/bin/bash
#
# Palworld Dedicated Server - All-in-One Manager
# Repository: https://github.com/thinhngotony/palworldx
# Usage: sudo bash palworld.sh [command] [--yes]
# Lifecycle commands stop/restart/update prompt before interrupting a running server.
# For automation, pass --yes only after independently verifying interruption is safe.
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
#
# Defaults are intentionally preserved. Deployments may provide a root-owned,
# line-oriented config at /etc/palworld/palworld.conf or use PALWORLD_* env vars.
# Values are parsed as data (never eval'd), then validated before use.
CONFIG_FILE="${PALWORLD_CONFIG_FILE:-/etc/palworld/palworld.conf}"
STEAM_USER="steam"
STEAM_HOME="/home/steam"
STEAMCMD_DIR="/home/steam/steamcmd"
PALWORLD_DIR="/home/steam/palworld-server"
SCREEN_NAME="palworld"
DASHBOARD_PORT="8080"
DASHBOARD_FILE="/home/steam/dashboard.py"
LIFECYCLE_LOCK_FILE="/home/steam/.palworld-lifecycle.lock"
APP_ID="2394010"

load_deployment_config() {
    local line key value
    [ -e "$CONFIG_FILE" ] || return 0
    [ -f "$CONFIG_FILE" ] && [ -r "$CONFIG_FILE" ] || { echo "Configuration must be a readable regular file: $CONFIG_FILE" >&2; return 1; }
    if [ "${CONFIG_FILE#/etc/}" != "$CONFIG_FILE" ] && [ "$(stat -c '%U' "$CONFIG_FILE" 2>/dev/null)" != "root" ]; then
        echo "Configuration under /etc must be owned by root: $CONFIG_FILE" >&2
        return 1
    fi

    while IFS= read -r line || [ -n "$line" ]; do
        line="${line#${line%%[![:space:]]*}}"
        [ -z "$line" ] || [ "${line:0:1}" = "#" ] && continue
        if [[ "$line" != *=* ]]; then
            echo "Invalid configuration line in $CONFIG_FILE" >&2
            return 1
        fi
        key="${line%%=*}"
        value="${line#*=}"
        value="${value#${value%%[![:space:]]*}}"
        value="${value%${value##*[![:space:]]}}"
        case "$value" in
            \"*\") value="${value:1:${#value}-2}" ;;
            \'*\') value="${value:1:${#value}-2}" ;;
        esac
        case "$key" in
            STEAM_USER) STEAM_USER="$value" ;;
            STEAM_HOME) STEAM_HOME="$value" ;;
            STEAMCMD_DIR) STEAMCMD_DIR="$value" ;;
            PALWORLD_DIR) PALWORLD_DIR="$value" ;;
            SCREEN_NAME) SCREEN_NAME="$value" ;;
            DASHBOARD_PORT) DASHBOARD_PORT="$value" ;;
            DASHBOARD_FILE) DASHBOARD_FILE="$value" ;;
            LIFECYCLE_LOCK_FILE) LIFECYCLE_LOCK_FILE="$value" ;;
            APP_ID) APP_ID="$value" ;;
            *) echo "Unknown configuration key '$key' in $CONFIG_FILE" >&2; return 1 ;;
        esac
    done < "$CONFIG_FILE"
}

validate_deployment_config() {
    local path
    [[ "$STEAM_USER" =~ ^[a-z_][a-z0-9_-]*[$]?$ ]] || { echo "Invalid STEAM_USER" >&2; return 1; }
    [[ "$SCREEN_NAME" =~ ^[A-Za-z0-9_.-]+$ ]] || { echo "Invalid SCREEN_NAME" >&2; return 1; }
    [[ "$APP_ID" =~ ^[0-9]+$ ]] || { echo "Invalid APP_ID" >&2; return 1; }
    [[ "$DASHBOARD_PORT" =~ ^[0-9]+$ ]] && [ "$DASHBOARD_PORT" -ge 1 ] && [ "$DASHBOARD_PORT" -le 65535 ] || { echo "Invalid DASHBOARD_PORT" >&2; return 1; }
    for path in "$STEAM_HOME" "$STEAMCMD_DIR" "$PALWORLD_DIR" "$DASHBOARD_FILE" "$LIFECYCLE_LOCK_FILE"; do
        [[ "$path" = /* && "$path" != *$'\n'* && "$path" != *$'\r'* ]] || { echo "Invalid runtime path: $path" >&2; return 1; }
    done
}

load_deployment_config
# Environment variables override the deployment file, which makes one-off
# read-only discovery/status checks possible without editing production config.
[ -n "${PALWORLD_STEAM_USER:-}" ] && STEAM_USER="$PALWORLD_STEAM_USER"
[ -n "${PALWORLD_STEAM_HOME:-}" ] && STEAM_HOME="$PALWORLD_STEAM_HOME"
[ -n "${PALWORLD_STEAMCMD_DIR:-}" ] && STEAMCMD_DIR="$PALWORLD_STEAMCMD_DIR"
[ -n "${PALWORLD_SERVER_ROOT:-}" ] && PALWORLD_DIR="$PALWORLD_SERVER_ROOT"
[ -n "${PALWORLD_SCREEN_NAME:-}" ] && SCREEN_NAME="$PALWORLD_SCREEN_NAME"
[ -n "${PALWORLD_DASHBOARD_PORT:-}" ] && DASHBOARD_PORT="$PALWORLD_DASHBOARD_PORT"
[ -n "${PALWORLD_DASHBOARD_FILE:-}" ] && DASHBOARD_FILE="$PALWORLD_DASHBOARD_FILE"
[ -n "${PALWORLD_LIFECYCLE_LOCK_FILE:-}" ] && LIFECYCLE_LOCK_FILE="$PALWORLD_LIFECYCLE_LOCK_FILE"
validate_deployment_config

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

# Check if server screen session is running (works from any user)
is_server_running() {
    su - "$STEAM_USER" -c "screen -list 2>/dev/null" | grep -Eq "[.]${SCREEN_NAME}[[:space:]]+(Detached|Attached)"
}

# Serialize operations that can change the server lifecycle.
acquire_lifecycle_lock() {
    exec 9>"$LIFECYCLE_LOCK_FILE"
    if ! flock -n 9; then
        echo -e "${YELLOW}⚠ Another server lifecycle operation is already running${NC}" >&2
        exec 9>&-
        return 1
    fi
}

release_lifecycle_lock() {
    flock -u 9 2>/dev/null || true
    exec 9>&-
}

# Interrupting operations require an explicit confirmation. Use --yes only for
# automated callers that have independently verified it is safe to interrupt.
confirm_lifecycle_interrupt() {
    local operation="$1"
    local confirmation_mode="${2:-}"

    if ! screen -list 2>/dev/null | grep -Eq "[.]${SCREEN_NAME}[[:space:]]+(Detached|Attached)"; then
        return 0
    fi

    if [ "$confirmation_mode" = "--yes" ]; then
        echo -e "${YELLOW}Proceeding with $operation because --yes was explicitly supplied.${NC}"
        return 0
    fi

    if [ ! -t 0 ] || [ ! -t 1 ]; then
        echo -e "${RED}✗ Refusing to interrupt the running server non-interactively.${NC}" >&2
        echo "Use '$0 $operation --yes' only after verifying interruption is safe." >&2
        return 1
    fi

    read -r -p "The server is running and will be interrupted by $operation. Type 'yes' to continue: " confirmation
    if [ "$confirmation" != "yes" ]; then
        echo -e "${YELLOW}Operation cancelled.${NC}"
        return 1
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
    local internal="${1:-}"
    check_steam_user start "$internal"

    if [ "$internal" != "--internal" ]; then
        acquire_lifecycle_lock || exit 1
    fi

    if is_server_running; then
        echo -e "${YELLOW}⚠ Server is already running${NC}"
        [ "$internal" != "--internal" ] && release_lifecycle_lock
        return 0
    fi

    if [ ! -d "$PALWORLD_DIR" ]; then
        echo -e "${RED}✗ Server not installed. Run: sudo bash palworld.sh install${NC}"
        [ "$internal" != "--internal" ] && release_lifecycle_lock
        return 1
    fi

    echo -e "${BLUE}🚀 Starting Palworld server...${NC}"
    cd "$PALWORLD_DIR"
    screen -dmS "$SCREEN_NAME" ./PalServer.sh
    sleep 2

    if is_server_running; then
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
    local confirmation_mode="${1:-}"
    local internal="${2:-}"
    check_steam_user stop "$confirmation_mode" "$internal"

    if [ "$internal" != "--internal" ]; then
        acquire_lifecycle_lock || exit 1
    fi

    if ! is_server_running; then
        echo -e "${YELLOW}⚠ Server is not running${NC}"
        [ "$internal" != "--internal" ] && release_lifecycle_lock
        return 0
    fi

    if [ "$confirmation_mode" != "--confirmed" ] && ! confirm_lifecycle_interrupt "stop" "$confirmation_mode"; then
        [ "$internal" != "--internal" ] && release_lifecycle_lock
        return 1
    fi

    echo -e "${BLUE}🛑 Stopping Palworld server...${NC}"
    screen -S "$SCREEN_NAME" -X quit
    sleep 2

    if ! is_server_running; then
        echo -e "${GREEN}✓ Server stopped${NC}"
    else
        echo -e "${RED}✗ Failed to stop server${NC}"
        return 1
    fi
}

# Restart server
do_restart() {
    local confirmation_mode="${1:-}"
    check_steam_user restart "$confirmation_mode"
    acquire_lifecycle_lock || exit 1
    trap release_lifecycle_lock RETURN

    if ! confirm_lifecycle_interrupt "restart" "$confirmation_mode"; then
        return 1
    fi

    echo -e "${BLUE}🔄 Restarting Palworld server...${NC}"
    do_stop --confirmed --internal
    sleep 3
    do_start --internal
}

# Update server
do_update() {
    local confirmation_mode="${1:-}"
    check_steam_user update "$confirmation_mode"
    acquire_lifecycle_lock || exit 1
    trap release_lifecycle_lock RETURN

    if ! confirm_lifecycle_interrupt "update" "$confirmation_mode"; then
        return 1
    fi

    echo -e "${BLUE}📥 Updating Palworld server...${NC}"

    if is_server_running; then
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
    if is_server_running; then
        echo -e "Server:       ${GREEN}✓ Running${NC}"
        echo -e "Screen:       ${SCREEN_NAME}"

        # Try to get process info
        PID=$(su - "$STEAM_USER" -c "screen -list" | grep -E "[.]${SCREEN_NAME}[[:space:]]+(Detached|Attached)" | awk -F'[.]' '{print $1}' | tr -d '[:space:]')
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
    if is_server_running; then
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

    if ! is_server_running; then
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
        if is_server_running; then
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
        echo -e "${MAGENTA}Web Interface:${NC}"
        echo "  12) 🌐 Launch Web Dashboard"
        echo ""
        echo -e "${RED}Other:${NC}"
        echo "  13) Uninstall Server"
        echo "  0) Exit"
        echo ""
        read -p "Enter your choice [0-13]: " choice

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
            12) check_root; do_dashboard ;;
            13)
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

# Start web dashboard
do_dashboard() {
    echo -e "${BLUE}🌐 Starting Web Dashboard...${NC}"
    echo ""

    # Check if Python3 is installed
    if ! command -v python3 > /dev/null 2>&1; then
        echo -e "${RED}✗ Python3 not found${NC}"
        echo "Installing Python3..."
        apt-get update -qq
        apt-get install -y python3 > /dev/null 2>&1
    fi

    # Check if dashboard.py exists
    if [ ! -f "$DASHBOARD_FILE" ]; then
        echo -e "${RED}✗ dashboard.py not found at ${DASHBOARD_FILE}${NC}"
        echo "Please download it from the repository"
        exit 1
    fi

    # Open dashboard port
    echo "Opening port ${DASHBOARD_PORT} for dashboard..."
    if command -v ufw > /dev/null 2>&1; then
        ufw allow "${DASHBOARD_PORT}/tcp" comment 'Palworld Dashboard' 2>/dev/null || true
    elif command -v iptables > /dev/null 2>&1; then
        iptables -C INPUT -p tcp --dport "$DASHBOARD_PORT" -j ACCEPT 2>/dev/null || iptables -A INPUT -p tcp --dport "$DASHBOARD_PORT" -j ACCEPT
    fi

    echo ""
    echo -e "${GREEN}✓ Dashboard starting...${NC}"
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}🌐 Web Dashboard Access:${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "  URL:      ${CYAN}http://YOUR_SERVER_IP:${DASHBOARD_PORT}${NC}"
    echo -e "  Password: ${YELLOW}admin${NC} (default - change in dashboard.py)"
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${YELLOW}Press Ctrl+C to stop the dashboard${NC}"
    echo ""

    # Run dashboard
    cd "$(dirname "$DASHBOARD_FILE")"
    python3 - "$DASHBOARD_PORT" "$DASHBOARD_FILE" <<'PY'
import importlib.util
import sys

port = int(sys.argv[1])
module_path = sys.argv[2]
spec = importlib.util.spec_from_file_location("palworld_dashboard", module_path)
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)
dashboard.DASHBOARD_PORT = port
server = dashboard.ThreadedHTTPServer(("0.0.0.0", port), dashboard.DashboardHandler)
try:
    server.serve_forever()
except KeyboardInterrupt:
    server.server_close()
PY
}

# Read-only discovery/status commands do not acquire lifecycle locks or change state.
do_discover() {
    printf 'steam_user=%s\nsteam_home=%s\nsteamcmd_dir=%s\nserver_root=%s\nscreen_name=%s\ndashboard_port=%s\ndashboard_file=%s\nlifecycle_lock=%s\ninstalled=%s\nrunning=%s\n' \
        "$STEAM_USER" "$STEAM_HOME" "$STEAMCMD_DIR" "$PALWORLD_DIR" "$SCREEN_NAME" "$DASHBOARD_PORT" "$DASHBOARD_FILE" "$LIFECYCLE_LOCK_FILE" \
        "$([ -d "$PALWORLD_DIR" ] && printf true || printf false)" "$(if is_server_running; then printf true; else printf false; fi)"
}

# Command-line lifecycle commands retain the existing menu for all other invocations.
if [ "$#" -gt 0 ]; then
    case "$1" in
        start) do_start "${2:-}" ;;
        stop) do_stop "${2:-}" ;;
        restart) do_restart "${2:-}" ;;
        update) do_update "${2:-}" ;;
        status) do_status ;;
        discover|config) do_discover ;;
        *) show_menu ;;
    esac
else
    show_menu
fi
