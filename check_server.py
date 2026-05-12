import requests
import sys
try:
    r = requests.get('http://localhost:8000', timeout=5)
    print(f'Server is running: status {r.status_code}')
except requests.exceptions.ConnectionError:
    print('Server is NOT running')
    sys.exit(1)
except Exception as e:
    print(f'Error: {e}')
    sys.exit(1)
