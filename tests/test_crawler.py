import pytest
from datetime import date
from crawler import parse_title

@pytest.fixture
def subscriptions():
    return [
        {"name": "바른밥상", "keywords": ["바른밥상", "바른 밥상"]},
        {"name": "엄니한식뷔페", "keywords": ["엄니한식", "엄니 한식"]},
        {"name": "해담가", "keywords": ["해담가"]},
        {"name": "정겨운맛풍경", "keywords": ["정겨운맛풍경", "정겨운 맛풍경"]}
    ]

def test_parse_title_korean_date_matching_restaurants(subscriptions):
    # Reference date is 2026-06-11
    ref_date = date(2026, 6, 11)
    
    # Test cases from requirements
    case1 = parse_title('6월11일 판교아이스퀘어 107호 "해담가" 오늘 메뉴', subscriptions, ref_date)
    assert case1["date"] == date(2026, 6, 11)
    assert case1["matched_restaurant"] == "해담가"
    
    case2 = parse_title('6월 11일 경기기업성장센터 2층 "정겨운맛풍경" 오늘 메뉴', subscriptions, ref_date)
    assert case2["date"] == date(2026, 6, 11)
    assert case2["matched_restaurant"] == "정겨운맛풍경"
    
    case3 = parse_title('6월11일 판교아이스퀘어 B1 "엄니한식뷔페" 오늘 메뉴', subscriptions, ref_date)
    assert case3["date"] == date(2026, 6, 11)
    assert case3["matched_restaurant"] == "엄니한식뷔페"
    
    # Subscribed restaurant, but keyword in middle of string
    case4 = parse_title('6월 11일 판교 "바른 밥상" 점심', subscriptions, ref_date)
    assert case4["date"] == date(2026, 6, 11)
    assert case4["matched_restaurant"] == "바른밥상"

def test_parse_title_unsubscribed_restaurant(subscriptions):
    ref_date = date(2026, 6, 11)
    
    # Yesterday's menu of unsubscribed restaurant
    case = parse_title('6월10일 목요일 런치포유 점심메뉴 글로벌비즈센터 B동 110호', subscriptions, ref_date)
    assert case["date"] == date(2026, 6, 10)
    assert case["matched_restaurant"] is None

def test_parse_title_slash_date_format(subscriptions):
    ref_date = date(2026, 6, 11)
    
    # Test slash pattern e.g., "06/11" or "6/11"
    case1 = parse_title('06/11 정겨운맛풍경 메뉴', subscriptions, ref_date)
    assert case1["date"] == date(2026, 6, 11)
    assert case1["matched_restaurant"] == "정겨운맛풍경"
    
    case2 = parse_title('6/11 엄니한식', subscriptions, ref_date)
    assert case2["date"] == date(2026, 6, 11)
    assert case2["matched_restaurant"] == "엄니한식뷔페"

def test_parse_title_invalid_date_or_restaurant(subscriptions):
    ref_date = date(2026, 6, 11)
    
    # Invalid date pattern
    case1 = parse_title('맛있는 해담가 오늘 메뉴', subscriptions, ref_date)
    assert case1["date"] is None
    assert case1["matched_restaurant"] == "해담가"
    
    # Completely unrelated title
    case2 = parse_title('공지사항 필독 바랍니다.', subscriptions, ref_date)
    assert case2["date"] is None
    assert case2["matched_restaurant"] is None
