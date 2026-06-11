import os
import json
import logging
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)

DEFAULT_RETENTION_DAYS = 7
SEEN_FILE_PATH = "seen.json"

def load_state(file_path: str = SEEN_FILE_PATH) -> dict:
    """Loads the state dictionary from seen.json. Returns a default dict if it doesn't exist."""
    if not os.path.exists(file_path):
        return {"retention_days": DEFAULT_RETENTION_DAYS}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                logger.warning("seen.json format is not a dictionary. Resetting.")
                return {"retention_days": DEFAULT_RETENTION_DAYS}
            if "retention_days" not in data:
                data["retention_days"] = DEFAULT_RETENTION_DAYS
            return data
    except Exception as e:
        logger.error(f"Error loading {file_path}: {e}. Returning default state.")
        return {"retention_days": DEFAULT_RETENTION_DAYS}

def save_state(state: dict, file_path: str = SEEN_FILE_PATH) -> None:
    """Saves the state dictionary to seen.json."""
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving {file_path}: {e}")

def is_seen(state: dict, post_id: str) -> bool:
    """Returns True if the post_id has already been processed (exists in any date key)."""
    for key, value in state.items():
        if key == "retention_days":
            continue
        if isinstance(value, list) and post_id in value:
            return True
    return False

def mark_seen(state: dict, date_str: str, post_id: str) -> None:
    """Marks a post_id as seen for the specified date."""
    if date_str not in state:
        state[date_str] = []
    if post_id not in state[date_str]:
        state[date_str].append(post_id)

def cleanup_old_entries(state: dict, today: date = None) -> dict:
    """Removes entries that are older than retention_days (default 7 days)."""
    if today is None:
        today = date.today()
        
    retention_days = state.get("retention_days", DEFAULT_RETENTION_DAYS)
    cutoff_date = today - timedelta(days=retention_days)
    
    keys_to_delete = []
    for key in state.keys():
        if key == "retention_days":
            continue
        try:
            # Parse the date key
            key_date = datetime.strptime(key, "%Y-%m-%d").date()
            if key_date < cutoff_date:
                keys_to_delete.append(key)
        except ValueError:
            # Skip keys that are not in YYYY-MM-DD format
            logger.warning(f"Skipping invalid date key in seen.json: {key}")
            continue

    for key in keys_to_delete:
        logger.info(f"Removing expired seen entry: {key}")
        del state[key]
        
    return state
