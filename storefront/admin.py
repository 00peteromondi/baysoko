# storefront/admin.py
from django.contrib import admin
from django.utils import timezone
from django.urls import reverse
from django.utils.html import format_html
from .models import Store, StoreReview, ReviewHelpful, Subscription, MpesaPayment


class StoreReviewInline(admin.TabularInline):
    """Inline for store reviews in admin"""
    model = StoreReview
    extra = 0
    readonly_fields = ['created_at', 'updated_at']
    can_delete = True
    fields = ['reviewer', 'rating', 'comment', 'helpful_count', 'created_at']


class MpesaPaymentInline(admin.TabularInline):
    """Inline for M-Pesa payments in admin"""
    model = MpesaPayment
    extra = 0
    readonly_fields = ['created_at', 'updated_at', 'checkout_request_id', 'merchant_request_id']
    can_delete = False
    fields = ['phone_number', 'amount', 'status', 'mpesa_receipt_number', 'transaction_date', 'created_at']


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    """Admin configuration for Store model"""
    list_display = ['name', 'owner', 'is_premium', 'is_active', 'get_listing_count', 'get_rating', 'created_at']
    list_filter = ['is_premium', 'is_active', 'created_at']
    search_fields = ['name', 'owner__username', 'owner__email', 'description']
    readonly_fields = ['slug', 'created_at', 'updated_at']
    inlines = [StoreReviewInline]
    
    fieldsets = (
        ('Store Information', {
            'fields': ('owner', 'name', 'slug', 'description', 'location', 'policies')
        }),
        ('Media', {
            'fields': ('logo', 'cover_image')
        }),
        ('Status', {
            'fields': ('is_premium', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_listing_count(self, obj):
        """Get number of listings for this store"""
        try:
            return obj.listings.count()
        except:
            return 0
    get_listing_count.short_description = 'Listings'
    
    def get_rating(self, obj):
        """Get store rating"""
        try:
            return obj.get_rating()
        except:
            return 0
    get_rating.short_description = 'Rating'
    
    def view_on_site(self, obj):
        """Link to view store on site"""
        return reverse('storefront:store_detail', kwargs={'slug': obj.slug})


@admin.register(StoreReview)
class StoreReviewAdmin(admin.ModelAdmin):
    """Admin configuration for StoreReview model"""
    list_display = ['store', 'reviewer', 'rating', 'helpful_count', 'created_at']
    list_filter = ['rating', 'created_at', 'store']
    search_fields = ['store__name', 'reviewer__username', 'comment']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Review Details', {
            'fields': ('store', 'reviewer', 'rating', 'comment')
        }),
        ('Metrics', {
            'fields': ('helpful_count',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ReviewHelpful)
class ReviewHelpfulAdmin(admin.ModelAdmin):
    """Admin configuration for ReviewHelpful model"""
    list_display = ['review', 'user', 'created_at']
    list_filter = ['created_at']
    search_fields = ['review__comment', 'user__username']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Helpful Vote', {
            'fields': ('review', 'user')
        }),
        ('Timestamp', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    """Admin configuration for Subscription model"""
    list_display = ['store', 'plan', 'status', 'amount', 'expires_at', 'started_at', 'is_active', 'view_store_link']
    list_filter = ['status', 'plan', 'started_at']
    search_fields = ['store__name', 'store__owner__username', 'mpesa_phone']
    readonly_fields = ['started_at', 'created_at', 'updated_at', 'expires_at']
    inlines = [MpesaPaymentInline]
    actions = ['activate_subscriptions', 'cancel_subscriptions']
    
    fieldsets = (
        ('Subscription Details', {
            'fields': ('store', 'plan', 'status', 'amount', 'currency')
        }),
        ('Billing Dates', {
            'fields': ('trial_ends_at', 'current_period_end', 'canceled_at')
        }),
        ('Payment Information', {
            'fields': ('mpesa_phone',)
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('started_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def expires_at(self, obj):
        """Display expiration date in admin"""
        if obj.expires_at:
            return obj.expires_at.strftime('%Y-%m-%d %H:%M')
        return "N/A"
    expires_at.short_description = 'Expires At'
    expires_at.admin_order_field = 'current_period_end'
    
    def is_active(self, obj):
        """Display active status in admin"""
        return obj.is_active()
    is_active.boolean = True
    is_active.short_description = 'Active'
    
    def view_store_link(self, obj):
        """Link to store in admin"""
        url = reverse('storefront:store_detail', kwargs={'slug': obj.store.slug})
        return format_html('<a href="{}" target="_blank">View Store</a>', url)
    view_store_link.short_description = 'Store Link'
    
    def activate_subscriptions(self, request, queryset):
        """Admin action to activate subscriptions"""
        updated = queryset.update(status='active')
        self.message_user(request, f'{updated} subscription(s) activated.')
    activate_subscriptions.short_description = "Activate selected subscriptions"
    
    def cancel_subscriptions(self, request, queryset):
        """Admin action to cancel subscriptions"""
        for subscription in queryset:
            subscription.cancel()
        self.message_user(request, f'{queryset.count()} subscription(s) cancelled.')
    cancel_subscriptions.short_description = "Cancel selected subscriptions"


@admin.register(MpesaPayment)
class MpesaPaymentAdmin(admin.ModelAdmin):
    """Admin configuration for MpesaPayment model"""
    list_display = ['subscription', 'phone_number', 'amount', 'status', 'mpesa_receipt_number', 'transaction_date', 'created_at']
    list_filter = ['status', 'transaction_date', 'created_at']
    search_fields = ['subscription__store__name', 'phone_number', 'mpesa_receipt_number']
    readonly_fields = ['created_at', 'updated_at', 'checkout_request_id', 'merchant_request_id']
    
    fieldsets = (
        ('Payment Details', {
            'fields': ('subscription', 'phone_number', 'amount', 'status')
        }),
        ('M-Pesa Transaction', {
            'fields': ('checkout_request_id', 'merchant_request_id', 'mpesa_receipt_number', 'transaction_date')
        }),
        ('Response Data', {
            'fields': ('result_code', 'result_description'),
            'classes': ('collapse',)
        }),
        ('Raw Response', {
            'fields': ('raw_response',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_completed', 'mark_as_failed']
    
    def mark_as_completed(self, request, queryset):
        """Admin action to mark payments as completed"""
        updated = queryset.update(status='completed')
        self.message_user(request, f'{updated} payment(s) marked as completed.')
    mark_as_completed.short_description = "Mark selected payments as completed"
    
    def mark_as_failed(self, request, queryset):
        """Admin action to mark payments as failed"""
        updated = queryset.update(status='failed')
        self.message_user(request, f'{updated} payment(s) marked as failed.')
    mark_as_failed.short_description = "Mark selected payments as failed"


# storefront/admin.py
from .models_trial import UserTrial

@admin.register(UserTrial)
class UserTrialAdmin(admin.ModelAdmin):
    list_display = ['user', 'trial_number', 'store', 'status', 'started_at', 'ended_at', 'days_used']
    list_filter = ['status', 'trial_number', 'started_at']
    search_fields = ['user__email', 'store__name', 'store__slug']
    readonly_fields = ['created_at', 'updated_at']
    actions = ['export_trial_data', 'flag_for_review']
    
    fieldsets = (
        ('Trial Information', {
            'fields': ('user', 'store', 'subscription', 'trial_number', 'status')
        }),
        ('Dates', {
            'fields': ('started_at', 'ended_at', 'days_used')
        }),
        ('Usage Metrics', {
            'fields': ('features_accessed', 'conversion_attempts')
        }),
        ('Audit Trail', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def export_trial_data(self, request, queryset):
        """Export trial data as CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="trial_data.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'User Email', 'Trial Number', 'Store', 'Status', 
            'Started At', 'Ended At', 'Days Used', 'Features Accessed'
        ])
        
        for trial in queryset:
            writer.writerow([
                trial.user.email,
                trial.trial_number,
                trial.store.name,
                trial.status,
                trial.started_at.strftime('%Y-%m-%d %H:%M:%S'),
                trial.ended_at.strftime('%Y-%m-%d %H:%M:%S') if trial.ended_at else '',
                trial.days_used,
                ', '.join(trial.features_accessed) if trial.features_accessed else ''
            ])
        
        return response
    
    export_trial_data.short_description = "Export selected trials as CSV"
    
    def flag_for_review(self, request, queryset):
        """Flag trials for manual review"""
        for trial in queryset:
            trial.metadata = trial.metadata or {}
            trial.metadata['flagged_for_review'] = {
                'by_admin': request.user.email,
                'at': timezone.now().isoformat(),
                'reason': 'manual_flag',
            }
            trial.save()
        
        self.message_user(request, f"{queryset.count()} trials flagged for review.")
    
    flag_for_review.short_description = "Flag selected trials for review"