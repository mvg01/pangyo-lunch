import re
import logging
from datetime import date, datetime
import urllib.request
import os

logger = logging.getLogger(__name__)

class CrawlResult:
    def __init__(self, status: bool, reason: str = None, posts: list = None):
        self.status = status
        self.reason = reason
        self.posts = posts or []

def parse_title(title: str, subscriptions: list, reference_date: date = None) -> dict:
    """
    Parses the post title to extract the date and match against subscribed restaurants.
    
    date patterns:
    - "6월11일", "6월 11일", "06월 11일"
    - "06/11", "6/11"
    """
    if reference_date is None:
        reference_date = date.today()
        
    year = reference_date.year
    extracted_date = None
    
    # 1. Try "M월 D일" pattern
    match_ko = re.search(r'(\d{1,2})\s*월\s*(\d{1,2})\s*일', title)
    if match_ko:
        month = int(match_ko.group(1))
        day = int(match_ko.group(2))
        try:
            extracted_date = date(year, month, day)
        except ValueError:
            pass
            
    # 2. Try "M/D" pattern if Korean pattern didn't match
    if not extracted_date:
        match_slash = re.search(r'(\d{1,2})\s*/\s*(\d{1,2})', title)
        if match_slash:
            month = int(match_slash.group(1))
            day = int(match_slash.group(2))
            try:
                extracted_date = date(year, month, day)
            except ValueError:
                pass

    # Match restaurant by keywords
    matched_restaurant = None
    for sub in subscriptions:
        name = sub.get("name")
        keywords = sub.get("keywords", [])
        for kw in keywords:
            # Simple keyword check (case-insensitive)
            if kw.lower() in title.lower():
                matched_restaurant = name
                break
        if matched_restaurant:
            break
            
    return {
        "date": extracted_date,
        "matched_restaurant": matched_restaurant
    }

def mock_crawl(config: dict, reference_date: date = None) -> CrawlResult:
    """
    Returns mock posts to verify the pipeline.
    Uses reference_date (defaults to today) for date matching.
    """
    if reference_date is None:
        reference_date = date.today()
        
    m = reference_date.month
    d = reference_date.day
    
    # Generate mock titles that will match config subscriptions
    posts = [
        {
            "post_id": "1001",
            "title": f"{m}월 {d}일 판교아이스퀘어 B1 \"엄니한식뷔페\" 오늘 메뉴",
            "link": "https://cafe.naver.com/f-e/cafes/30487307/articles/1001",
            "image_urls": ["https://picsum.photos/400/300"]
        },
        {
            "post_id": "1002",
            "title": f"{m}월{d}일 판교아이스퀘어 107호 \"해담가\" 오늘 메뉴",
            "link": "https://cafe.naver.com/f-e/cafes/30487307/articles/1002",
            "image_urls": ["https://picsum.photos/400/300"]
        },
        {
            "post_id": "1003",
            "title": f"{m}/{d} 경기기업성장센터 2층 \"정겨운맛풍경\" 오늘 메뉴",
            "link": "https://cafe.naver.com/f-e/cafes/30487307/articles/1003",
            "image_urls": ["https://picsum.photos/400/300"]
        },
        # This one is not subscribed
        {
            "post_id": "1004",
            "title": f"{m}월 {d}일 목요일 런치포유 점심메뉴 글로벌비즈센터 B동 110호",
            "link": "https://cafe.naver.com/f-e/cafes/30487307/articles/1004",
            "image_urls": ["https://picsum.photos/400/300"]
        },
        # This one is yesterday's menu
        {
            "post_id": "1005",
            "title": f"{m}월 {d-1}일 판교아이스퀘어 B1 \"엄니한식뷔페\" 오늘 메뉴" if d > 1 else f"{m-1}월 28일 판교아이스퀘어 B1 \"엄니한식뷔페\" 오늘 메뉴",
            "link": "https://cafe.naver.com/f-e/cafes/30487307/articles/1005",
            "image_urls": ["https://picsum.photos/400/300"]
        }
    ]
    
    return CrawlResult(status=True, posts=posts)

def crawl_cafe(config: dict, use_mock: bool = False, reference_date: date = None) -> CrawlResult:
    """
    Main entry point for crawling. Calls mock_crawl if use_mock is True,
    otherwise runs the Playwright crawler.
    """
    if use_mock:
        return mock_crawl(config, reference_date)
        
    if reference_date is None:
        reference_date = date.today()
        
    board_url = config.get("cafe", {}).get("board_url")
    if not board_url:
        return CrawlResult(status=False, reason="No board_url configured in config.yaml")
        
    # Extract cafe ID from board URL
    cafe_match = re.search(r'/cafes/(\d+)', board_url)
    if not cafe_match:
        return CrawlResult(status=False, reason=f"Could not parse cafe ID from board URL: {board_url}")
    cafe_id = cafe_match.group(1)
    
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return CrawlResult(status=False, reason="playwright library is not installed")
        
    try:
        with sync_playwright() as p:
            logger.info("Launching headless browser...")
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            
            # Inject cookies if present in environment variable
            cookies_json = os.environ.get("NAVER_COOKIES")
            if cookies_json:
                try:
                    import json
                    cookies = json.loads(cookies_json)
                    context.add_cookies(cookies)
                    logger.info("Successfully injected login cookies into Playwright context.")
                except Exception as ex:
                    logger.error(f"Failed to inject NAVER_COOKIES: {ex}")
            
            page = context.new_page()
            logger.info(f"Navigating to board URL: {board_url}")
            
            # Use domcontentloaded for faster loading and wait manually
            page.goto(board_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(5000) # Wait 5s for dynamic content
            
            # Parse list page
            logger.info("Parsing list page article links...")
            article_locators = page.locator("a.article").all()
            
            raw_posts = []
            for item in article_locators:
                href = item.get_attribute("href")
                title = item.inner_text()
                
                if not href or not title:
                    continue
                    
                # Exclude comment links
                if "commentFocus=true" in href:
                    continue
                    
                post_match = re.search(r'/articles/(\d+)', href)
                if post_match:
                    post_id = post_match.group(1)
                    # Construct clean desktop/mobile link
                    clean_link = f"https://cafe.naver.com/f-e/cafes/{cafe_id}/articles/{post_id}"
                    raw_posts.append({
                        "post_id": post_id,
                        "title": title.strip(),
                        "link": clean_link,
                        "image_urls": []
                    })
            
            logger.info(f"Found {len(raw_posts)} articles on the first page.")
            
            # Filter posts before navigating to details page
            subscriptions = config.get("subscriptions", [])
            matched_posts = []
            
            for post in raw_posts:
                parsed = parse_title(post["title"], subscriptions, reference_date)
                # Only crawl if today's post and matching subscribed restaurant
                if parsed["date"] == reference_date and parsed["matched_restaurant"]:
                    # Limit to 5 detail pages max to avoid rate limits/blocks
                    if len(matched_posts) >= 5:
                        logger.warning("Reached limit of 5 matched posts. Skipping remaining.")
                        break
                    matched_posts.append(post)
                    
            logger.info(f"Matched {len(matched_posts)} posts to crawl details for.")
            
            # Crawl details for matched posts
            for post in matched_posts:
                # Direct content page URL (bypassing the outermost iframe wrapper if loaded directly)
                detail_url = f"https://cafe.naver.com/ca-fe/cafes/{cafe_id}/articles/{post['post_id']}?fromNext=true"
                logger.info(f"Fetching article detail: {detail_url}")
                
                detail_page = context.new_page()
                try:
                    detail_page.goto(detail_url, wait_until="domcontentloaded", timeout=20000)
                    detail_page.wait_for_timeout(3000) # Wait 3s for images to render
                    
                    # Locate images with class se-image-resource
                    img_locators = detail_page.locator("img.se-image-resource").all()
                    image_urls = []
                    for img in img_locators:
                        src = img.get_attribute("src")
                        if src:
                            image_urls.append(src)
                            
                    post["image_urls"] = image_urls
                    logger.info(f"Post {post['post_id']} has {len(image_urls)} images.")
                except Exception as detail_err:
                    logger.error(f"Error crawling details for post {post['post_id']}: {detail_err}")
                finally:
                    detail_page.close()
                
                # 2 second sleep between posts as requested
                page.wait_for_timeout(2000)
                
            browser.close()
            return CrawlResult(status=True, posts=matched_posts)
            
    except Exception as e:
        logger.error(f"Error during Playwright crawling: {e}")
        return CrawlResult(status=False, reason=str(e))

def download_images(image_urls: list, temp_dir: str = "temp_images") -> list:
    """
    Downloads images to a local directory for API processing.
    """
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
        
    local_paths = []
    for i, url in enumerate(image_urls):
        local_path = os.path.join(temp_dir, f"image_{i}_{int(datetime.now().timestamp())}.jpg")
        try:
            if url.startswith("http"):
                req = urllib.request.Request(
                    url, 
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
                )
                with urllib.request.urlopen(req, timeout=10) as response, open(local_path, 'wb') as out_file:
                    out_file.write(response.read())
                local_paths.append(local_path)
            else:
                # Mock path helper
                with open(local_path, "w") as f:
                    f.write("mock image data")
                local_paths.append(local_path)
        except Exception as e:
            logger.warning(f"Failed to download image {url}: {e}")
    return local_paths
