# Integration example for Baysoko
# Add this to your Baysoko project

# baysoko/integrations/delivery.py
import requests
from django.conf import settings

class DeliverySystemIntegration:
    def __init__(self):
        self.api_url = getattr(settings, 'DELIVERY_SYSTEM_URL', 'http://localhost:8001/api')
        self.api_key = getattr(settings, 'DELIVERY_SYSTEM_API_KEY', '')
    
    def create_delivery_from_order(self, order):
        """Create delivery in delivery system from Baysoko order"""
        delivery_data = {
            'order_id': str(order.id),
            'marketplace': 'baysoko',
            'order_total': float(order.total_price),
            'seller_name': order.order_items.first().listing.seller.get_full_name(),
            'seller_phone': order.order_items.first().listing.seller.phone_number,
            'pickup_address': self._get_seller_address(order),
            'customer_name': f"{order.first_name} {order.last_name}",
            'customer_phone': order.phone_number,
            'delivery_address': order.shipping_address,
            'package_description': self._get_package_description(order),
            'package_weight': self._estimate_package_weight(order)
        }
        
        try:
            response = requests.post(
                f"{self.api_url}/public/deliveries/",
                json=delivery_data,
                headers={'Authorization': f'Bearer {self.api_key}'} if self.api_key else {}
            )
            
            if response.status_code == 201:
                return response.json()
            else:
                print(f"Delivery creation failed: {response.text}")
                return None
                
        except requests.RequestException as e:
            print(f"Delivery API error: {e}")
            return None
    
    def _get_seller_address(self, order):
        """Extract seller address from order"""
        # Implement based on your user model
        seller = order.order_items.first().listing.seller
        return getattr(seller, 'location', 'Homabay, Kenya')
    
    def _get_package_description(self, order):
        """Generate package description from order items"""
        items = [f"{item.quantity}x {item.listing.title}" for item in order.order_items.all()]
        return ", ".join(items)
    
    def _estimate_package_weight(self, order):
        """Estimate package weight (simplified)"""
        return sum(item.quantity for item in order.order_items.all()) * 0.5  # 0.5kg per item