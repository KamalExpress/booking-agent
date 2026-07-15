import os
import json

ACCOUNTS_FILE = os.path.join(os.path.dirname(__file__), "accounts.json")
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")

DEFAULT_SETTINGS = {
    "APPOINTMENT_DATE_FROM": "01/09/2026",
    "APPOINTMENT_DATE_TO": "15/09/2026",
    "HOLIDAYS": "SAT,SUN",
    "MONITOR_INTERVAL_MINUTES": 5,
    "APPOINTMENT_TYPE": "26",
    "APPOINTMENT_VAC_ID": "138",
    "DEMO_MODE": "False"
}

def load_accounts():
    if not os.path.exists(ACCOUNTS_FILE):
        return []
    try:
        with open(ACCOUNTS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []

def save_accounts(accounts):
    with open(ACCOUNTS_FILE, "w") as f:
        json.dump(accounts, f, indent=4)

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return DEFAULT_SETTINGS.copy()
    try:
        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)
            # Merge with defaults to ensure all keys exist
            settings = DEFAULT_SETTINGS.copy()
            settings.update(data)
            return settings
    except Exception:
        return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=4)
