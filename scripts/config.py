import base64
_d = lambda s: base64.b64decode(s).decode()

PI_HOST      = "192.168.1.30"
PI_USER      = "pi"
PI_PASS      = _d("cmFzcGJlcnJ5")

UKHO_API_KEY   = _d("OGEwMzE5YmY4NDk3NDljOTkwODMyODNlZTY2M2FiZTE=")
CMEMS_USERNAME = _d("bWlrZS5rb2xsaW5nQGR5bmFtaWNzMjQ3Lm5ldA==")
CMEMS_PASSWORD = _d("NTNjVXIxdFk/PzUzY1VyMXRZPz8=")
