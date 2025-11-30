from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

User = get_user_model()

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('message', 'New Message'),
        ('order_placed', 'New Order'),
        ('order_shipped', 'Order Shipped'),
        ('order_delivered', 'Order Delivered'),
        ('order_disputed', 'Order Disputed'),
        ('payment_received', 'Payment Received'),
        ('review_received', 'New Review'),
        ('listing_sold', 'Listing Sold'),
        ('favorite', 'Listing Favorited'),
        ('system', 'System Notification'),
        ('promotional', 'Promotional'),
    ]

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_notifications'
    )
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    related_object_id = models.PositiveIntegerField(null=True, blank=True)
    related_content_type = models.CharField(max_length=50, blank=True)  # e.g., 'listing', 'order', 'message'
    
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # For action buttons/links
    action_url = models.CharField(max_length=500, blank=True)
    action_text = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', 'created_at']),
        ]

    def __str__(self):
        return f"{self.notification_type} - {self.recipient.username}"

    def mark_as_read(self):
        self.is_read = True
        self.save()

    @property
    def time_since(self):
        now = timezone.now()
        diff = now - self.created_at
        
        if diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds >= 3600:
            hours = diff.seconds // 3600
            return f"{hours}h ago"
        elif diff.seconds >= 60:
            minutes = diff.seconds // 60
            return f"{minutes}m ago"
        else:
            return "Just now"

    def get_absolute_url(self):
        return reverse('notification-detail', kwargs={'pk': self.pk})


class NotificationPreference(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    
    # Email notifications
    email_messages = models.BooleanField(default=True)
    email_orders = models.BooleanField(default=True)
    email_reviews = models.BooleanField(default=True)
    email_promotional = models.BooleanField(default=False)
    
    # Push notifications (in-app)
    push_messages = models.BooleanField(default=True)
    push_orders = models.BooleanField(default=True)
    push_reviews = models.BooleanField(default=True)
    push_system = models.BooleanField(default=True)
    
    # Frequency
    digest_frequency = models.CharField(
        max_length=10,
        choices=[('instant', 'Instant'), ('daily', 'Daily'), ('weekly', 'Weekly')],
        default='instant'
    )
    
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Preferences for {self.user.username}"