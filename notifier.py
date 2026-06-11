import os
import json
import logging
import requests

logger = logging.getLogger(__name__)

def send_slack_message(webhook_url: str, restaurant_name: str, date_str: str, menu_data: dict, post_link: str, image_url: str = None, use_mock: bool = True) -> bool:
    """
    Sends a formatted menu message to Slack using Block Kit.
    If use_mock is True or webhook_url is missing, it will log the payload instead.
    """
    menus = menu_data.get("menus", [])
    price = menu_data.get("price")
    notes = menu_data.get("notes")
    
    # Format menus as bullet points
    if menus:
        menu_text = "\n".join([f"• {item}" for item in menus])
    else:
        menu_text = "_메뉴판 이미지 판독 불가 또는 메뉴 없음 (본문 이미지를 확인해 주세요)_"
        
    # Build block list
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🍚 {restaurant_name} — {date_str} 메뉴",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*오늘의 메뉴 목록*\n{menu_text}"
            }
        }
    ]
    
    # Add price and notes if available
    context_elements = []
    if price:
        context_elements.append({"type": "mrkdwn", "text": f"*가격:* {price}"})
    if notes:
        context_elements.append({"type": "mrkdwn", "text": f"*참고사항:* {notes}"})
        
    if context_elements:
        blocks.append({
            "type": "context",
            "elements": context_elements
        })
        
    # Add Action link button to original post
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "네이버 카페 원본 글 보기 🔗",
                    "emoji": True
                },
                "url": post_link,
                "action_id": "view_original_post"
            }
        ]
    })
    
    # Add Image Block if we have an image URL
    if image_url:
        blocks.append({
            "type": "image",
            "image_url": image_url,
            "alt_text": f"{restaurant_name} 메뉴판 사진"
        })
        
    blocks.append({"type": "divider"})

    payload = {"blocks": blocks}

    if use_mock or not webhook_url:
        logger.info(f"Running send_slack_message in Mock mode for {restaurant_name}.")
        # Pretty print to stdout/logging
        print(f"\n--- [SLACK MOCK NOTIFICATION] ---")
        print(f"Header: 🍚 {restaurant_name} — {date_str} 메뉴")
        print(f"Content:\n{menu_text}")
        if price or notes:
            print(f"Details: Price={price}, Notes={notes}")
        print(f"Link: {post_link}")
        if image_url:
            print(f"Image URL: {image_url}")
        print(f"---------------------------------\n")
        return True
        
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info(f"Slack notification sent successfully for {restaurant_name}.")
            return True
        else:
            logger.error(f"Failed to send Slack notification: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending Slack notification: {e}")
        return False

def send_error(webhook_url: str, message: str, use_mock: bool = True) -> bool:
    """
    Sends an error notification to Slack.
    """
    payload = {
        "text": f"⚠️ *판교 점심 메뉴 알림 봇 에러 발생*\n{message}"
    }
    
    if use_mock or not webhook_url:
        logger.error(f"[SLACK MOCK ERROR] {message}")
        return True
        
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Error sending Slack error notification: {e}")
        return False
