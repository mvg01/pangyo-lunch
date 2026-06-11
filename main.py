import os
import argparse
import yaml
import logging
from datetime import date, datetime
import state
import crawler
import menu_extractor
import notifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("pangyo_lunch_bot")

def load_config(config_path: str = "config.yaml") -> dict:
    """Loads subscription configuration from config.yaml."""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load config {config_path}: {e}")
        return {"subscriptions": []}

def run_pipeline(args):
    logger.info("Starting Pangyo Lunch Bot pipeline...")
    
    # 1. Load config and state
    config = load_config(args.config)
    subscriptions = config.get("subscriptions", [])
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    
    current_state = state.load_state(args.state_file)
    
    # Determine reference date (for testing, can be overridden)
    reference_date = date.today()
    if args.date:
        reference_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        
    date_str = reference_date.strftime("%Y-%m-%d")
    logger.info(f"Running for date: {date_str} (Mock: {args.mock})")
    
    # 2. Get posts (Mock or Real crawling)
    if args.mock:
        crawl_result = crawler.mock_crawl(config, reference_date)
    else:
        crawl_result = crawler.crawl_cafe(config, use_mock=False, reference_date=reference_date)
        
    if not crawl_result.status:
        error_msg = f"Crawl failed: {crawl_result.reason}"
        logger.error(error_msg)
        notifier.send_error(webhook_url, error_msg, use_mock=args.mock)
        return
        
    posts = crawl_result.posts
    logger.info(f"Crawled {len(posts)} posts from cafe.")
    
    # Track which restaurants have posts today
    found_restaurants = set()
    processed_count = 0
    
    # 3. Process each post
    for post in posts:
        post_id = post.get("post_id")
        title = post.get("title")
        link = post.get("link")
        image_urls = post.get("image_urls", [])
        
        # Check if already processed
        if state.is_seen(current_state, post_id):
            logger.info(f"Post {post_id} already processed. Skipping.")
            # Record restaurant as found if already processed before
            parsed = crawler.parse_title(title, subscriptions, reference_date)
            if parsed["matched_restaurant"] and parsed["date"] == reference_date:
                found_restaurants.add(parsed["matched_restaurant"])
            continue
            
        # Parse title
        parsed = crawler.parse_title(title, subscriptions, reference_date)
        post_date = parsed.get("date")
        restaurant = parsed.get("matched_restaurant")
        
        # Filter out if date doesn't match or not a subscribed restaurant
        if not post_date or post_date != reference_date:
            logger.debug(f"Skipping post {post_id} (Date mismatch or not parsed): '{title}'")
            continue
            
        if not restaurant:
            logger.debug(f"Skipping post {post_id} (No subscribed restaurant match): '{title}'")
            continue
            
        logger.info(f"Processing post {post_id} for '{restaurant}' - '{title}'")
        found_restaurants.add(restaurant)
        
        # Download images
        local_images = []
        if image_urls:
            local_images = crawler.download_images(image_urls)
            
        # Extract menu from first image (fallback to text-only if none/fails)
        menu_data = {
            "is_menu_board": False,
            "restaurant_name_on_image": restaurant,
            "date_on_image": date_str,
            "menus": [],
            "price": None,
            "uncertain_items": [],
            "notes": None
        }
        
        if local_images:
            # We pass use_mock to extraction as well
            menu_data = menu_extractor.extract_menu_from_image(
                local_images[0], 
                restaurant, 
                use_mock=args.mock
            )
            
        # Slack notification
        first_image_url = image_urls[0] if image_urls else None
        success = notifier.send_slack_message(
            webhook_url=webhook_url,
            restaurant_name=restaurant,
            date_str=date_str,
            menu_data=menu_data,
            post_link=link,
            image_url=first_image_url,
            use_mock=args.mock
        )
        
        if success:
            state.mark_seen(current_state, date_str, post_id)
            processed_count += 1
            
    # 4. Handle edge case: missing posts alert in late execution (10:40)
    # Check if run time is 10:40 (passed in via arg or detected as late morning KST)
    is_late_run = False
    if args.time == "10:40":
        is_late_run = True
    else:
        # Auto-detect if current KST time is after 10:30 (when run without args)
        # Assuming GitHub actions runs on schedule
        now = datetime.now()
        if now.hour > 10 or (now.hour == 10 and now.minute >= 30):
            is_late_run = True
            
    if is_late_run:
        logger.info("Performing missing posts check for late execution.")
        for sub in subscriptions:
            restaurant_name = sub.get("name")
            if restaurant_name not in found_restaurants:
                # We haven't seen this restaurant's menu today
                alert_key = f"alert_sent:{restaurant_name}"
                
                # Check if we already alerted for this today
                if not state.is_seen(current_state, alert_key):
                    alert_msg = f"오늘 {restaurant_name} 메뉴 글이 아직 등록되지 않았습니다."
                    logger.warning(alert_msg)
                    # Notify Slack
                    success = notifier.send_error(webhook_url, alert_msg, use_mock=args.mock)
                    if success:
                        state.mark_seen(current_state, date_str, alert_key)
                        
    # 5. Cleanup and save state
    current_state = state.cleanup_old_entries(current_state, reference_date)
    state.save_state(current_state, args.state_file)
    logger.info(f"Pipeline finished. Processed {processed_count} new posts.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pangyo Lunch Bot")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--state-file", default="seen.json", help="Path to seen.json")
    parser.add_argument("--mock", action="store_true", default=False, help="Run in mock mode")
    parser.add_argument("--date", help="Override run date (YYYY-MM-DD) for testing")
    parser.add_argument("--time", choices=["10:00", "10:40"], help="Override run time (10:00 or 10:40) for missing checks")
    
    args = parser.parse_args()
    
    # Default to mock if environment is not set up
    if not os.environ.get("GEMINI_API_KEY") and not os.environ.get("SLACK_WEBHOOK_URL"):
        logger.info("No API keys found in environment. Defaulting --mock to True.")
        args.mock = True
        
    run_pipeline(args)
