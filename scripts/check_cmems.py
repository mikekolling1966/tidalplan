"""
check_cmems.py — poll the Pi until CMEMS data is downloaded and ready.

Usage:  python scripts/check_cmems.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import config

import urllib.request, json, warnings, time
warnings.filterwarnings('ignore')

url = f'http://{config.PI_HOST}:8081/api/tides/cmems/status'
print(f'Polling {url} every 15 s ...\n')

for attempt in range(24):
    time.sleep(15)
    try:
        r = urllib.request.urlopen(url, timeout=10)
        data = json.loads(r.read())
        print(f'Attempt {attempt+1}:')
        print(json.dumps(data, indent=2))
        if data.get('available'):
            print('\nCMEMS is READY!')
            break
        else:
            print(f"  Not ready yet: {data.get('reason', '')}\n")
    except Exception as e:
        print(f'  Check failed: {e}\n')
