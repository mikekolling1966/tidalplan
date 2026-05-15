"""
install_pi.py — first-time install of TidalPlan onto a Raspberry Pi.

Clones the repo, creates a venv, installs all dependencies, writes .env
with API keys, and sets up the systemd service.

Usage:  python scripts/install_pi.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import config

import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(config.PI_HOST, username=config.PI_USER, password=config.PI_PASS, timeout=15)


def run(label, cmd, timeout=180):
    print(f'> {label}...', flush=True)
    _, stdout, _ = client.exec_command(cmd, timeout=timeout, get_pty=True)
    out = stdout.read().decode('utf-8', errors='replace').encode('ascii', errors='replace').decode('ascii')
    if out.strip():
        print(out.strip()[-500:])
    print('  done')


run('Updating apt cache',      'sudo apt-get update -qq')
run('Installing git + venv',   'sudo apt-get install -y -qq git python3-venv python3-pip', timeout=120)
run('Cloning / updating repo',
    'if [ -d /opt/tidalplan/.git ]; then sudo git -C /opt/tidalplan pull; '
    'else sudo git clone https://github.com/mikekolling1966/tidalplan.git /opt/tidalplan; fi')
run('Creating virtual env',    'sudo python3 -m venv /opt/tidalplan/venv')
run('Upgrading pip',           'sudo /opt/tidalplan/venv/bin/pip install --upgrade pip -q')
run('Installing requirements', 'sudo /opt/tidalplan/venv/bin/pip install -r /opt/tidalplan/requirements.txt', timeout=300)

# Write .env with all credentials
env_contents = (
    f"UKHO_API_KEY={config.UKHO_API_KEY}\\n"
    f"CMEMS_USERNAME={config.CMEMS_USERNAME}\\n"
    f"CMEMS_PASSWORD={config.CMEMS_PASSWORD}\\n"
)
run('Writing .env',
    f"printf 'UKHO_API_KEY={config.UKHO_API_KEY}\\nCMEMS_USERNAME={config.CMEMS_USERNAME}\\nCMEMS_PASSWORD={config.CMEMS_PASSWORD}\\n' "
    f"| sudo tee /opt/tidalplan/.env > /dev/null")

run('Creating data directory', 'sudo mkdir -p /opt/tidalplan/data')
run('Fixing ownership',        f'sudo chown -R {config.PI_USER}:{config.PI_USER} /opt/tidalplan')

service = """[Unit]
Description=TidalPlan tidal departure planner
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/tidalplan
ExecStart=/opt/tidalplan/venv/bin/python start.py
Restart=on-failure
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
"""
run('Writing systemd service',
    f"printf '%s' '{service}' | sudo tee /etc/systemd/system/tidalplan.service > /dev/null")
run('Enabling + starting service',
    'sudo systemctl daemon-reload && sudo systemctl enable tidalplan && sudo systemctl restart tidalplan')
run('Checking service status',
    'sleep 3 && sudo systemctl status tidalplan --no-pager')

client.close()
print(f'\nInstallation complete!')
print(f'Open http://{config.PI_HOST}:8081 in your browser.')
