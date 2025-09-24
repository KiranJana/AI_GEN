# limit_manager.py

import bpy
import json
import os
import time
from datetime import datetime

# --- Constants for Free Tier Limits ---
RPM_LIMIT = 10  # Requests Per Minute
RPD_LIMIT = 250 # Requests Per Day

def get_log_path():
    """Gets the path to the usage log file."""
    config_path = bpy.utils.user_resource('CONFIG')
    return os.path.join(config_path, "ai_scene_gen_usage.json")

def load_usage_data():
    """Loads usage data from the JSON log file."""
    log_path = get_log_path()
    if not os.path.exists(log_path):
        return {"requests": []}
    try:
        with open(log_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"requests": []}

def save_usage_data(data):
    """Saves usage data to the JSON log file."""
    log_path = get_log_path()
    try:
        with open(log_path, 'w') as f:
            json.dump(data, f, indent=4)
    except IOError as e:
        print(f"Error saving usage data: {e}")

def check_limits(usage_data):
    """
    Checks if a new request is allowed based on RPM and RPD limits.
    Returns (is_allowed, reason, cooldown)
    """
    now = time.time()
    requests = usage_data.get("requests", [])
    
    today = datetime.now().date()
    requests_today = [r for r in requests if datetime.fromtimestamp(r).date() == today]
    if len(requests_today) >= RPD_LIMIT:
        return (False, f"Daily limit of {RPD_LIMIT} reached.", 0)

    one_minute_ago = now - 60
    requests_last_minute = [r for r in requests if r > one_minute_ago]
    if len(requests_last_minute) >= RPM_LIMIT:
        oldest_request = min(requests_last_minute)
        cooldown = int(60 - (now - oldest_request)) + 1
        return (False, f"Per-minute limit reached.", cooldown)

    return (True, "Ready", 0)

def log_request(usage_data):
    """Adds a timestamp for a new request."""
    now = time.time()
    usage_data["requests"].append(now)
    
    one_day_ago = now - 86400 
    usage_data["requests"] = [r for r in usage_data["requests"] if r > one_day_ago]
    
    return usage_data