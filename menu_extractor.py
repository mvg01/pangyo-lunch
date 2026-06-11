import os
import json
import logging

logger = logging.getLogger(__name__)

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False
    logger.warning("easyocr not available.")

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    logger.warning("groq not available.")

_ocr_reader = None

def _get_reader():
    global _ocr_reader
    if _ocr_reader is None:
        logger.info("Initializing EasyOCR (Korean + English)...")
        _ocr_reader = easyocr.Reader(['ko', 'en'], gpu=False, verbose=False)
    return _ocr_reader


def extract_menu_from_image(image_paths, restaurant_name: str, use_mock: bool = True) -> dict:
    """image_paths는 단일 경로(str) 또는 경로 리스트를 모두 허용."""
    if isinstance(image_paths, str):
        image_paths = [image_paths]

    api_key = os.environ.get("GROQ_API_KEY")

    if use_mock or not api_key or not EASYOCR_AVAILABLE or not GROQ_AVAILABLE:
        logger.info(f"Mock mode for {restaurant_name}.")
        return get_mock_menu_response(restaurant_name)

    try:
        # Step 1: 모든 이미지에서 OCR 텍스트 추출 후 합치기
        reader = _get_reader()
        all_texts = []
        for idx, image_path in enumerate(image_paths):
            results = reader.readtext(image_path)
            text = '\n'.join([t for _, t, conf in results if conf > 0.3])
            if text.strip():
                all_texts.append(text)
                logger.info(f"OCR image {idx+1}/{len(image_paths)}: {len(text)} chars")

        raw_text = '\n---\n'.join(all_texts)

        if not raw_text.strip():
            logger.warning(f"No text extracted from any image for {restaurant_name}")
            return {"menus": [], "price": None, "notes": "이미지 텍스트 인식 실패"}

        logger.info(f"OCR extracted text ({len(raw_text)} chars) for {restaurant_name}")

        # Step 2: Groq(Llama)로 메뉴 파싱
        client = Groq(api_key=api_key)
        prompt = (
            f"다음은 '{restaurant_name}' 식당 점심 메뉴판 이미지를 OCR로 읽은 텍스트야:\n\n"
            f"{raw_text}\n\n"
            "위 텍스트에서 오늘의 점심 메뉴 항목과 가격을 추출해서 아래 JSON 형식으로만 응답해:\n"
            '{"menus": ["메뉴1", "메뉴2", ...], "price": "가격 (없으면 null)", "notes": "특이사항 (없으면 null)"}\n'
            "메뉴 항목만 리스트에 넣고 식당명, 날짜, 기타 불필요한 텍스트는 제외해."
        )

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        result = json.loads(response.choices[0].message.content)
        logger.info(f"Groq parsed menu for {restaurant_name}: {result}")
        return result

    except Exception as e:
        logger.error(f"Error during menu extraction for {restaurant_name}: {e}")
        return {"menus": [], "price": None, "notes": f"추출 오류: {str(e)[:200]}"}


def get_mock_menu_response(restaurant_name: str) -> dict:
    import datetime
    today_str = datetime.date.today().strftime("%m월 %d일")

    mock_menus = {
        "바른밥상": ["돈까스", "생선까스", "쫄면", "겉절이", "된장국"],
        "엄니한식뷔페": ["양념제육볶음", "계란말이", "콩나물무침", "시래기된장국"],
        "해담가": ["고등어구이", "간장불고기", "도토리묵무침", "미역국"],
        "정겨운맛풍경": ["오징어볶음", "동그랑땡전", "고사리나물", "감자수제비국"],
    }

    return {
        "menus": mock_menus.get(restaurant_name, ["오늘의 메뉴"]),
        "price": "9,000원",
        "notes": None,
    }
