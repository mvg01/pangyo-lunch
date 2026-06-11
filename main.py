import os
import argparse
import yaml
import logging
from datetime import date, datetime
from dotenv import load_dotenv
load_dotenv()
import state
import crawler
import menu_extractor
import notifier

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("pangyo_lunch_bot")

def load_config(config_path: str = "config.yaml") -> dict:
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load config {config_path}: {e}")
        return {"subscriptions": []}

def run_pipeline(args):
    logger.info("Starting Pangyo Lunch Bot pipeline...")

    config = load_config(args.config)
    subscriptions = config.get("subscriptions", [])

    current_state = state.load_state(args.state_file)

    reference_date = date.today()
    if args.date:
        reference_date = datetime.strptime(args.date, "%Y-%m-%d").date()

    date_str = reference_date.strftime("%Y-%m-%d")
    logger.info(f"Running for date: {date_str} (Mock: {args.mock})")

    # 크롤링
    if args.mock:
        crawl_result = crawler.mock_crawl(config, reference_date)
    else:
        crawl_result = crawler.crawl_cafe(config, use_mock=False, reference_date=reference_date)

    if not crawl_result.status:
        logger.error(f"Crawl failed: {crawl_result.reason}")
        notifier.generate_html(args.menus_file, subscriptions, reference_date)
        return

    posts = crawl_result.posts
    logger.info(f"Crawled {len(posts)} posts from cafe.")

    found_restaurants = set()
    processed_count = 0

    for post in posts:
        post_id = post.get("post_id")
        title = post.get("title")
        link = post.get("link")
        image_urls = post.get("image_urls", [])

        if state.is_seen(current_state, post_id):
            logger.info(f"Post {post_id} already processed. Skipping.")
            parsed = crawler.parse_title(title, subscriptions, reference_date)
            if parsed["matched_restaurant"] and parsed["date"] == reference_date:
                found_restaurants.add(parsed["matched_restaurant"])
            continue

        parsed = crawler.parse_title(title, subscriptions, reference_date)
        post_date = parsed.get("date")
        restaurant = parsed.get("matched_restaurant")

        if not post_date or post_date != reference_date:
            logger.debug(f"Skipping post {post_id} (date mismatch): '{title}'")
            continue

        if not restaurant:
            logger.debug(f"Skipping post {post_id} (no restaurant match): '{title}'")
            continue

        logger.info(f"Processing post {post_id} for '{restaurant}' - '{title}'")
        found_restaurants.add(restaurant)

        local_images = []
        if image_urls:
            local_images = crawler.download_images(image_urls)

        menu_data = {
            "is_menu_board": False,
            "restaurant_name_on_image": restaurant,
            "date_on_image": date_str,
            "menus": [],
            "price": None,
            "uncertain_items": [],
            "notes": None,
        }

        if local_images:
            menu_data = menu_extractor.extract_menu_from_image(
                local_images,
                restaurant,
                use_mock=args.mock,
            )

        notifier.save_menu(args.menus_file, date_str, restaurant, menu_data, link)
        state.mark_seen(current_state, date_str, post_id)
        processed_count += 1

    # 마지막 실행(10:30)에 미등록 식당 로그 출력
    if args.last_run:
        logger.info("Last run: checking for missing restaurants.")
        for sub in subscriptions:
            if sub["name"] not in found_restaurants:
                logger.warning(f"No menu found for '{sub['name']}' today ({date_str}). Will show as 미등록.")

    # HTML 생성 (항상 실행)
    notifier.generate_html(args.menus_file, subscriptions, reference_date)

    # 상태 정리 및 저장
    notifier.cleanup_old_menus(args.menus_file, reference_date)
    current_state = state.cleanup_old_entries(current_state, reference_date)
    state.save_state(current_state, args.state_file)
    logger.info(f"Pipeline finished. Processed {processed_count} new posts.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pangyo Lunch Bot")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--state-file", default="seen.json")
    parser.add_argument("--menus-file", default="menus.json")
    parser.add_argument("--mock", action="store_true", default=False)
    parser.add_argument("--date", help="Override run date (YYYY-MM-DD)")
    parser.add_argument("--last-run", action="store_true", default=False, help="Mark as last scheduled run of the day")

    args = parser.parse_args()

    if not os.environ.get("GROQ_API_KEY"):
        logger.info("GROQ_API_KEY not set. Defaulting --mock to True.")
        args.mock = True

    run_pipeline(args)
