#!/usr/bin/env python3
"""
Palworld Server Web Dashboard
Zero-dependency real-time monitoring and control interface
Uses only Python standard library (no Flask needed)
"""

import os
import json
import subprocess
import hashlib
import secrets
import time
import threading
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from datetime import datetime

# Configuration
STEAM_USER = "steam"
STEAM_HOME = f"/home/{STEAM_USER}"
PALWORLD_DIR = f"{STEAM_HOME}/palworld-server"
SCREEN_NAME = "palworld"
DASHBOARD_PORT = 8080
DEFAULT_PASSWORD = "admin"  # Change this!
PASSWORD_HASH = hashlib.sha256(DEFAULT_PASSWORD.encode()).hexdigest()

# Session storage
sessions = {}
SESSION_TIMEOUT = 3600  # 1 hour

# Command history for the terminal
command_history = []


def generate_session_id():
    return secrets.token_hex(32)


def validate_session(cookie_header):
    if not cookie_header:
        return False
    cookie = SimpleCookie()
    cookie.load(cookie_header)
    if 'session_id' in cookie:
        sid = cookie['session_id'].value
        if sid in sessions:
            if time.time() - sessions[sid]['created'] < SESSION_TIMEOUT:
                return True
            else:
                del sessions[sid]
    return False


def run_command(cmd, timeout_sec=10):
    """Run shell command and return output"""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout_sec
        )
        return result.stdout.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "Command timed out", 1
    except Exception as e:
        return str(e), 1


def is_server_running():
    output, _ = run_command(f"su - {STEAM_USER} -c 'screen -list 2>/dev/null' | grep {SCREEN_NAME}")
    return SCREEN_NAME in output


def get_server_pid():
    """Get the actual PalServer process PID"""
    output, code = run_command("pgrep -f PalServer-Linux-Shipping 2>/dev/null || pgrep -f PalServer 2>/dev/null")
    if code == 0 and output:
        return output.split('\n')[0].strip()
    return None


def get_server_stats():
    stats = {
        'running': is_server_running(),
        'uptime': 'N/A',
        'cpu': 0.0,
        'ram': 0.0,
        'ram_mb': 0,
        'players': 0,
        'port': 8211,
        'version': 'Unknown',
        'size': 'Unknown',
        'pid': None,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    if stats['running']:
        pid = get_server_pid()
        if pid:
            stats['pid'] = pid
            cpu_output, _ = run_command(f"ps -p {pid} -o %cpu --no-headers 2>/dev/null")
            ram_output, _ = run_command(f"ps -p {pid} -o %mem --no-headers 2>/dev/null")
            rss_output, _ = run_command(f"ps -p {pid} -o rss --no-headers 2>/dev/null")
            start_output, _ = run_command(f"ps -p {pid} -o etime= 2>/dev/null")

            try:
                stats['cpu'] = float(cpu_output.strip())
            except (ValueError, AttributeError):
                pass
            try:
                stats['ram'] = float(ram_output.strip())
            except (ValueError, AttributeError):
                pass
            try:
                stats['ram_mb'] = int(rss_output.strip()) // 1024
            except (ValueError, AttributeError):
                pass
            if start_output:
                stats['uptime'] = start_output.strip()

    if os.path.exists(PALWORLD_DIR):
        size_output, _ = run_command(f"du -sh {PALWORLD_DIR} 2>/dev/null | cut -f1")
        stats['size'] = size_output or 'Unknown'

    return stats


def get_system_info():
    info = {}
    cpu_output, _ = run_command("grep -c ^processor /proc/cpuinfo")
    info['cpu_cores'] = cpu_output or 'Unknown'

    cpu_model, _ = run_command("grep 'model name' /proc/cpuinfo | head -1 | cut -d: -f2")
    info['cpu_model'] = cpu_model.strip() if cpu_model else 'Unknown'

    mem_output, _ = run_command("free -h | grep Mem | awk '{print $2}'")
    info['total_ram'] = mem_output or 'Unknown'

    mem_used, _ = run_command("free -h | grep Mem | awk '{print $3}'")
    info['used_ram'] = mem_used or 'Unknown'

    mem_pct, _ = run_command("free | grep Mem | awk '{printf \"%.1f\", $3/$2*100}'")
    info['ram_percent'] = float(mem_pct) if mem_pct else 0

    disk_output, _ = run_command("df -h / | tail -1 | awk '{print $2}'")
    info['total_disk'] = disk_output or 'Unknown'

    disk_used, _ = run_command("df -h / | tail -1 | awk '{print $3}'")
    info['used_disk'] = disk_used or 'Unknown'

    disk_pct, _ = run_command("df / | tail -1 | awk '{print $5}' | tr -d '%'")
    info['disk_percent'] = float(disk_pct) if disk_pct else 0

    sys_cpu, _ = run_command("top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1")
    info['sys_cpu_percent'] = float(sys_cpu) if sys_cpu else 0

    os_output, _ = run_command("cat /etc/os-release | grep PRETTY_NAME | cut -d'\"' -f2")
    info['os'] = os_output or 'Unknown'

    uptime_output, _ = run_command("uptime -p 2>/dev/null || uptime")
    info['sys_uptime'] = uptime_output or 'Unknown'

    load_output, _ = run_command("cat /proc/loadavg | awk '{print $1, $2, $3}'")
    info['load_avg'] = load_output or 'Unknown'

    hostname_output, _ = run_command("hostname")
    info['hostname'] = hostname_output or 'Unknown'

    ip_output, _ = run_command("hostname -I 2>/dev/null | awk '{print $1}'")
    info['ip'] = ip_output or 'Unknown'

    return info


def get_recent_logs(lines=100):
    log_dir = f"{PALWORLD_DIR}/Pal/Saved/Logs"
    if not os.path.exists(log_dir):
        return "No logs available - server may not have been started yet."
    output, _ = run_command(
        f"ls -t {log_dir}/*.log 2>/dev/null | head -1 | xargs tail -n {lines} 2>/dev/null || echo 'No log files found'"
    )
    return output


def get_config():
    """Read PalWorldSettings.ini"""
    config_path = f"{PALWORLD_DIR}/Pal/Saved/Config/LinuxServer/PalWorldSettings.ini"
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return f.read()
    return "Config file not found. Start the server once to generate it."


def save_config(content):
    """Save PalWorldSettings.ini"""
    config_path = f"{PALWORLD_DIR}/Pal/Saved/Config/LinuxServer/PalWorldSettings.ini"
    config_dir = os.path.dirname(config_path)
    if not os.path.exists(config_dir):
        os.makedirs(config_dir, exist_ok=True)
    with open(config_path, 'w') as f:
        f.write(content)
    return True


def get_backup_list():
    """List available backups"""
    backup_dir = f"{PALWORLD_DIR}/Pal/Saved/SaveGames"
    if not os.path.exists(backup_dir):
        return []
    output, _ = run_command(f"find {backup_dir} -name '*.sav' -type f -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -20")
    backups = []
    for line in output.split('\n'):
        if line.strip():
            parts = line.split(' ', 1)
            if len(parts) == 2:
                ts = float(parts[0])
                path = parts[1]
                backups.append({
                    'path': path,
                    'name': os.path.basename(path),
                    'date': datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S'),
                    'size': os.path.getsize(path) if os.path.exists(path) else 0
                })
    return backups


def get_network_info():
    """Get network/port status"""
    info = {
        'game_port': False,
        'query_port': False,
        'rcon_port': False,
    }
    netstat, _ = run_command("ss -tuln 2>/dev/null || netstat -tuln 2>/dev/null")
    if ':8211' in netstat:
        info['game_port'] = True
    if ':27015' in netstat:
        info['query_port'] = True
    if ':25575' in netstat:
        info['rcon_port'] = True
    return info


# ─── HTML Templates ───

LOGIN_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Login - Palworld Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
body{font-family:'Inter',system-ui,-apple-system,sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;
background:#0f0f1a;background-image:radial-gradient(ellipse at 20% 50%,rgba(88,80,236,0.15),transparent 50%),radial-gradient(ellipse at 80% 50%,rgba(124,58,237,0.1),transparent 50%)}
.login-container{width:100%;max-width:420px;padding:20px}
.login-card{background:rgba(22,22,40,0.9);border:1px solid rgba(255,255,255,0.06);border-radius:24px;padding:48px 40px;backdrop-filter:blur(40px);box-shadow:0 25px 60px rgba(0,0,0,0.4)}
.logo{text-align:center;margin-bottom:36px}
.logo-icon{width:72px;height:72px;background:linear-gradient(135deg,#5850ec,#7c3aed);border-radius:20px;display:inline-flex;align-items:center;justify-content:center;font-size:36px;margin-bottom:16px;box-shadow:0 8px 24px rgba(88,80,236,0.3)}
.logo h1{color:#fff;font-size:22px;font-weight:600;letter-spacing:-0.5px}
.logo p{color:rgba(255,255,255,0.4);font-size:13px;margin-top:4px}
.form-group{margin-bottom:20px}
.form-group label{display:block;color:rgba(255,255,255,0.6);font-size:13px;font-weight:500;margin-bottom:8px}
.form-group input{width:100%;padding:14px 16px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.08);border-radius:12px;color:#fff;font-size:15px;font-family:inherit;transition:all .2s}
.form-group input:focus{outline:none;border-color:#5850ec;background:rgba(88,80,236,0.08);box-shadow:0 0 0 3px rgba(88,80,236,0.15)}
.btn-login{width:100%;padding:14px;background:linear-gradient(135deg,#5850ec,#7c3aed);color:#fff;border:none;border-radius:12px;font-size:15px;font-weight:600;cursor:pointer;transition:all .2s;font-family:inherit}
.btn-login:hover{transform:translateY(-1px);box-shadow:0 8px 24px rgba(88,80,236,0.4)}
.btn-login:active{transform:translateY(0)}
.error-msg{background:rgba(239,68,68,0.12);border:1px solid rgba(239,68,68,0.2);color:#f87171;padding:12px 16px;border-radius:10px;margin-bottom:20px;font-size:13px;text-align:center}
</style>
</head>
<body>
<div class="login-container">
<div class="login-card">
<div class="logo">
<div class="logo-icon">&#127918;</div>
<h1>Palworld Dashboard</h1>
<p>Server Management Console</p>
</div>
__ERROR__
<form method="POST" action="/login">
<div class="form-group">
<label>Password</label>
<input type="password" name="password" placeholder="Enter dashboard password" required autofocus>
</div>
<button type="submit" class="btn-login">Sign In</button>
</form>
</div>
</div>
</body>
</html>'''

DASHBOARD_HTML = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Palworld Server Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
:root{
--bg-primary:#0f0f1a;--bg-card:rgba(22,22,40,0.85);--bg-card-hover:rgba(30,30,52,0.9);
--border:rgba(255,255,255,0.06);--border-hover:rgba(255,255,255,0.12);
--text-primary:#fff;--text-secondary:rgba(255,255,255,0.6);--text-muted:rgba(255,255,255,0.35);
--accent:#5850ec;--accent-light:#7c6ef0;--accent-glow:rgba(88,80,236,0.3);
--green:#10b981;--green-glow:rgba(16,185,129,0.2);
--red:#ef4444;--red-glow:rgba(239,68,68,0.2);
--orange:#f59e0b;--orange-glow:rgba(245,158,11,0.2);
--blue:#3b82f6;--blue-glow:rgba(59,130,246,0.2);
--purple:#8b5cf6;
--radius:16px;--radius-sm:10px;--radius-xs:8px;
}
body{font-family:'Inter',system-ui,sans-serif;background:var(--bg-primary);color:var(--text-primary);min-height:100vh;
background-image:radial-gradient(ellipse at 20% 0%,rgba(88,80,236,0.08),transparent 50%),radial-gradient(ellipse at 80% 100%,rgba(124,58,237,0.06),transparent 50%)}
.app{display:flex;min-height:100vh}

/* Sidebar */
.sidebar{width:260px;background:rgba(15,15,30,0.95);border-right:1px solid var(--border);padding:20px 0;display:flex;flex-direction:column;position:fixed;height:100vh;z-index:100;transition:transform .3s}
.sidebar-brand{padding:8px 24px 28px;display:flex;align-items:center;gap:14px;border-bottom:1px solid var(--border)}
.brand-icon{width:42px;height:42px;background:linear-gradient(135deg,#5850ec,#7c3aed);border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:22px;flex-shrink:0}
.brand-text h2{font-size:16px;font-weight:600;letter-spacing:-0.3px}
.brand-text p{font-size:11px;color:var(--text-muted);margin-top:2px}
.nav{flex:1;padding:16px 12px;overflow-y:auto}
.nav-section{margin-bottom:20px}
.nav-section-title{font-size:10px;text-transform:uppercase;letter-spacing:1.5px;color:var(--text-muted);padding:0 12px;margin-bottom:8px;font-weight:600}
.nav-item{display:flex;align-items:center;gap:12px;padding:10px 14px;border-radius:var(--radius-sm);color:var(--text-secondary);cursor:pointer;transition:all .15s;font-size:13.5px;font-weight:500;margin-bottom:2px;user-select:none}
.nav-item:hover{background:rgba(255,255,255,0.04);color:var(--text-primary)}
.nav-item.active{background:rgba(88,80,236,0.12);color:#a5b4fc;border:1px solid rgba(88,80,236,0.15)}
.nav-item .icon{width:20px;text-align:center;font-size:16px;flex-shrink:0}
.nav-footer{padding:16px;border-top:1px solid var(--border)}
.server-status-pill{display:flex;align-items:center;gap:8px;padding:10px 14px;border-radius:var(--radius-sm);font-size:13px;font-weight:500}
.server-status-pill.online{background:rgba(16,185,129,0.1);color:var(--green);border:1px solid rgba(16,185,129,0.15)}
.server-status-pill.offline{background:rgba(239,68,68,0.1);color:var(--red);border:1px solid rgba(239,68,68,0.15)}
.status-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.status-dot.online{background:var(--green);box-shadow:0 0 8px var(--green-glow)}
.status-dot.offline{background:var(--red);box-shadow:0 0 8px var(--red-glow)}
.pulse{animation:pulse 2s ease-in-out infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}

/* Main */
.main{margin-left:260px;flex:1;padding:28px 32px;min-height:100vh}

/* Mobile menu button */
.mobile-menu-btn{display:none;position:fixed;top:16px;left:16px;z-index:200;width:40px;height:40px;background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius-xs);cursor:pointer;align-items:center;justify-content:center;font-size:20px;color:var(--text-primary)}
.sidebar-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:99}

/* Page header */
.page-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:28px;flex-wrap:wrap;gap:12px}
.page-title{font-size:24px;font-weight:700;letter-spacing:-0.5px}
.page-subtitle{color:var(--text-muted);font-size:13px;margin-top:4px}
.header-actions{display:flex;gap:8px;align-items:center}
.header-time{color:var(--text-muted);font-size:12px;font-family:'JetBrains Mono',monospace}

/* Cards */
.card{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);padding:24px;backdrop-filter:blur(20px);transition:all .2s}
.card:hover{border-color:var(--border-hover)}
.card-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:20px}
.card-title{font-size:14px;font-weight:600;color:var(--text-secondary);text-transform:uppercase;letter-spacing:0.5px}
.card-badge{font-size:11px;padding:4px 10px;border-radius:20px;font-weight:500}

/* Stats grid */
.stats-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px}
.stat-card{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);padding:22px;transition:all .2s}
.stat-card:hover{border-color:var(--border-hover);transform:translateY(-2px)}
.stat-icon{width:40px;height:40px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:20px;margin-bottom:14px}
.stat-icon.green{background:rgba(16,185,129,0.1);color:var(--green)}
.stat-icon.blue{background:rgba(59,130,246,0.1);color:var(--blue)}
.stat-icon.orange{background:rgba(245,158,11,0.1);color:var(--orange)}
.stat-icon.purple{background:rgba(139,92,246,0.1);color:var(--purple)}
.stat-icon.red{background:rgba(239,68,68,0.1);color:var(--red)}
.stat-value{font-size:26px;font-weight:700;letter-spacing:-1px;margin-bottom:4px}
.stat-label{font-size:12px;color:var(--text-muted);font-weight:500}
.stat-sub{font-size:11px;color:var(--text-muted);margin-top:6px;font-family:'JetBrains Mono',monospace}

/* Progress bars */
.progress-track{width:100%;height:6px;background:rgba(255,255,255,0.06);border-radius:3px;overflow:hidden;margin-top:12px}
.progress-fill{height:100%;border-radius:3px;transition:width .6s ease}
.progress-fill.green{background:linear-gradient(90deg,#10b981,#34d399)}
.progress-fill.blue{background:linear-gradient(90deg,#3b82f6,#60a5fa)}
.progress-fill.orange{background:linear-gradient(90deg,#f59e0b,#fbbf24)}
.progress-fill.red{background:linear-gradient(90deg,#ef4444,#f87171)}
.progress-fill.purple{background:linear-gradient(90deg,#8b5cf6,#a78bfa)}

/* Grid layouts */
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px}
.grid-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin-bottom:24px}

/* Controls */
.controls-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px}
.ctrl-btn{display:flex;align-items:center;justify-content:center;gap:10px;padding:14px 20px;border:1px solid var(--border);border-radius:var(--radius-sm);background:rgba(255,255,255,0.03);color:var(--text-primary);font-size:14px;font-weight:600;cursor:pointer;transition:all .2s;font-family:inherit}
.ctrl-btn:hover{transform:translateY(-1px);box-shadow:0 4px 16px rgba(0,0,0,0.3)}
.ctrl-btn:active{transform:translateY(0)}
.ctrl-btn:disabled{opacity:.4;cursor:not-allowed;transform:none!important;box-shadow:none!important}
.ctrl-btn .btn-icon{font-size:18px}
.ctrl-btn.start{border-color:rgba(16,185,129,0.3);background:rgba(16,185,129,0.08)}
.ctrl-btn.start:hover{background:rgba(16,185,129,0.15);border-color:rgba(16,185,129,0.5)}
.ctrl-btn.stop{border-color:rgba(239,68,68,0.3);background:rgba(239,68,68,0.08)}
.ctrl-btn.stop:hover{background:rgba(239,68,68,0.15);border-color:rgba(239,68,68,0.5)}
.ctrl-btn.restart{border-color:rgba(245,158,11,0.3);background:rgba(245,158,11,0.08)}
.ctrl-btn.restart:hover{background:rgba(245,158,11,0.15);border-color:rgba(245,158,11,0.5)}
.ctrl-btn.update{border-color:rgba(59,130,246,0.3);background:rgba(59,130,246,0.08)}
.ctrl-btn.update:hover{background:rgba(59,130,246,0.15);border-color:rgba(59,130,246,0.5)}

/* Info rows */
.info-row{display:flex;justify-content:space-between;align-items:center;padding:12px 0;border-bottom:1px solid rgba(255,255,255,0.04)}
.info-row:last-child{border-bottom:none}
.info-label{color:var(--text-muted);font-size:13px;font-weight:500}
.info-value{color:var(--text-primary);font-size:13px;font-weight:600;font-family:'JetBrains Mono',monospace}

/* Port status */
.port-status{display:flex;align-items:center;gap:8px;font-size:13px}
.port-dot{width:8px;height:8px;border-radius:50%}
.port-dot.open{background:var(--green)}
.port-dot.closed{background:var(--red)}

/* Terminal / Logs */
.terminal{background:#0d0d14;border:1px solid rgba(255,255,255,0.06);border-radius:var(--radius-sm);overflow:hidden}
.terminal-header{display:flex;align-items:center;justify-content:space-between;padding:10px 16px;background:rgba(255,255,255,0.03);border-bottom:1px solid rgba(255,255,255,0.06)}
.terminal-dots{display:flex;gap:6px}
.terminal-dot{width:10px;height:10px;border-radius:50%}
.terminal-dot.r{background:#ef4444}.terminal-dot.y{background:#f59e0b}.terminal-dot.g{background:#10b981}
.terminal-title{font-size:12px;color:var(--text-muted);font-family:'JetBrains Mono',monospace}
.terminal-body{padding:16px;font-family:'JetBrains Mono',monospace;font-size:12px;line-height:1.7;color:#a0aec0;max-height:450px;overflow-y:auto;white-space:pre-wrap;word-break:break-all}
.terminal-body::-webkit-scrollbar{width:6px}
.terminal-body::-webkit-scrollbar-track{background:transparent}
.terminal-body::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.1);border-radius:3px}

/* Config editor */
.config-editor{width:100%;min-height:350px;background:#0d0d14;border:1px solid rgba(255,255,255,0.08);border-radius:var(--radius-xs);color:#a0aec0;font-family:'JetBrains Mono',monospace;font-size:12.5px;line-height:1.7;padding:16px;resize:vertical}
.config-editor:focus{outline:none;border-color:var(--accent)}

/* Toast */
.toast-container{position:fixed;top:24px;right:24px;z-index:1000;display:flex;flex-direction:column;gap:8px}
.toast{padding:14px 20px;border-radius:var(--radius-sm);font-size:13px;font-weight:500;display:flex;align-items:center;gap:10px;animation:slideIn .3s ease;backdrop-filter:blur(20px);border:1px solid;min-width:280px;box-shadow:0 8px 32px rgba(0,0,0,0.3)}
.toast.success{background:rgba(16,185,129,0.15);border-color:rgba(16,185,129,0.2);color:#6ee7b7}
.toast.error{background:rgba(239,68,68,0.15);border-color:rgba(239,68,68,0.2);color:#fca5a5}
.toast.info{background:rgba(59,130,246,0.15);border-color:rgba(59,130,246,0.2);color:#93c5fd}
@keyframes slideIn{from{transform:translateX(100px);opacity:0}to{transform:translateX(0);opacity:1}}
@keyframes slideOut{from{transform:translateX(0);opacity:1}to{transform:translateX(100px);opacity:0}}

/* Loading spinner */
.spinner{width:16px;height:16px;border:2px solid rgba(255,255,255,0.2);border-top-color:#fff;border-radius:50%;animation:spin .6s linear infinite;display:inline-block}
@keyframes spin{to{transform:rotate(360deg)}}

/* Page sections (tabs) */
.page{display:none}
.page.active{display:block}

/* Responsive */
@media(max-width:1200px){.stats-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:900px){
.sidebar{transform:translateX(-100%)}
.sidebar.open{transform:translateX(0)}
.sidebar-overlay.show{display:block}
.mobile-menu-btn{display:flex}
.main{margin-left:0;padding:20px 16px;padding-top:64px}
.stats-grid{grid-template-columns:1fr 1fr}
.grid-2,.grid-3{grid-template-columns:1fr}
.page-title{font-size:20px}
}
@media(max-width:500px){
.stats-grid{grid-template-columns:1fr}
.controls-grid{grid-template-columns:1fr}
}

/* Scrollbar */
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.08);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:rgba(255,255,255,0.15)}

/* Logout btn */
.btn-logout{display:flex;align-items:center;gap:8px;padding:10px 14px;border-radius:var(--radius-sm);color:var(--text-muted);cursor:pointer;transition:all .15s;font-size:13px;font-weight:500;border:none;background:none;width:100%;font-family:inherit}
.btn-logout:hover{background:rgba(239,68,68,0.08);color:var(--red)}

/* Save button */
.btn-save{padding:10px 24px;background:linear-gradient(135deg,#5850ec,#7c3aed);color:#fff;border:none;border-radius:var(--radius-xs);font-size:13px;font-weight:600;cursor:pointer;transition:all .2s;font-family:inherit}
.btn-save:hover{box-shadow:0 4px 16px var(--accent-glow)}
.btn-save:disabled{opacity:.5;cursor:not-allowed}

/* Refresh button */
.btn-refresh{padding:6px 12px;background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:var(--radius-xs);color:var(--text-secondary);cursor:pointer;font-size:12px;font-family:inherit;transition:all .15s}
.btn-refresh:hover{background:rgba(255,255,255,0.08);border-color:var(--border-hover)}

/* Connection info */
.connect-box{background:rgba(88,80,236,0.08);border:1px solid rgba(88,80,236,0.15);border-radius:var(--radius-sm);padding:16px 20px;margin-bottom:16px}
.connect-label{font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--accent-light);margin-bottom:6px;font-weight:600}
.connect-value{font-size:18px;font-weight:700;font-family:'JetBrains Mono',monospace;color:#c7d2fe;letter-spacing:0.5px}
</style>
</head>
<body>

<button class="mobile-menu-btn" onclick="toggleSidebar()">&#9776;</button>
<div class="sidebar-overlay" id="sidebarOverlay" onclick="toggleSidebar()"></div>

<div class="app">
<!-- Sidebar -->
<aside class="sidebar" id="sidebar">
<div class="sidebar-brand">
<div class="brand-icon">&#127918;</div>
<div class="brand-text">
<h2>Palworld</h2>
<p>Server Dashboard</p>
</div>
</div>
<nav class="nav">
<div class="nav-section">
<div class="nav-section-title">Overview</div>
<div class="nav-item active" onclick="showPage('dashboard',this)">
<span class="icon">&#128200;</span> Dashboard
</div>
<div class="nav-item" onclick="showPage('controls',this)">
<span class="icon">&#127918;</span> Controls
</div>
</div>
<div class="nav-section">
<div class="nav-section-title">Monitor</div>
<div class="nav-item" onclick="showPage('logs',this)">
<span class="icon">&#128196;</span> Server Logs
</div>
<div class="nav-item" onclick="showPage('network',this)">
<span class="icon">&#128274;</span> Network
</div>
</div>
<div class="nav-section">
<div class="nav-section-title">Configure</div>
<div class="nav-item" onclick="showPage('config',this)">
<span class="icon">&#9881;</span> Settings
</div>
<div class="nav-item" onclick="showPage('backups',this)">
<span class="icon">&#128190;</span> Backups
</div>
</div>
<div class="nav-section">
<div class="nav-section-title">System</div>
<div class="nav-item" onclick="showPage('system',this)">
<span class="icon">&#128187;</span> System Info
</div>
</div>
</nav>
<div class="nav-footer">
<div class="server-status-pill offline" id="sidebarStatus">
<div class="status-dot offline" id="sidebarDot"></div>
<span id="sidebarStatusText">Checking...</span>
</div>
<button class="btn-logout" onclick="if(confirm('Logout?'))window.location='/logout'" style="margin-top:8px">
<span>&#x2192;</span> Sign Out
</button>
</div>
</aside>

<!-- Main content -->
<main class="main">

<!-- ═══ DASHBOARD PAGE ═══ -->
<div class="page active" id="page-dashboard">
<div class="page-header">
<div>
<div class="page-title">Dashboard</div>
<div class="page-subtitle">Real-time server monitoring</div>
</div>
<div class="header-actions">
<span class="header-time" id="clockDisplay"></span>
<button class="btn-refresh" onclick="refreshAll()">&#x21bb; Refresh</button>
</div>
</div>

<div class="stats-grid">
<div class="stat-card">
<div class="stat-icon green" id="statusIcon">&#9679;</div>
<div class="stat-value" id="statStatus">--</div>
<div class="stat-label">Server Status</div>
<div class="stat-sub" id="statUptime">--</div>
</div>
<div class="stat-card">
<div class="stat-icon blue">&#9881;</div>
<div class="stat-value" id="statCPU">--%</div>
<div class="stat-label">CPU Usage</div>
<div class="progress-track"><div class="progress-fill blue" id="cpuBar" style="width:0%"></div></div>
</div>
<div class="stat-card">
<div class="stat-icon purple">&#128204;</div>
<div class="stat-value" id="statRAM">--%</div>
<div class="stat-label">RAM Usage</div>
<div class="stat-sub" id="statRAMmb">-- MB</div>
<div class="progress-track"><div class="progress-fill purple" id="ramBar" style="width:0%"></div></div>
</div>
<div class="stat-card">
<div class="stat-icon orange">&#128101;</div>
<div class="stat-value" id="statPlayers">0</div>
<div class="stat-label">Players Online</div>
<div class="stat-sub">Port 8211/UDP</div>
</div>
</div>

<div class="grid-2">
<div class="card">
<div class="card-header">
<span class="card-title">Quick Controls</span>
</div>
<div class="controls-grid">
<button class="ctrl-btn start" id="qStart" onclick="serverAction('start')"><span class="btn-icon">&#9654;</span> Start</button>
<button class="ctrl-btn stop" id="qStop" onclick="serverAction('stop')"><span class="btn-icon">&#9724;</span> Stop</button>
<button class="ctrl-btn restart" id="qRestart" onclick="serverAction('restart')"><span class="btn-icon">&#8635;</span> Restart</button>
<button class="ctrl-btn update" id="qUpdate" onclick="serverAction('update')"><span class="btn-icon">&#8681;</span> Update</button>
</div>
</div>
<div class="card">
<div class="card-header">
<span class="card-title">Server Details</span>
</div>
<div class="info-row"><span class="info-label">Game Port</span><span class="info-value">8211/UDP</span></div>
<div class="info-row"><span class="info-label">Query Port</span><span class="info-value">27015</span></div>
<div class="info-row"><span class="info-label">RCON Port</span><span class="info-value">25575</span></div>
<div class="info-row"><span class="info-label">Install Size</span><span class="info-value" id="detailSize">--</span></div>
<div class="info-row"><span class="info-label">PID</span><span class="info-value" id="detailPID">--</span></div>
</div>
</div>
</div>

<!-- ═══ CONTROLS PAGE ═══ -->
<div class="page" id="page-controls">
<div class="page-header">
<div>
<div class="page-title">Server Controls</div>
<div class="page-subtitle">Manage your Palworld server</div>
</div>
</div>
<div class="card" style="margin-bottom:24px">
<div class="card-header"><span class="card-title">Server Actions</span></div>
<div class="controls-grid" style="max-width:700px">
<button class="ctrl-btn start" id="cStart" onclick="serverAction('start')"><span class="btn-icon">&#9654;</span> Start Server</button>
<button class="ctrl-btn stop" id="cStop" onclick="serverAction('stop')"><span class="btn-icon">&#9724;</span> Stop Server</button>
<button class="ctrl-btn restart" id="cRestart" onclick="serverAction('restart')"><span class="btn-icon">&#8635;</span> Restart Server</button>
<button class="ctrl-btn update" id="cUpdate" onclick="serverAction('update')"><span class="btn-icon">&#8681;</span> Update Server</button>
</div>
</div>
<div class="card">
<div class="card-header"><span class="card-title">Connection Info</span></div>
<div class="connect-box">
<div class="connect-label">Server Address</div>
<div class="connect-value" id="connectAddr">Loading...</div>
</div>
<div class="info-row"><span class="info-label">Status</span><span class="info-value" id="ctrlStatus">--</span></div>
<div class="info-row"><span class="info-label">Uptime</span><span class="info-value" id="ctrlUptime">--</span></div>
<div class="info-row"><span class="info-label">Process ID</span><span class="info-value" id="ctrlPID">--</span></div>
</div>
</div>

<!-- ═══ LOGS PAGE ═══ -->
<div class="page" id="page-logs">
<div class="page-header">
<div>
<div class="page-title">Server Logs</div>
<div class="page-subtitle">Real-time log viewer</div>
</div>
<div class="header-actions">
<button class="btn-refresh" onclick="refreshLogs()">&#x21bb; Refresh Logs</button>
</div>
</div>
<div class="terminal">
<div class="terminal-header">
<div class="terminal-dots"><div class="terminal-dot r"></div><div class="terminal-dot y"></div><div class="terminal-dot g"></div></div>
<span class="terminal-title">palworld-server.log</span>
</div>
<div class="terminal-body" id="logContent">Loading logs...</div>
</div>
</div>

<!-- ═══ NETWORK PAGE ═══ -->
<div class="page" id="page-network">
<div class="page-header">
<div>
<div class="page-title">Network Status</div>
<div class="page-subtitle">Port and connectivity monitoring</div>
</div>
<div class="header-actions">
<button class="btn-refresh" onclick="refreshNetwork()">&#x21bb; Refresh</button>
</div>
</div>
<div class="card">
<div class="card-header"><span class="card-title">Port Status</span></div>
<div class="info-row">
<span class="info-label">8211/UDP - Game Port</span>
<span class="port-status"><span class="port-dot" id="portGame"></span><span id="portGameText">--</span></span>
</div>
<div class="info-row">
<span class="info-label">27015 - Query Port</span>
<span class="port-status"><span class="port-dot" id="portQuery"></span><span id="portQueryText">--</span></span>
</div>
<div class="info-row">
<span class="info-label">25575/TCP - RCON Port</span>
<span class="port-status"><span class="port-dot" id="portRcon"></span><span id="portRconText">--</span></span>
</div>
</div>
</div>

<!-- ═══ CONFIG PAGE ═══ -->
<div class="page" id="page-config">
<div class="page-header">
<div>
<div class="page-title">Server Settings</div>
<div class="page-subtitle">Edit PalWorldSettings.ini</div>
</div>
<div class="header-actions">
<button class="btn-save" id="btnSaveConfig" onclick="saveConfig()">Save Changes</button>
</div>
</div>
<div class="card">
<textarea class="config-editor" id="configEditor" spellcheck="false">Loading configuration...</textarea>
</div>
</div>

<!-- ═══ BACKUPS PAGE ═══ -->
<div class="page" id="page-backups">
<div class="page-header">
<div>
<div class="page-title">Save Data</div>
<div class="page-subtitle">Server save files</div>
</div>
<div class="header-actions">
<button class="btn-refresh" onclick="refreshBackups()">&#x21bb; Refresh</button>
</div>
</div>
<div class="card">
<div class="card-header"><span class="card-title">Save Files</span></div>
<div id="backupList"><p style="color:var(--text-muted);font-size:13px">Loading...</p></div>
</div>
</div>

<!-- ═══ SYSTEM PAGE ═══ -->
<div class="page" id="page-system">
<div class="page-header">
<div>
<div class="page-title">System Information</div>
<div class="page-subtitle">Host machine details</div>
</div>
</div>
<div class="grid-2">
<div class="card">
<div class="card-header"><span class="card-title">Hardware</span></div>
<div class="info-row"><span class="info-label">Hostname</span><span class="info-value" id="sysHostname">--</span></div>
<div class="info-row"><span class="info-label">IP Address</span><span class="info-value" id="sysIP">--</span></div>
<div class="info-row"><span class="info-label">OS</span><span class="info-value" id="sysOS">--</span></div>
<div class="info-row"><span class="info-label">CPU</span><span class="info-value" id="sysCPUModel">--</span></div>
<div class="info-row"><span class="info-label">CPU Cores</span><span class="info-value" id="sysCores">--</span></div>
<div class="info-row"><span class="info-label">System Uptime</span><span class="info-value" id="sysUptime">--</span></div>
<div class="info-row"><span class="info-label">Load Average</span><span class="info-value" id="sysLoad">--</span></div>
</div>
<div class="card">
<div class="card-header"><span class="card-title">Resources</span></div>
<div class="info-row"><span class="info-label">System CPU</span><span class="info-value" id="sysCPUpct">--%</span></div>
<div class="progress-track"><div class="progress-fill blue" id="sysCPUbar" style="width:0%"></div></div>
<div class="info-row" style="margin-top:12px"><span class="info-label">RAM</span><span class="info-value" id="sysRAMinfo">--</span></div>
<div class="progress-track"><div class="progress-fill purple" id="sysRAMbar" style="width:0%"></div></div>
<div class="info-row" style="margin-top:12px"><span class="info-label">Disk</span><span class="info-value" id="sysDiskInfo">--</span></div>
<div class="progress-track"><div class="progress-fill orange" id="sysDiskBar" style="width:0%"></div></div>
</div>
</div>
</div>

</main>
</div>

<div class="toast-container" id="toasts"></div>

<script>
// ─── State ───
let serverRunning = false;
let actionInProgress = false;

// ─── Navigation ───
function showPage(id, el) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById('page-'+id).classList.add('active');
  if(el) el.classList.add('active');
  // Load page-specific data
  if(id==='logs') refreshLogs();
  if(id==='config') refreshConfig();
  if(id==='backups') refreshBackups();
  if(id==='network') refreshNetwork();
  if(id==='system') refreshAll();
  // Close mobile sidebar
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebarOverlay').classList.remove('show');
}

function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
  document.getElementById('sidebarOverlay').classList.toggle('show');
}

// ─── Toast notifications ───
function toast(msg, type='info') {
  const c = document.getElementById('toasts');
  const t = document.createElement('div');
  const icons = {success:'&#10003;', error:'&#10007;', info:'&#8505;'};
  t.className = 'toast '+type;
  t.innerHTML = '<span>'+icons[type]+'</span> '+msg;
  c.appendChild(t);
  setTimeout(() => { t.style.animation='slideOut .3s ease forwards'; setTimeout(()=>t.remove(),300); }, 4000);
}

// ─── Clock ───
function updateClock() {
  const now = new Date();
  document.getElementById('clockDisplay').textContent = now.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'});
}
setInterval(updateClock, 1000);
updateClock();

// ─── Fetch helpers ───
function api(url, opts) {
  return fetch(url, opts).then(r => {
    if(r.status === 401) { window.location = '/login'; throw new Error('Unauthorized'); }
    return r.json();
  });
}

// ─── Refresh stats ───
function refreshStats() {
  api('/api/stats').then(data => {
    const s = data.stats;
    const sys = data.system;
    serverRunning = s.running;

    // Dashboard stats
    document.getElementById('statStatus').textContent = s.running ? 'Online' : 'Offline';
    document.getElementById('statusIcon').innerHTML = s.running ? '&#9679;' : '&#9679;';
    document.getElementById('statusIcon').className = 'stat-icon ' + (s.running ? 'green' : 'red');
    document.getElementById('statUptime').textContent = s.running ? 'Uptime: '+s.uptime : 'Server is stopped';

    const cpuVal = s.cpu.toFixed(1);
    document.getElementById('statCPU').textContent = cpuVal+'%';
    document.getElementById('cpuBar').style.width = Math.min(s.cpu,100)+'%';

    const ramVal = s.ram.toFixed(1);
    document.getElementById('statRAM').textContent = ramVal+'%';
    document.getElementById('statRAMmb').textContent = s.ram_mb+' MB';
    document.getElementById('ramBar').style.width = Math.min(s.ram,100)+'%';

    document.getElementById('statPlayers').textContent = s.players;
    document.getElementById('detailSize').textContent = s.size;
    document.getElementById('detailPID').textContent = s.pid || '--';

    // Controls page
    document.getElementById('ctrlStatus').textContent = s.running ? 'Running' : 'Stopped';
    document.getElementById('ctrlUptime').textContent = s.uptime;
    document.getElementById('ctrlPID').textContent = s.pid || '--';
    document.getElementById('connectAddr').textContent = (sys.ip || 'YOUR_IP') + ':8211';

    // Button states
    ['q','c'].forEach(prefix => {
      const startBtn = document.getElementById(prefix+'Start');
      const stopBtn = document.getElementById(prefix+'Stop');
      const restartBtn = document.getElementById(prefix+'Restart');
      if(startBtn) startBtn.disabled = s.running || actionInProgress;
      if(stopBtn) stopBtn.disabled = !s.running || actionInProgress;
      if(restartBtn) restartBtn.disabled = !s.running || actionInProgress;
    });
    document.getElementById('qUpdate').disabled = actionInProgress;
    document.getElementById('cUpdate').disabled = actionInProgress;

    // Sidebar status
    const pill = document.getElementById('sidebarStatus');
    const dot = document.getElementById('sidebarDot');
    const txt = document.getElementById('sidebarStatusText');
    pill.className = 'server-status-pill '+(s.running?'online':'offline');
    dot.className = 'status-dot '+(s.running?'online':'offline')+' pulse';
    txt.textContent = s.running ? 'Server Online' : 'Server Offline';

    // System page
    document.getElementById('sysHostname').textContent = sys.hostname;
    document.getElementById('sysIP').textContent = sys.ip;
    document.getElementById('sysOS').textContent = sys.os;
    document.getElementById('sysCPUModel').textContent = sys.cpu_model;
    document.getElementById('sysCores').textContent = sys.cpu_cores;
    document.getElementById('sysUptime').textContent = sys.sys_uptime;
    document.getElementById('sysLoad').textContent = sys.load_avg;
    document.getElementById('sysCPUpct').textContent = sys.sys_cpu_percent.toFixed(1)+'%';
    document.getElementById('sysCPUbar').style.width = Math.min(sys.sys_cpu_percent,100)+'%';
    document.getElementById('sysRAMinfo').textContent = sys.used_ram+' / '+sys.total_ram;
    document.getElementById('sysRAMbar').style.width = Math.min(sys.ram_percent,100)+'%';
    document.getElementById('sysDiskInfo').textContent = sys.used_disk+' / '+sys.total_disk;
    document.getElementById('sysDiskBar').style.width = Math.min(sys.disk_percent,100)+'%';
  }).catch(e => console.error('Stats fetch error:', e));
}

// ─── Server actions ───
function serverAction(action) {
  if(actionInProgress) return;
  if(!confirm('Are you sure you want to '+action+' the server?')) return;

  actionInProgress = true;
  toast('Sending '+action+' command...', 'info');
  refreshStats();

  api('/api/control', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({action:action})
  }).then(data => {
    actionInProgress = false;
    if(data.success) {
      toast(data.message, 'success');
    } else {
      toast(data.message || 'Action failed', 'error');
    }
    setTimeout(refreshStats, 2000);
    setTimeout(refreshStats, 5000);
  }).catch(e => {
    actionInProgress = false;
    toast('Error: '+e.message, 'error');
    refreshStats();
  });
}

// ─── Logs ───
function refreshLogs() {
  api('/api/logs').then(data => {
    const el = document.getElementById('logContent');
    el.textContent = data.logs || 'No logs available';
    el.scrollTop = el.scrollHeight;
  });
}

// ─── Network ───
function refreshNetwork() {
  api('/api/network').then(data => {
    const net = data.network;
    setPort('portGame','portGameText', net.game_port);
    setPort('portQuery','portQueryText', net.query_port);
    setPort('portRcon','portRconText', net.rcon_port);
  });
}
function setPort(dotId, textId, isOpen) {
  document.getElementById(dotId).className = 'port-dot '+(isOpen?'open':'closed');
  document.getElementById(textId).textContent = isOpen?'Listening':'Closed';
}

// ─── Config ───
function refreshConfig() {
  api('/api/config').then(data => {
    document.getElementById('configEditor').value = data.config;
  });
}
function saveConfig() {
  const content = document.getElementById('configEditor').value;
  const btn = document.getElementById('btnSaveConfig');
  btn.disabled = true;
  btn.textContent = 'Saving...';
  api('/api/config', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({config:content})
  }).then(data => {
    btn.disabled = false;
    btn.textContent = 'Save Changes';
    if(data.success) toast('Configuration saved!','success');
    else toast('Failed to save config','error');
  }).catch(e => {
    btn.disabled = false;
    btn.textContent = 'Save Changes';
    toast('Error saving config','error');
  });
}

// ─── Backups ───
function refreshBackups() {
  api('/api/backups').then(data => {
    const el = document.getElementById('backupList');
    if(!data.backups || data.backups.length===0) {
      el.innerHTML = '<p style="color:var(--text-muted);font-size:13px;padding:12px 0">No save files found. Start the server to generate save data.</p>';
      return;
    }
    let html = '';
    data.backups.forEach(b => {
      const sizeKB = (b.size/1024).toFixed(1);
      html += '<div class="info-row"><span class="info-label">'+b.name+'</span><span class="info-value">'+b.date+' ('+sizeKB+' KB)</span></div>';
    });
    el.innerHTML = html;
  });
}

// ─── Refresh all ───
function refreshAll() { refreshStats(); }

// ─── Init ───
refreshStats();
setInterval(refreshStats, 5000);
</script>
</body>
</html>'''


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the dashboard"""

    def log_message(self, format, *args):
        """Suppress default logging, use custom format"""
        pass

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def send_html(self, html, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode())

    def is_authenticated(self):
        cookie_header = self.headers.get('Cookie', '')
        return validate_session(cookie_header)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path

        if path == '/login':
            html = LOGIN_HTML.replace('__ERROR__', '')
            self.send_html(html)
            return

        if path == '/logout':
            cookie_header = self.headers.get('Cookie', '')
            if cookie_header:
                cookie = SimpleCookie()
                cookie.load(cookie_header)
                if 'session_id' in cookie:
                    sid = cookie['session_id'].value
                    sessions.pop(sid, None)
            self.send_response(302)
            self.send_header('Location', '/login')
            self.send_header('Set-Cookie', 'session_id=; Path=/; Max-Age=0')
            self.end_headers()
            return

        if not self.is_authenticated():
            self.send_response(302)
            self.send_header('Location', '/login')
            self.end_headers()
            return

        if path == '/' or path == '':
            self.send_html(DASHBOARD_HTML)

        elif path == '/api/stats':
            self.send_json({'stats': get_server_stats(), 'system': get_system_info()})

        elif path == '/api/logs':
            self.send_json({'logs': get_recent_logs()})

        elif path == '/api/config':
            self.send_json({'config': get_config()})

        elif path == '/api/backups':
            self.send_json({'backups': get_backup_list()})

        elif path == '/api/network':
            self.send_json({'network': get_network_info()})

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else ''
        path = urllib.parse.urlparse(self.path).path

        if path == '/login':
            # Parse form data
            params = urllib.parse.parse_qs(body)
            password = params.get('password', [''])[0]
            password_hash = hashlib.sha256(password.encode()).hexdigest()

            if password_hash == PASSWORD_HASH:
                sid = generate_session_id()
                sessions[sid] = {'created': time.time()}
                self.send_response(302)
                self.send_header('Location', '/')
                self.send_header('Set-Cookie', f'session_id={sid}; Path=/; HttpOnly')
                self.end_headers()
            else:
                html = LOGIN_HTML.replace('__ERROR__', '<div class="error-msg">Invalid password</div>')
                self.send_html(html)
            return

        # All other POST endpoints require auth
        if not self.is_authenticated():
            self.send_json({'error': 'Unauthorized'}, 401)
            return

        if path == '/api/control':
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self.send_json({'success': False, 'message': 'Invalid request'})
                return

            action = data.get('action', '')
            script_path = f"{STEAM_HOME}/palworld.sh"

            if action == 'start':
                # Start directly with screen
                if is_server_running():
                    self.send_json({'success': False, 'message': 'Server is already running'})
                    return
                cmd = f"su - {STEAM_USER} -c 'cd {PALWORLD_DIR} && screen -dmS {SCREEN_NAME} ./PalServer.sh'"
                output, code = run_command(cmd, timeout_sec=15)
                time.sleep(2)
                running = is_server_running()
                self.send_json({
                    'success': running,
                    'message': 'Server started successfully' if running else 'Failed to start server'
                })

            elif action == 'stop':
                if not is_server_running():
                    self.send_json({'success': False, 'message': 'Server is not running'})
                    return
                cmd = f"su - {STEAM_USER} -c 'screen -S {SCREEN_NAME} -X quit'"
                run_command(cmd)
                time.sleep(2)
                stopped = not is_server_running()
                self.send_json({
                    'success': stopped,
                    'message': 'Server stopped successfully' if stopped else 'Failed to stop server'
                })

            elif action == 'restart':
                # Stop
                if is_server_running():
                    run_command(f"su - {STEAM_USER} -c 'screen -S {SCREEN_NAME} -X quit'")
                    time.sleep(3)
                # Start
                cmd = f"su - {STEAM_USER} -c 'cd {PALWORLD_DIR} && screen -dmS {SCREEN_NAME} ./PalServer.sh'"
                run_command(cmd, timeout_sec=15)
                time.sleep(2)
                running = is_server_running()
                self.send_json({
                    'success': running,
                    'message': 'Server restarted successfully' if running else 'Failed to restart server'
                })

            elif action == 'update':
                # Run update in background
                cmd = f"su - {STEAM_USER} -c 'cd {STEAM_HOME}/steamcmd && ./steamcmd.sh +force_install_dir {PALWORLD_DIR} +login anonymous +app_update 2394010 validate +quit' > /tmp/palworld-update.log 2>&1 &"
                run_command(cmd)
                self.send_json({'success': True, 'message': 'Update started in background (check /tmp/palworld-update.log)'})

            else:
                self.send_json({'success': False, 'message': 'Unknown action'})

        elif path == '/api/config':
            try:
                data = json.loads(body)
                config_content = data.get('config', '')
                if save_config(config_content):
                    self.send_json({'success': True})
                else:
                    self.send_json({'success': False})
            except Exception as e:
                self.send_json({'success': False, 'message': str(e)})

        else:
            self.send_response(404)
            self.end_headers()


class ThreadedHTTPServer(HTTPServer):
    """Handle requests in separate threads"""
    def process_request(self, request, client_address):
        thread = threading.Thread(target=self._handle, args=(request, client_address))
        thread.daemon = True
        thread.start()

    def _handle(self, request, client_address):
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(request)


if __name__ == '__main__':
    print(f"\033[36m{'='*50}\033[0m")
    print(f"\033[32m  Palworld Server Dashboard\033[0m")
    print(f"\033[36m{'='*50}\033[0m")
    print()
    print(f"  URL:      \033[36mhttp://0.0.0.0:{DASHBOARD_PORT}\033[0m")
    print(f"  Password: \033[33m{DEFAULT_PASSWORD}\033[0m")
    print()
    print(f"\033[36m{'='*50}\033[0m")
    print(f"  \033[33mPress Ctrl+C to stop\033[0m")
    print()

    server = ThreadedHTTPServer(('0.0.0.0', DASHBOARD_PORT), DashboardHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\033[33mDashboard stopped.\033[0m")
        server.server_close()
