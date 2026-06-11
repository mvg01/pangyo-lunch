import os
import json
import logging
from typing import List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Try to import google-generativeai, but allow fallback for Phase 1 tests
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google-generativeai package not available. Real API calls will fail.")

# Define response schema using Pydantic
class MenuBoardAnalysis(BaseModel):
    is_menu_board: bool = Field(description="True if the image contains a lunch menu board/plate or written menu, False otherwise.")
    restaurant_name_on_image: Optional[str] = Field(None, description="The name of the restaurant as visible in the image.")
    date_on_image: Optional[str] = Field(None, description="The date shown on the menu board.")
    menus: List[str] = Field(default_factory=list, description="List of menu items parsed from the image.")
    price: Optional[str] = Field(None, description="Price of the meal if visible on the image.")
    uncertain_items: List[str] = Field(default_factory=list, description="Items that were blurry or hard to read.")
    notes: Optional[str] = Field(None, description="Any notes, holiday announcements, or special notices.")

def extract_menu_from_image(image_path: str, restaurant_name: str, use_mock: bool = True) -> dict:
    """
    Extracts menu from a local image file.
    If use_mock is True or Gemini API key is missing, returns mock data.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    
    if use_mock or not api_key or not GEMINI_AVAILABLE:
        logger.info(f"Running extract_menu_from_image in Mock mode for {restaurant_name}.")
        return get_mock_menu_response(restaurant_name)
        
    try:
        genai.configure(api_key=api_key)
        # Using gemini-1.5-flash as the cost-efficient/free tier model
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction="You are an expert OCR and menu analysis assistant. Analyze the uploaded image and extract the menu information."
        )
        
        # Load image file
        with open(image_path, "rb") as f:
            image_data = f.read()
            
        # Prepare content
        prompt = f"Extract the lunch menu details from this image. The restaurant is believed to be '{restaurant_name}'."
        image_part = {
            "mime_type": "image/jpeg",
            "data": image_data
        }
        
        # API call with structured output
        response = model.generate_content(
            contents=[prompt, image_part],
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=MenuBoardAnalysis,
                temperature=0.1
            )
        )
        
        result_dict = json.loads(response.text)
        logger.info(f"Successfully extracted menu from image: {result_dict}")
        return result_dict
        
    except Exception as e:
        logger.error(f"Error during Gemini API call: {e}")
        # Return fallback non-menu dict
        return {
            "is_menu_board": False,
            "restaurant_name_on_image": None,
            "date_on_image": None,
            "menus": [],
            "price": None,
            "uncertain_items": [],
            "notes": f"Error: {str(e)}"
        }

def get_mock_menu_response(restaurant_name: str) -> dict:
    """Returns realistic mock menus based on the restaurant name."""
    import datetime
    today_str = datetime.date.today().strftime("%m월 %d일")
    
    mock_menus = {
        "바른밥상": ["돈까스", "생선까스", "쫄면", "겉절이", "된장국", "단무지무침"],
        "엄니한식뷔페": ["양념제육볶음", "계란말이", "콩나물무침", "포기김치", "시래기된장국", "쌈채소"],
        "해담가": ["고등어구이", "간장불고기", "도토리묵무침", "열무김치", "미역국", "흰밥"],
        "정겨운맛풍경": ["오징어볶음", "동그랑땡전", "고사리나물", "깍두기", "감자수제비국", "잡곡밥"]
    }
    
    menus = mock_menus.get(restaurant_name, ["수제돈까스", "감자튀김", "양배추샐러드", "크림스프"])
    
    return {
        "is_menu_board": True,
        "restaurant_name_on_image": restaurant_name,
        "date_on_image": today_str,
        "menus": menus,
        "price": "9,000원",
        "uncertain_items": [],
        "notes": "국산 돼지고기 사용"
    }
