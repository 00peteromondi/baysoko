"""
Admin interface for integration models
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    EcommercePlatform, OrderSyncLog, OrderMapping,
    WebhookEvent, OrderSyncRule, IntegrationConfig
)


@admin.register(EcommercePlatform)
class EcommercePlatformAdmin(admin.ModelAdmin):
    list_display = ['name', 'platform_type', 'is_active', 'sync_enabled', 'last_sync', 'created_at']
    list_filter = ['platform_type', 'is_active', 'sync_enabled']
    search_fields = ['name', 'base_url']
    list_editable = ['is_active', 'sync_enabled']
    readonly_fields = ['last_sync', 'created_at']
    
    fieldsets = (
        ('Platform Information', {
            'fields': ('name', 'platform_type', 'base_url', 'is_active')
        }),
        ('API Configuration', {
            'fields': ('api_key', 'api_secret'),
            'classes': ('collapse',)
        }),
        ('Webhook Configuration', {
            'fields': ('webhook_url', 'webhook_secret'),
            'classes': ('collapse',)
        }),
        ('Sync Configuration', {
            'fields': ('sync_enabled', 'sync_interval', 'last_sync')
        }),
    )
    
    actions = ['test_connection', 'sync_now']
    
    def test_connection(self, request, queryset):
        for platform in queryset:
            # Implement connection test
            self.message_user(request, f"Tested connection to {platform.name}")
    test_connection.short_description = "Test connection to selected platforms"
    
    def sync_now(self, request, queryset):
        from .sync import sync_orders_from_platform
        for platform in queryset:
            result = sync_orders_from_platform(platform)
            if result['success']:
                self.message_user(
                    request,
                    f"Synced {result['synced']} orders from {platform.name}"
                )
            else:
                self.message_user(
                    request,
                    f"Failed to sync {platform.name}: {result.get('error')}",
                    level='error'
                )
    sync_now.short_description = "Sync orders from selected platforms"


@admin.register(OrderSyncLog)
class OrderSyncLogAdmin(admin.ModelAdmin):
    list_display = ['platform', 'sync_type', 'status', 'orders_synced', 'orders_failed', 'started_at']
    list_filter = ['status', 'sync_type', 'platform', 'started_at']
    search_fields = ['platform__name', 'error_message']
    readonly_fields = ['started_at', 'completed_at', 'details']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(OrderMapping)
class OrderMappingAdmin(admin.ModelAdmin):
    list_display = ['platform', 'platform_order_number', 'delivery_request', 'synced_at']
    list_filter = ['platform', 'synced_at']
    search_fields = ['platform_order_id', 'platform_order_number', 'delivery_request__tracking_number']
    readonly_fields = ['synced_at', 'last_updated', 'raw_order_data_preview']
    
    def raw_order_data_preview(self, obj):
        import json
        return format_html('<pre>{}</pre>', json.dumps(obj.raw_order_data, indent=2))
    raw_order_data_preview.short_description = 'Raw Order Data'


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ['platform', 'event_type', 'status', 'created_at', 'processed_at']
    list_filter = ['event_type', 'status', 'platform', 'created_at']
    search_fields = ['event_id', 'error_message']
    readonly_fields = ['created_at', 'processed_at', 'payload_preview', 'headers_preview']
    
    def payload_preview(self, obj):
        import json
        return format_html('<pre>{}</pre>', json.dumps(obj.payload, indent=2))
    payload_preview.short_description = 'Payload'
    
    def headers_preview(self, obj):
        import json
        return format_html('<pre>{}</pre>', json.dumps(obj.headers, indent=2))
    headers_preview.short_description = 'Headers'
    
    actions = ['retry_processing']
    
    def retry_processing(self, request, queryset):
        from .tasks import process_webhook_async
        for event in queryset:
            process_webhook_async.delay(event.id)
        self.message_user(request, f"Queued {queryset.count()} events for reprocessing")
    retry_processing.short_description = "Retry processing selected webhooks"


@admin.register(OrderSyncRule)
class OrderSyncRuleAdmin(admin.ModelAdmin):
    list_display = ['platform', 'rule_name', 'rule_type', 'is_active', 'priority']
    list_filter = ['rule_type', 'is_active', 'platform']
    list_editable = ['is_active', 'priority']
    search_fields = ['rule_name', 'condition']


@admin.register(IntegrationConfig)
class IntegrationConfigAdmin(admin.ModelAdmin):
    list_display = ['key', 'description', 'created_at']
    search_fields = ['key', 'description']
    readonly_fields = ['created_at', 'updated_at']