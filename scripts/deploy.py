"""
deploy.py — pull latest code from GitHub and restart TidalPlan on the Pi.

Usage:  python scripts/deploy.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import config

import paramiko, warnings
warnings.filterwarnings('ignore')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(config.PI_HOST, username=config.PI_USER, password=config.PI_PASS, timeout=15)


def run(label, cmd, timeout=120):
    print(f'> {label}...', flush=True)
    _, stdout, _ = client.exec_command(cmd, timeout=timeout, get_pty=True)
    out = stdout.read().decode('utf-8', errors='replace').encode('ascii', errors='replace').decode('ascii')
    if out.strip():
        print(out.strip()[-600:])
    print('  done')


run('Git pull latest code',  'cd /opt/tidalplan && git pull')
run('Restarting service',    'sudo systemctl restart tidalplan')
run('Checking startup logs', 'sleep 5 && sudo journalctl -u tidalplan --no-pager -n 15')

client.close()
print(f'\nDeploy complete.')
print(f'App:          http://{config.PI_HOST}:8081/')
print(f'CMEMS status: http://{config.PI_HOST}:8081/api/tides/cmems/status')
