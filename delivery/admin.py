from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.contrib.auth.models import User, Group
from .models import (
    DeliveryService, DeliveryPerson, DeliveryZone, DeliveryRequest,
    DeliveryStatusHistory, DeliveryProof, DeliveryRoute,
    DeliveryRating, DeliveryNotification, DeliveryPricingRule,
    DeliveryPackageType, DeliveryTimeSlot, DeliveryInsurance,
    DeliveryAnalytics
)
from django.utils import timezone

@admin.register(DeliveryService)
class DeliveryServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'service_type', 'base_price', 'is_active', 'created_at']
    list_filter = ['service_type', 'is_active']
    search_fields = ['name', 'description']
    list_editable = ['is_active']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'service_type', 'description', 'is_active')
        }),
        ('Pricing', {
            'fields': ('base_price', 'price_per_kg', 'price_per_km')
        }),
        ('Service Details', {
            'fields': ('estimated_days_min', 'estimated_days_max', 'service_areas')
        }),
        ('API Configuration', {
            'fields': ('api_endpoint', 'api_key'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(DeliveryPerson)
class DeliveryPersonAdmin(admin.ModelAdmin):
    list_display = ['employee_id', 'user', 'vehicle_type', 'current_status', 'is_available', 'rating']
    list_filter = ['vehicle_type', 'current_status', 'is_available', 'is_verified']
    search_fields = ['employee_id', 'user__username', 'user__email', 'phone']
    readonly_fields = ['created_at', 'updated_at', 'total_deliveries', 'completed_deliveries']
    list_editable = ['is_available']
    fieldsets = (
        ('Personal Information', {
            'fields': ('user', 'employee_id', 'phone')
        }),
        ('Vehicle Information', {
            'fields': ('vehicle_type', 'vehicle_registration')
        }),
        ('Status & Location', {
            'fields': ('current_status', 'is_available', 'current_latitude', 'current_longitude')
        }),
        ('Capabilities', {
            'fields': ('max_weight_capacity', 'service_radius')
        }),
        ('Performance', {
            'fields': ('rating', 'total_deliveries', 'completed_deliveries')
        }),
        ('Verification', {
            'fields': ('is_verified', 'verification_document')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(DeliveryZone)
class DeliveryZoneAdmin(admin.ModelAdmin):
    list_display = ['name', 'delivery_fee', 'min_order_amount', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    list_editable = ['is_active', 'delivery_fee']
    readonly_fields = ['created_at']
    fieldsets = (
        ('Zone Information', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Geographical Data', {
            'fields': ('polygon_coordinates', 'center_latitude', 'center_longitude', 'radius_km')
        }),
        ('Pricing', {
            'fields': ('delivery_fee', 'min_order_amount')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


class DeliveryStatusHistoryInline(admin.TabularInline):
    model = DeliveryStatusHistory
    extra = 0
    readonly_fields = ['old_status', 'new_status', 'changed_by', 'notes', 'created_at']
    can_delete = False
    max_num = 10


class DeliveryProofInline(admin.TabularInline):
    model = DeliveryProof
    extra = 0
    readonly_fields = ['proof_type', 'file', 'created_at']
    can_delete = False
    max_num = 3


@admin.register(DeliveryRequest)
class DeliveryRequestAdmin(admin.ModelAdmin):
    list_display = ['tracking_number', 'order_id', 'status', 'priority', 'recipient_name', 
                    'delivery_fee', 'created_at', 'delivery_person']
    list_filter = ['status', 'priority', 'payment_status', 'created_at']
    search_fields = ['tracking_number', 'order_id', 'recipient_name', 'recipient_phone']
    readonly_fields = ['created_at', 'updated_at', 'tracking_number', 'calculate_distance']
    list_editable = ['status', 'priority']
    inlines = [DeliveryStatusHistoryInline, DeliveryProofInline]
    
    fieldsets = (
        ('Tracking Information', {
            'fields': ('tracking_number', 'order_id', 'external_order_ref', 'status', 'priority')
        }),
        ('Pickup Details', {
            'fields': ('pickup_name', 'pickup_address', 'pickup_phone', 'pickup_email', 'pickup_notes')
        }),
        ('Delivery Details', {
            'fields': ('recipient_name', 'recipient_address', 'recipient_phone', 
                      'recipient_email', 'delivery_zone')
        }),
        ('Package Information', {
            'fields': ('package_description', 'package_weight', 'declared_value',
                      'is_fragile', 'requires_signature')
        }),
        ('Service Assignment', {
            'fields': ('delivery_service', 'delivery_person')
        }),
        ('Financial Information', {
            'fields': ('delivery_fee', 'tax_amount', 'insurance_fee', 'total_amount', 'payment_status')
        }),
        ('Timestamps', {
            'fields': ('pickup_time', 'estimated_delivery_time', 'actual_delivery_time',
                      'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
        ('Additional Information', {
            'fields': ('notes', 'metadata'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_delivered', 'assign_to_random_driver', 'calculate_all_distances']
    
    def mark_as_delivered(self, request, queryset):
        updated = 0
        for delivery in queryset:
            delivery.status = 'delivered'
            delivery.actual_delivery_time = timezone.now()
            delivery.save()
            updated += 1
        
        self.message_user(request, f"{updated} deliveries marked as delivered.")
    mark_as_delivered.short_description = "Mark selected deliveries as delivered"
    
    def assign_to_random_driver(self, request, queryset):
        from django.db.models import Count
        available_drivers = DeliveryPerson.objects.filter(
            is_available=True, 
            current_status='available'
        ).annotate(
            delivery_count=Count('assignments')
        ).order_by('delivery_count')
        
        if available_drivers.exists():
            for delivery in queryset.filter(status='accepted'):
                driver = available_drivers.first()
                delivery.delivery_person = driver
                delivery.status = 'assigned'
                delivery.save()
                available_drivers = available_drivers.exclude(id=driver.id)
            self.message_user(request, f"Assigned {queryset.count()} deliveries to available drivers.")
        else:
            self.message_user(request, "No available drivers found.", level='error')
    
    def calculate_all_distances(self, request, queryset):
        for delivery in queryset:
            distance = delivery.calculate_distance()
            if distance:
                delivery.metadata['calculated_distance_km'] = distance
                delivery.save()
        self.message_user(request, f"Calculated distances for {queryset.count()} deliveries.")


@admin.register(DeliveryStatusHistory)
class DeliveryStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ['delivery_request', 'old_status', 'new_status', 'changed_by', 'created_at']
    list_filter = ['new_status', 'created_at']
    search_fields = ['delivery_request__tracking_number', 'notes']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'


@admin.register(DeliveryProof)
class DeliveryProofAdmin(admin.ModelAdmin):
    list_display = ['delivery_request', 'proof_type', 'recipient_name', 'created_at']
    list_filter = ['proof_type', 'created_at']
    search_fields = ['delivery_request__tracking_number', 'recipient_name']
    readonly_fields = ['created_at']


@admin.register(DeliveryRoute)
class DeliveryRouteAdmin(admin.ModelAdmin):
    list_display = ['route_name', 'delivery_person', 'total_distance', 'is_completed', 'created_at']
    list_filter = ['is_completed', 'created_at']
    search_fields = ['route_name', 'delivery_person__user__username']
    readonly_fields = ['created_at']
    filter_horizontal = ['deliveries']


@admin.register(DeliveryRating)
class DeliveryRatingAdmin(admin.ModelAdmin):
    list_display = ['delivery_request', 'rating', 'on_time', 'would_recommend', 'created_at']
    list_filter = ['rating', 'on_time', 'would_recommend']
    search_fields = ['delivery_request__tracking_number', 'comment']
    readonly_fields = ['created_at']


@admin.register(DeliveryNotification)
class DeliveryNotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'notification_type', 'title', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['user__username', 'title', 'message']
    readonly_fields = ['created_at']
    list_editable = ['is_read']


@admin.register(DeliveryPricingRule)
class DeliveryPricingRuleAdmin(admin.ModelAdmin):
    list_display = ['name', 'rule_type', 'base_price', 'price_modifier', 'is_active', 'priority']
    list_filter = ['rule_type', 'is_active']
    search_fields = ['name']
    list_editable = ['is_active', 'priority']
    filter_horizontal = ['applies_to']


@admin.register(DeliveryPackageType)
class DeliveryPackageTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'base_price', 'max_weight', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    list_editable = ['is_active', 'base_price']


@admin.register(DeliveryTimeSlot)
class DeliveryTimeSlotAdmin(admin.ModelAdmin):
    list_display = ['delivery_service', 'day_of_week', 'start_time', 'end_time', 'is_available', 'is_active']
    list_filter = ['day_of_week', 'is_active', 'delivery_service']
    list_editable = ['is_active']


@admin.register(DeliveryInsurance)
class DeliveryInsuranceAdmin(admin.ModelAdmin):
    list_display = ['name', 'coverage_amount', 'premium_rate', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    list_editable = ['is_active']


@admin.register(DeliveryAnalytics)
class DeliveryAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['date', 'total_deliveries', 'completed_deliveries', 'total_revenue', 'average_delivery_time']
    list_filter = ['date']
    readonly_fields = ['created_at']
    date_hierarchy = 'date'


# Custom Admin Site Configuration
admin.site.site_header = "Delivery Management System"
admin.site.site_title = "Delivery Management"
admin.site.index_title = "Welcome to Delivery Management System"