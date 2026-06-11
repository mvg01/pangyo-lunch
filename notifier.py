import json
import os
import logging
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)

MENUS_FILE = "menus.json"
DOCS_DIR = "docs"
WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]


def load_menus(menus_file: str = MENUS_FILE) -> dict:
    if not os.path.exists(menus_file):
        return {}
    try:
        with open(menus_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_menu(menus_file: str, date_str: str, restaurant: str, menu_data: dict, post_link: str) -> None:
    menus = load_menus(menus_file)
    if date_str not in menus:
        menus[date_str] = {}
    menus[date_str][restaurant] = {
        "menus": menu_data.get("menus", []),
        "price": menu_data.get("price"),
        "notes": menu_data.get("notes"),
        "post_link": post_link,
    }
    with open(menus_file, "w", encoding="utf-8") as f:
        json.dump(menus, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved menu for {restaurant} on {date_str}")


def cleanup_old_menus(menus_file: str, today: date, keep_days: int = 14) -> None:
    menus = load_menus(menus_file)
    cutoff = today - timedelta(days=keep_days)
    keys_to_delete = [k for k in menus if _try_parse_date(k) is not None and _try_parse_date(k) < cutoff]
    if not keys_to_delete:
        return
    for k in keys_to_delete:
        del menus[k]
    with open(menus_file, "w", encoding="utf-8") as f:
        json.dump(menus, f, indent=2, ensure_ascii=False)


def _try_parse_date(date_str: str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None


def generate_html(menus_file: str, subscriptions: list, reference_date: date = None) -> None:
    if reference_date is None:
        reference_date = date.today()

    menus = load_menus(menus_file)
    os.makedirs(DOCS_DIR, exist_ok=True)

    restaurants = [s["name"] for s in subscriptions]

    # 최근 5 평일 수집
    weekdays = []
    d = reference_date
    while len(weekdays) < 5:
        if d.weekday() < 5:
            weekdays.append(d)
        d -= timedelta(days=1)

    days_data = []
    for i, d in enumerate(weekdays):
        date_str = d.strftime("%Y-%m-%d")
        day_menus = menus.get(date_str, {})
        rests = []
        for r in restaurants:
            if r in day_menus:
                rests.append({
                    "name": r,
                    "found": True,
                    "menus": day_menus[r].get("menus", []),
                    "price": day_menus[r].get("price"),
                    "notes": day_menus[r].get("notes"),
                    "post_link": day_menus[r].get("post_link"),
                })
            else:
                rests.append({"name": r, "found": False, "menus": [], "price": None, "notes": None, "post_link": None})
        days_data.append({
            "date_str": date_str,
            "label": f"{d.month}월 {d.day}일 ({WEEKDAY_KO[d.weekday()]})",
            "is_latest": i == 0,
            "restaurants": rests,
        })

    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    html = _build_html(days_data, updated_at)

    out_path = os.path.join(DOCS_DIR, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info(f"Generated HTML: {out_path}")


def _build_card(r: dict) -> str:
    name = r["name"]
    if r["found"]:
        badge = '<span class="badge badge-ok">등록됨</span>'
        if r["menus"]:
            items = "".join(f"<li>{item}</li>" for item in r["menus"])
        else:
            items = "<li>메뉴 파싱 불가 — 원본 글을 확인해 주세요</li>"
        menu_html = f'<ul class="menu-list">{items}</ul>'

        meta_parts = []
        if r["price"]:
            meta_parts.append(f"가격: {r['price']}")
        if r["notes"]:
            meta_parts.append(r["notes"])
        meta_html = f'<p class="card-meta">{" &nbsp;|&nbsp; ".join(meta_parts)}</p>' if meta_parts else ""

        link_html = ""
        if r["post_link"]:
            link_html = f'<a href="{r["post_link"]}" target="_blank" rel="noopener" class="card-link">네이버 카페 원본 보기 →</a>'

        body = f"{menu_html}{meta_html}{link_html}"
    else:
        badge = '<span class="badge badge-missing">미등록</span>'
        body = '<p class="no-menu-text">아직 오늘의 메뉴가 등록되지 않았어요</p>'

    return (
        f'<div class="card">'
        f'<div class="card-header">'
        f'<span class="card-title">{name}</span>'
        f'{badge}'
        f'</div>'
        f'{body}'
        f'</div>'
    )


def _build_html(days_data: list, updated_at: str) -> str:
    tabs_html = ""
    for day in days_data:
        dot = '<span class="today-dot"></span>' if day["is_latest"] else ""
        active = "active" if day["is_latest"] else ""
        tabs_html += (
            f'<button class="tab {active}" onclick="showDay(\'{day["date_str"]}\')" '
            f'data-date="{day["date_str"]}">{day["label"]}{dot}</button>'
        )

    contents_html = ""
    for day in days_data:
        active = "active" if day["is_latest"] else ""
        cards_html = "".join(_build_card(r) for r in day["restaurants"])
        contents_html += (
            f'<div class="day-content {active}" id="day-{day["date_str"]}">'
            f'<div class="cards">{cards_html}</div>'
            f'</div>'
        )

    return (
        '<!DOCTYPE html>\n<html lang="ko">\n<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        '<title>판교 점심 메뉴</title>\n'
        f'<style>{_CSS}</style>\n'
        '</head>\n<body>\n'
        '<header class="header"><h1>🍚 판교 점심 메뉴</h1></header>\n'
        f'<div class="tabs-wrapper"><div class="tabs">{tabs_html}</div></div>\n'
        '<div class="content">'
        '<div id="weekend-banner" class="weekend-banner" style="display:none">'
        '<div class="emoji">🏖️</div>'
        '<h2>오늘은 주말이에요!</h2>'
        '<p>평일 메뉴는 위 탭에서 확인하세요</p>'
        '</div>'
        f'{contents_html}'
        '</div>\n'
        f'<p class="updated-at">마지막 업데이트: {updated_at} KST</p>\n'
        f'<script>{_JS}</script>\n'
        '</body>\n</html>'
    )


_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans KR', sans-serif; background: #f8f9fa; color: #212529; min-height: 100vh; }
.header { background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); color: white; padding: 24px 20px; text-align: center; }
.header h1 { font-size: 22px; font-weight: 700; }
.tabs-wrapper { background: white; border-bottom: 1px solid #e9ecef; overflow-x: auto; -webkit-overflow-scrolling: touch; position: sticky; top: 0; z-index: 10; box-shadow: 0 1px 3px rgba(0,0,0,.06); }
.tabs { display: flex; padding: 0 8px; }
.tab { padding: 14px 12px; cursor: pointer; font-size: 13px; font-weight: 500; color: #868e96; border: none; background: none; border-bottom: 3px solid transparent; white-space: nowrap; transition: all 0.15s; }
.tab:hover { color: #495057; }
.tab.active { color: #4f46e5; border-bottom-color: #4f46e5; font-weight: 600; }
.today-dot { display: inline-block; width: 5px; height: 5px; background: #f03e3e; border-radius: 50%; margin-left: 4px; vertical-align: middle; position: relative; top: -1px; }
.content { max-width: 960px; margin: 0 auto; padding: 20px 16px 40px; }
.day-content { display: none; }
.day-content.active { display: block; }
.weekend-banner { text-align: center; padding: 60px 20px; }
.weekend-banner .emoji { font-size: 52px; margin-bottom: 16px; }
.weekend-banner h2 { font-size: 20px; color: #495057; margin-bottom: 8px; }
.weekend-banner p { color: #868e96; font-size: 14px; }
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.card { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.card-title { font-size: 16px; font-weight: 700; }
.badge { font-size: 11px; padding: 3px 8px; border-radius: 20px; font-weight: 600; }
.badge-ok { background: #d3f9d8; color: #2b8a3e; }
.badge-missing { background: #ffe3e3; color: #c92a2a; }
.menu-list { list-style: none; margin-bottom: 12px; }
.menu-list li { padding: 6px 0; font-size: 14px; color: #495057; border-bottom: 1px solid #f1f3f5; display: flex; align-items: center; gap: 8px; }
.menu-list li:last-child { border-bottom: none; }
.menu-list li::before { content: ''; display: inline-block; width: 6px; height: 6px; background: #4f46e5; border-radius: 50%; flex-shrink: 0; }
.card-meta { font-size: 12px; color: #868e96; margin-bottom: 12px; line-height: 1.6; }
.card-link { display: block; text-align: center; padding: 9px 12px; background: #f8f9fa; border-radius: 8px; font-size: 13px; color: #4f46e5; text-decoration: none; border: 1px solid #e9ecef; transition: background 0.15s; }
.card-link:hover { background: #e9ecef; }
.no-menu-text { color: #adb5bd; font-size: 14px; text-align: center; padding: 24px 0; }
.updated-at { text-align: center; font-size: 12px; color: #ced4da; padding: 16px; }
"""

_JS = """
function showDay(dateStr) {
  document.querySelectorAll('.day-content').forEach(function(el) { el.classList.remove('active'); });
  document.querySelectorAll('.tab').forEach(function(el) { el.classList.remove('active'); });
  var c = document.getElementById('day-' + dateStr);
  var t = document.querySelector('[data-date="' + dateStr + '"]');
  if (c) c.classList.add('active');
  if (t) t.classList.add('active');
}
document.addEventListener('DOMContentLoaded', function() {
  var dow = new Date().getDay();
  if (dow === 0 || dow === 6) {
    document.getElementById('weekend-banner').style.display = 'block';
  }
});
"""
