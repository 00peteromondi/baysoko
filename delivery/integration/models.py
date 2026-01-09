"""
Models for e-commerce integration
"""
from django.db import models
from django.utils import timezone
import uuid
import json
from django.conf import settings


class EcommercePlatform(models.Model):
    """Registered e-commerce platforms"""
    PLATFORM_TYPES = [
        ('homabay_souq', 'HomaBay Souq'),
        ('shopify', 'Shopify'),
        ('woocommerce', 'WooCommerce'),
        ('magento', 'Magento'),
        ('custom', 'Custom Platform'),
    ]
    
    name = models.CharField(max_length=100)
    platform_type = models.CharField(max_length=20, choices=PLATFORM_TYPES)
    base_url = models.URLField()
    api_key = models.CharField(max_length=255)
    api_secret = models.CharField(max_length=255, blank=True)
    webhook_url = models.URLField(blank=True)
    webhook_secret = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    sync_enabled = models.BooleanField(default=True)
    last_sync = models.DateTimeField(null=True, blank=True)
    sync_interval = models.IntegerField(default=5, help_text="Sync interval in minutes")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'E-commerce Platform'
        verbose_name_plural = 'E-commerce Platforms'
    
    def __str__(self):
        return f"{self.name} ({self.get_platform_type_display()})"
    
    def sync_orders(self):
        """Trigger order synchronization"""
        from .sync import sync_orders_from_platform
        return sync_orders_from_platform(self)


class OrderSyncLog(models.Model):
    """Log of order synchronization attempts"""
    platform = models.ForeignKey(EcommercePlatform, on_delete=models.CASCADE, related_name='sync_logs')
    sync_type = models.CharField(max_length=20, choices=[
        ('webhook', 'Webhook'),
        ('manual', 'Manual'),
        ('scheduled', 'Scheduled'),
        ('api_pull', 'API Pull'),
    ])
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('success', 'Success'),
        ('partial', 'Partial Success'),
        ('failed', 'Failed'),
    ])
    orders_synced = models.IntegerField(default=0)
    orders_failed = models.IntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    details = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-started_at']
    
    def __str__(self):
        return f"Sync {self.platform.name} - {self.status}"


class OrderMapping(models.Model):
    """Map e-commerce platform orders to delivery requests"""
    platform = models.ForeignKey(EcommercePlatform, on_delete=models.CASCADE, related_name='order_mappings')
    platform_order_id = models.CharField(max_length=255, db_index=True)
    platform_order_number = models.CharField(max_length=255, db_index=True)
    delivery_request = models.OneToOneField('delivery.DeliveryRequest', on_delete=models.CASCADE, 
                                           related_name='order_mapping')
    raw_order_data = models.JSONField(default=dict)
    synced_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['platform', 'platform_order_id']
        indexes = [
            models.Index(fields=['platform_order_id', 'platform_order_number']),
        ]
    
    def __str__(self):
        return f"{self.platform.name} Order #{self.platform_order_number}"


class WebhookEvent(models.Model):
    """Incoming webhook events from e-commerce platforms"""
    EVENT_TYPES = [
        ('order_created', 'Order Created'),
        ('order_updated', 'Order Updated'),
        ('order_cancelled', 'Order Cancelled'),
        ('order_paid', 'Order Paid'),
        ('order_shipped', 'Order Shipped'),
        ('order_delivered', 'Order Delivered'),
        ('order_refunded', 'Order Refunded'),
        ('payment_failed', 'Payment Failed'),
    ]
    
    platform = models.ForeignKey(EcommercePlatform, on_delete=models.CASCADE, related_name='webhook_events')
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    event_id = models.CharField(max_length=255, db_index=True, default=uuid.uuid4)
    payload = models.JSONField()
    headers = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=[
        ('received', 'Received'),
        ('processing', 'Processing'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
    ], default='received')
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event_id', 'platform']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.platform.name} - {self.get_event_type_display()} - {self.created_at}"
    
    def process(self):
        """Process the webhook event"""
        from .processors import process_webhook_event
        return process_webhook_event(self)


class OrderSyncRule(models.Model):
    """Rules for order synchronization"""
    platform = models.ForeignKey(EcommercePlatform, on_delete=models.CASCADE, related_name='sync_rules')
    rule_name = models.CharField(max_length=100)
    rule_type = models.CharField(max_length=20, choices=[
        ('status_filter', 'Status Filter'),
        ('payment_filter', 'Payment Filter'),
        ('date_filter', 'Date Filter'),
        ('value_filter', 'Order Value Filter'),
        ('customer_filter', 'Customer Filter'),
    ])
    condition = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['priority']
    
    def __str__(self):
        return f"{self.rule_name} - {self.platform.name}"
    
    def evaluate(self, order_data):
        """Evaluate if order matches this rule"""
        from .sync import evaluate_sync_rule
        return evaluate_sync_rule(self, order_data)


class IntegrationConfig(models.Model):
    """Integration configuration"""
    key = models.CharField(max_length=100, unique=True)
    value = models.JSONField(default=dict)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Integration Configuration'
        verbose_name_plural = 'Integration Configurations'
    
    def __str__(self):
        return self.key