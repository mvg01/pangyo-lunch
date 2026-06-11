import os
import json
import pytest
from datetime import date
from state import load_state, save_state, is_seen, mark_seen, cleanup_old_entries

@pytest.fixture
def temp_state_file(tmp_path):
    return os.path.join(tmp_path, "seen_test.json")

def test_load_state_default(temp_state_file):
    # If file doesn't exist, should return default state
    state_data = load_state(temp_state_file)
    assert state_data == {"retention_days": 7}

def test_save_and_load_state(temp_state_file):
    state_data = {
        "retention_days": 5,
        "2026-06-11": ["1001", "1002"]
    }
    save_state(state_data, temp_state_file)
    
    loaded = load_state(temp_state_file)
    assert loaded == state_data

def test_is_seen():
    state_data = {
        "retention_days": 7,
        "2026-06-10": ["1001"],
        "2026-06-11": ["1002", "1003"]
    }
    
    assert is_seen(state_data, "1001") is True
    assert is_seen(state_data, "1002") is True
    assert is_seen(state_data, "1003") is True
    assert is_seen(state_data, "1004") is False
    assert is_seen(state_data, "retention_days") is False

def test_mark_seen():
    state_data = {"retention_days": 7}
    
    mark_seen(state_data, "2026-06-11", "1001")
    assert state_data["2026-06-11"] == ["1001"]
    
    # Check duplicate prevention inside list
    mark_seen(state_data, "2026-06-11", "1001")
    assert state_data["2026-06-11"] == ["1001"]
    
    # Check adding different post
    mark_seen(state_data, "2026-06-11", "1002")
    assert state_data["2026-06-11"] == ["1001", "1002"]
    
    # Check another date
    mark_seen(state_data, "2026-06-12", "1003")
    assert state_data["2026-06-12"] == ["1003"]

def test_cleanup_old_entries():
    today = date(2026, 6, 11)
    # Retention days is 7, so cutoff is 2026-06-04.
    # Anything strictly before 2026-06-04 should be deleted.
    state_data = {
        "retention_days": 7,
        "2026-06-11": ["today_post"],     # Keep
        "2026-06-05": ["keep_post"],      # Keep (exactly cutoff+1 day)
        "2026-06-04": ["keep_post2"],     # Keep (exactly cutoff day)
        "2026-06-03": ["delete_post1"],   # Delete (1 day older than cutoff)
        "2026-05-20": ["delete_post2"],   # Delete (much older)
        "invalid_date": ["keep_invalid"]  # Should log warning, but won't crash
    }
    
    cleaned = cleanup_old_entries(state_data, today)
    
    assert "2026-06-11" in cleaned
    assert "2026-06-05" in cleaned
    assert "2026-06-04" in cleaned
    assert "2026-06-03" not in cleaned
    assert "2026-05-20" not in cleaned
    assert "invalid_date" in cleaned # Invalid formats are skipped from cleanup
    assert cleaned["retention_days"] == 7
