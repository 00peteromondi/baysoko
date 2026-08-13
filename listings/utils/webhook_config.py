"""
Environment-based webhook configuration
"""
import os
from django.conf import settings

class WebhookConfig:
    """Dynamically configure webhooks based on environment"""
    
    @staticmethod
    def get_config():
        env = os.environ.get('DJANGO_ENV', 'development')
        
        configs = {
            'development': {
                'enabled': True,
                'url': 'http://localhost:8001/webhook/baysoko/',
                'simulate': True,  # Simulate responses for development
            },
            'staging': {
                'enabled': True,
                'url': 'https://staging-delivery-api.example.com/webhook/',
                'simulate': False,
            },
            'production': {
                'enabled': True,
                'url': 'https://api.delivery-partner.com/webhook/baysoko/',
                'simulate': False,
            }
        }
        
        return configs.get(env, configs['development'])
    
    @staticmethod
    def simulate_webhook(order, event_type):
        """Simulate webhook response for development"""
        # Return fake tracking number for testing
        import random
        return {
            'success': True,
            'tracking_number': f'TRK{order.id:06d}{random.randint(1000, 9999)}',
            'estimated_delivery': '2024-12-28'
        }