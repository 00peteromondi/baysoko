"""
AI-powered listing assistant for HomaBay Souq
Updated for OpenAI API v1.0+
"""
import os
import json
import logging
from typing import Dict, Any, Optional, List
from django.conf import settings
from openai import OpenAI
try:
    # OpenAI exception classes (may vary by version)
    from openai.error import RateLimitError, OpenAIError
except Exception:
    RateLimitError = Exception
    OpenAIError = Exception
from dotenv import load_dotenv
import time

load_dotenv()

logger = logging.getLogger(__name__)


class ListingAIHelper:
    """
    AI assistant to help users create listings by automatically
    populating missing fields based on provided information.
    """
    
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY') or getattr(settings, 'OPENAI_API_KEY', '')
        self.model = getattr(settings, 'OPENAI_MODEL', 'gpt-3.5-turbo')
        self.enabled = bool(self.api_key)
        
        # Timed disable state for quota/rate-limit errors
        self.last_error: Optional[str] = None
        self.disabled_until: Optional[float] = None
        # How long to disable AI after encountering quota/rate-limit (seconds)
        self.disable_seconds = getattr(settings, 'AI_DISABLE_SECONDS', 600)

        if self.enabled:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None
    
    def generate_listing_data(self, user_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate complete listing data from partial user input.
        """
        # If AI was previously disabled due to quota/rate-limit, check timeout
        if self.disabled_until:
            if time.time() < self.disabled_until:
                # Still disabled
                return self._fallback_generation(user_input)
            else:
                # Re-enable after timeout
                self.disabled_until = None
                self.last_error = None

        if not self.enabled or not self.client:
            logger.warning("AI disabled or client not initialized. Using fallback generation.")
            return self._fallback_generation(user_input)
        
        try:
            # Prepare prompt for AI
            prompt = self._build_enhanced_prompt(user_input)
            
            # Call OpenAI API with new syntax
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert e-commerce assistant for HomaBay Souq in Homa Bay, Kenya.
                        Your task is to create complete, detailed product listings from minimal information.
                        
                        IMPORTANT RULES:
                        1. ALWAYS fill in EVERY field with realistic, specific information
                        2. Make educated guesses based on product type and context
                        3. Use Kenyan market context and pricing
                        4. Be specific with technical details
                        5. If a field is not specified, infer it from the product type
                        6. Return ONLY valid JSON with no additional text"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=1500,
                response_format={"type": "json_object"}
            )
            
            # Parse response
            content = response.choices[0].message.content
            logger.info(f"AI Response: {content}")

            ai_data = self._parse_ai_response(content, user_input)
            
            # Ensure all required fields are present
            ai_data = self._ensure_complete_data(ai_data, user_input)
            
            return ai_data
            
        except RateLimitError as e:
            # Disable AI temporarily to avoid repeated failing calls and fallback
            self.last_error = str(e)
            self.disabled_until = time.time() + self.disable_seconds
            logger.warning(f"OpenAI rate limit / quota error: {self.last_error}. Disabling AI until {self.disabled_until}.")
            return self._fallback_generation(user_input)
        except OpenAIError as e:
            # Generic OpenAI error
            self.last_error = str(e)
            logger.error(f"OpenAI error: {self.last_error}", exc_info=True)
            # Do not always disable; just fallback this time
            return self._fallback_generation(user_input)
        except Exception as e:
            logger.error(f"AI listing generation failed: {str(e)}", exc_info=True)
            return self._fallback_generation(user_input)
    
    def _build_enhanced_prompt(self, user_input: Dict[str, Any]) -> str:
        """Build an enhanced prompt that forces AI to fill all fields."""
        title = user_input.get('title', '').strip()
        description = user_input.get('description', '').strip()
        
        prompt = f"""
        Create a complete product listing for HomaBay Souq e-commerce marketplace in Homa Bay, Kenya.
        
        PRODUCT INFORMATION:
        Title: {title if title else "Not provided"}
        Description: {description if description else "Not provided"}
        
        REQUIRED FIELDS TO FILL (MUST COMPLETE ALL):
        
        1. title: {title if title else "Generate a catchy, descriptive title for the product"}
        2. description: Detailed product description including features, specifications, and condition
        3. category: MUST be one of: Electronics, Fashion, Home & Garden, Vehicles, Real Estate, 
           Services, Jobs, Education, Health & Beauty, Sports & Fitness, Food & Agriculture, 
           Construction, Events, Other
        4. condition: 'new', 'used', or 'refurbished' - infer from title/description
        5. price: Realistic price in Kenyan Shillings (KES) based on product type
        6. brand: Specific brand name (e.g., Samsung, Nike, Apple, etc.)
        7. model: Specific model name/number
        8. dimensions: Physical dimensions in format "10x5x3 inches" or "30x20x15 cm"
        9. weight: Weight in kg or grams (e.g., "0.5 kg", "150g")
        10. color: Specific color(s)
        11. material: Primary material(s)
        12. delivery_option: 'pickup', 'delivery', or 'shipping' - choose based on product size/weight
        13. location: MUST be one of: HB_Town, Kendu_Bay, Rodi_Kopany, Mbita, Oyugis, Rangwe, Ndhiwa, Suba
        14. meta_description: SEO-friendly description under 160 characters
        
        EXAMPLE FOR "iPhone 17 Pro Max":
        - brand: "Apple"
        - model: "iPhone 17 Pro Max"
        - dimensions: "160.8x78.1x7.8 mm"
        - weight: "221g"
        - color: "Titanium Black, Titanium White, Titanium Blue, Titanium Natural"
        - material: "Titanium frame, Ceramic Shield front"
        - price: "180000" (KES)
        - condition: "new"
        - category: "Electronics"
        
        INSTRUCTIONS:
        - If information is missing, MAKE EDUCATED GUESSES based on typical products
        - Be SPECIFIC and DETAILED for all fields
        - Use realistic Kenyan market prices
        - Include technical specifications when applicable
        - For electronics: include screen size, storage, battery, etc. in description
        - For fashion: include size, fabric, style in description
        - For vehicles: include year, mileage, fuel type in description
        
        RETURN ONLY JSON with this exact structure:
        {{
            "title": "string",
            "description": "string",
            "category": "string",
            "condition": "string",
            "price": "number or string",
            "brand": "string",
            "model": "string",
            "dimensions": "string",
            "weight": "string",
            "color": "string",
            "material": "string",
            "delivery_option": "string",
            "location": "string",
            "meta_description": "string"
        }}
        """
        
        return prompt
    
    def _parse_ai_response(self, content: str, user_input: Dict[str, Any]) -> Dict[str, Any]:
        """Parse AI response and merge with user input."""
        try:
            # Clean the response
            content = content.strip()
            
            # Remove any markdown code blocks
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            
            ai_data = json.loads(content)
            
            # Convert price to string if it's a number
            if 'price' in ai_data:
                if isinstance(ai_data['price'], (int, float)):
                    ai_data['price'] = str(ai_data['price'])
            
            return ai_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response: {str(e)}. Content: {content[:500]}")
            return self._fallback_generation(user_input)
        except Exception as e:
            logger.error(f"Error parsing AI response: {str(e)}")
            return self._fallback_generation(user_input)
    
    def _ensure_complete_data(self, ai_data: Dict[str, Any], user_input: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure all required fields have values, filling missing ones with defaults."""
        # Field-specific default generators
        def get_default_brand(title: str) -> str:
            title_lower = title.lower()
            if 'iphone' in title_lower or 'apple' in title_lower:
                return "Apple"
            elif 'samsung' in title_lower:
                return "Samsung"
            elif 'nike' in title_lower:
                return "Nike"
            elif 'adidas' in title_lower:
                return "Adidas"
            elif 'toyota' in title_lower:
                return "Toyota"
            else:
                return "Various"
        
        def get_default_category(title: str) -> str:
            title_lower = title.lower()
            categories = {
                'electronics': ['phone', 'laptop', 'tv', 'computer', 'electronic', 'tablet', 'camera', 'charger'],
                'fashion': ['shirt', 'dress', 'shoe', 'clothing', 'fashion', 'wear', 'jacket', 'jeans', 'bag'],
                'home & garden': ['furniture', 'bed', 'table', 'garden', 'plant', 'home', 'kitchen', 'sofa'],
                'vehicles': ['car', 'bike', 'motorcycle', 'vehicle', 'truck', 'van', 'suv'],
                'real estate': ['house', 'land', 'apartment', 'property', 'rent', 'sell'],
                'health & beauty': ['beauty', 'health', 'cosmetic', 'perfume', 'cream', 'vitamin', 'makeup'],
                'sports & fitness': ['sport', 'fitness', 'gym', 'ball', 'racket', 'equipment'],
                'food & agriculture': ['food', 'agriculture', 'crop', 'fruit', 'vegetable', 'grain'],
            }
            
            for category, keywords in categories.items():
                if any(keyword in title_lower for keyword in keywords):
                    return category.title()
            return "Other"
        
        def get_default_dimensions(category: str) -> str:
            category_lower = category.lower()
            if 'electronics' in category_lower:
                return "Varies by model"
            elif 'fashion' in category_lower:
                return "Varies by size"
            elif 'home' in category_lower:
                return "Varies by item"
            else:
                return "Standard size"
        
        def get_default_weight(category: str) -> str:
            category_lower = category.lower()
            if 'electronics' in category_lower:
                return "0.2-2 kg"
            elif 'fashion' in category_lower:
                return "0.1-1 kg"
            elif 'home' in category_lower:
                return "1-50 kg"
            else:
                return "1 kg"
        
        def get_default_color(title: str) -> str:
            title_lower = title.lower()
            colors = ['black', 'white', 'blue', 'red', 'green', 'silver', 'gold', 'gray', 'brown']
            for color in colors:
                if color in title_lower:
                    return color.title()
            return "Various"
        
        def get_default_material(category: str) -> str:
            category_lower = category.lower()
            if 'electronics' in category_lower:
                return "Metal, Glass, Plastic"
            elif 'fashion' in category_lower:
                return "Cotton, Polyester, Leather"
            elif 'home' in category_lower:
                return "Wood, Metal, Fabric"
            else:
                return "Various"
        
        # Get title for defaults
        title = user_input.get('title', ai_data.get('title', ''))
        
        # Ensure all fields have values
        defaults = {
            'title': title or "Product Listing",
            'description': user_input.get('description') or f"{title}. Available in Homa Bay, Kenya.",
            'category': user_input.get('category') or ai_data.get('category') or get_default_category(title),
            'condition': user_input.get('condition') or ai_data.get('condition') or 'new',
            'price': user_input.get('price') or ai_data.get('price') or '1000',
            'brand': user_input.get('brand') or ai_data.get('brand') or get_default_brand(title),
            'model': user_input.get('model') or ai_data.get('model') or title.split()[-1] if title else "Standard",
            'dimensions': user_input.get('dimensions') or ai_data.get('dimensions') or get_default_dimensions(ai_data.get('category', '')),
            'weight': user_input.get('weight') or ai_data.get('weight') or get_default_weight(ai_data.get('category', '')),
            'color': user_input.get('color') or ai_data.get('color') or get_default_color(title),
            'material': user_input.get('material') or ai_data.get('material') or get_default_material(ai_data.get('category', '')),
            'delivery_option': user_input.get('delivery_option') or ai_data.get('delivery_option') or 'delivery',
            'location': user_input.get('location') or ai_data.get('location') or 'HB_Town',
            'meta_description': user_input.get('meta_description') or ai_data.get('meta_description') or f"Buy {title} in Homa Bay, Kenya. Best prices and quality guaranteed."
        }
        
        # Update ai_data with defaults for missing fields
        for key, default_value in defaults.items():
            if key not in ai_data or not ai_data[key] or str(ai_data[key]).strip() == '':
                ai_data[key] = default_value
        
        return ai_data
    
    def _fallback_generation(self, user_input: Dict[str, Any]) -> Dict[str, Any]:
        """Enhanced fallback method when AI is disabled or fails."""
        title = user_input.get('title', '')
        
        # Enhanced product recognition
        product_info = self._analyze_product(title)
        
        result = {
            'title': title or 'Product for Sale',
            'description': user_input.get('description') or product_info.get('description', f'{title}. Available in Homa Bay, Kenya.'),
            'category': user_input.get('category') or product_info.get('category', 'Other'),
            'condition': user_input.get('condition') or 'new',
            'price': user_input.get('price') or product_info.get('price', '10000'),
            'brand': user_input.get('brand') or product_info.get('brand', 'Various'),
            'model': user_input.get('model') or product_info.get('model', 'Standard'),
            'dimensions': user_input.get('dimensions') or product_info.get('dimensions', 'Varies'),
            'weight': user_input.get('weight') or product_info.get('weight', '1 kg'),
            'color': user_input.get('color') or product_info.get('color', 'Various'),
            'material': user_input.get('material') or product_info.get('material', 'Various'),
            'delivery_option': user_input.get('delivery_option') or 'delivery',
            'location': user_input.get('location') or 'HB_Town',
            'meta_description': user_input.get('meta_description') or f"Buy {title} in Homa Bay, Kenya. Quality products at great prices."
        }
        
        return result
    
    def _analyze_product(self, title: str) -> Dict[str, str]:
        """Analyze product title to extract information."""
        title_lower = title.lower()
        
        # Product database (expand as needed)
        products = {
            'iphone': {
                'category': 'Electronics',
                'brand': 'Apple',
                'model': title.split()[-1] if title else 'iPhone',
                'dimensions': '160.8x78.1x7.8 mm',
                'weight': '221g',
                'color': 'Titanium Black',
                'material': 'Titanium, Glass',
                'price': '180000',
                'description': f'{title}. Latest Apple iPhone with advanced features, high-resolution camera, and long battery life.'
            },
            'samsung': {
                'category': 'Electronics',
                'brand': 'Samsung',
                'model': title.split()[-1] if title else 'Galaxy',
                'dimensions': 'Varies by model',
                'weight': '200g',
                'color': 'Black',
                'material': 'Glass, Metal',
                'price': '120000',
                'description': f'{title}. Samsung smartphone with excellent display and camera features.'
            },
            'laptop': {
                'category': 'Electronics',
                'brand': 'Various',
                'model': 'Laptop',
                'dimensions': '30x20x2 cm',
                'weight': '1.5 kg',
                'color': 'Silver',
                'material': 'Aluminum, Plastic',
                'price': '80000',
                'description': f'{title}. Portable computer for work, study, and entertainment.'
            },
            'shirt': {
                'category': 'Fashion',
                'brand': 'Various',
                'model': 'Shirt',
                'dimensions': 'Varies by size',
                'weight': '0.3 kg',
                'color': 'White',
                'material': 'Cotton',
                'price': '1500',
                'description': f'{title}. Comfortable and stylish shirt for everyday wear.'
            },
            'shoe': {
                'category': 'Fashion',
                'brand': 'Various',
                'model': 'Shoes',
                'dimensions': 'Varies by size',
                'weight': '0.8 kg',
                'color': 'Black',
                'material': 'Leather, Rubber',
                'price': '5000',
                'description': f'{title}. Comfortable shoes for daily use or special occasions.'
            }
        }
        
        # Find matching product
        for product_key, product_info in products.items():
            if product_key in title_lower:
                return product_info
        
        # Generic product info
        return {
            'category': 'Other',
            'brand': 'Various',
            'model': 'Standard',
            'dimensions': 'Varies',
            'weight': '1 kg',
            'color': 'Various',
            'material': 'Various',
            'price': '5000',
            'description': f'{title}. Quality product available in Homa Bay, Kenya.'
        }
    
    def suggest_categories(self, title: str, description: str = '') -> List[Dict[str, Any]]:
        """Suggest categories based on product title and description."""
        # Respect temporary disable state
        if self.disabled_until:
            if time.time() < self.disabled_until:
                return self._suggest_categories_fallback(title)
            else:
                self.disabled_until = None
                self.last_error = None

        if not self.enabled or not self.client:
            return self._suggest_categories_fallback(title)
        
        try:
            prompt = f"""
            Given this product: "{title}"
            Description: "{description}"
            
            Suggest the 3 most relevant categories from this exact list:
            Electronics, Fashion, Home & Garden, Vehicles, Real Estate, 
            Services, Jobs, Education, Health & Beauty, Sports & Fitness, 
            Food & Agriculture, Construction, Events, Other
            
            Return ONLY JSON array with objects containing id and name:
            [{{"id": 1, "name": "Electronics"}}, {{"id": 2, "name": "Fashion"}}]
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a category classifier. Return only JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=200,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            try:
                data = json.loads(content)
                if isinstance(data, list):
                    return data[:3]
                elif 'categories' in data:
                    return data['categories'][:3]
            except:
                pass
                
        except RateLimitError as e:
            self.last_error = str(e)
            self.enabled = False
            logger.warning(f"OpenAI rate limit / quota error during category suggestion: {self.last_error}. Disabling AI temporarily.")
            return self._suggest_categories_fallback(title)
        except OpenAIError as e:
            self.last_error = str(e)
            logger.error(f"OpenAI error during category suggestion: {self.last_error}")
            return self._suggest_categories_fallback(title)
        except Exception as e:
            logger.error(f"AI category suggestion failed: {str(e)}")
        
        return self._suggest_categories_fallback(title)
    
    def _suggest_categories_fallback(self, title: str) -> List[Dict[str, Any]]:
        """Fallback category suggestion."""
        from .models import Category
        
        title_lower = title.lower()
        
        # Map keywords to category names
        keyword_mapping = {
            'Electronics': ['phone', 'laptop', 'tv', 'computer', 'electronic', 'charger', 'cable', 'tablet', 'camera'],
            'Fashion': ['shirt', 'dress', 'shoe', 'clothing', 'fashion', 'wear', 'jacket', 'jeans', 'bag', 'accessory'],
            'Home & Garden': ['furniture', 'bed', 'table', 'garden', 'plant', 'home', 'kitchen', 'sofa', 'chair'],
            'Vehicles': ['car', 'bike', 'motorcycle', 'vehicle', 'truck', 'van', 'suv', 'cycle'],
            'Real Estate': ['house', 'land', 'apartment', 'property', 'rent', 'sell', 'plot'],
            'Health & Beauty': ['beauty', 'health', 'cosmetic', 'perfume', 'cream', 'vitamin', 'makeup', 'skincare'],
            'Sports & Fitness': ['sport', 'fitness', 'gym', 'ball', 'racket', 'equipment', 'exercise'],
        }
        
        suggested_names = []
        for category_name, keywords in keyword_mapping.items():
            if any(keyword in title_lower for keyword in keywords):
                suggested_names.append(category_name)
        
        # Get actual category objects
        if suggested_names:
            categories = Category.objects.filter(name__in=suggested_names, is_active=True)[:3]
            return [{'id': cat.id, 'name': cat.name} for cat in categories]
        
        # Default fallback
        default_cat = Category.objects.filter(is_active=True).first()
        if default_cat:
            return [{'id': default_cat.id, 'name': default_cat.name}]
        
        return [{'id': 0, 'name': 'Other'}]


# Global instance
listing_ai = ListingAIHelper()

