import logging
from functools import wraps
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.conf import settings
from django.utils import timezone
from .models import MpesaPayment, Subscription

logger = logging.getLogger('storefront.payment')

def log_payment_error(payment_id, error_message, error_type="payment_error"):
    """Log payment-related errors"""
    logger.error(f"Payment Error ({error_type}) - Payment ID: {payment_id} - {error_message}")

def log_subscription_event(subscription_id, event_type, details):
    """Log subscription lifecycle events"""
    logger.info(f"Subscription Event - ID: {subscription_id} - Type: {event_type} - Details: {details}")

def monitor_payment_status(func):
    """Decorator to monitor payment processing"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            # Log successful payment processing
            if hasattr(result, 'subscription_id'):
                log_subscription_event(
                    result.subscription_id,
                    "payment_processed",
                    f"Amount: {result.amount}, Status: {result.status}"
                )
            return result
        except Exception as e:
            # Log payment processing errors
            payment_id = kwargs.get('payment_id', 'unknown')
            log_payment_error(payment_id, str(e), "processing_error")
            raise
    return wrapper

def monitor_subscription_status(func):
    """Decorator to monitor subscription status changes"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            # Log subscription status changes
            if hasattr(result, 'id'):
                log_subscription_event(
                    result.id,
                    "status_changed",
                    f"New Status: {result.status}"
                )
            return result
        except Exception as e:
            subscription_id = kwargs.get('subscription_id', 'unknown')
            logger.error(f"Subscription Error - ID: {subscription_id} - {str(e)}")
            raise
    return wrapper

def handle_mpesa_error(func):
    """Decorator to handle M-Pesa API errors"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Log the error
            logger.error(f"M-Pesa API Error: {str(e)}")
            
            # Return appropriate response based on environment
            if settings.DEBUG:
                return JsonResponse({
                    'status': 'error',
                    'error': str(e),
                    'type': 'mpesa_api_error'
                }, status=500)
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Payment processing failed. Please try again later.'
                }, status=500)
    return wrapper

class PaymentMonitor:
    """Class to monitor payment health and metrics"""
    
    @staticmethod
    def get_payment_success_rate(time_period=None):
        """Calculate payment success rate"""
        from django.utils import timezone
        from datetime import timedelta
        
        if time_period:
            start_time = timezone.now() - time_period
            payments = MpesaPayment.objects.filter(transaction_date__gte=start_time)
        else:
            payments = MpesaPayment.objects.all()
            
        total = payments.count()
        if total == 0:
            return 100.0
            
        successful = payments.filter(status='completed').count()
        return (successful / total) * 100

    @staticmethod
    def get_failed_payments(limit=10):
        """Get recent failed payments"""
        return MpesaPayment.objects.filter(
            status='failed'
        ).select_related('subscription__store').order_by('-transaction_date')[:limit]

    @staticmethod
    def get_subscription_metrics(time_period=None):
        """Get detailed subscription health metrics"""
        from django.db.models import Count, Avg, Sum
        from django.db.models.functions import TruncDate
        from datetime import timedelta

        if time_period:
            start_time = timezone.now() - time_period
            base_queryset = Subscription.objects.filter(started_at__gte=start_time)
        else:
            base_queryset = Subscription.objects.all()
            start_time = base_queryset.order_by('started_at').first().started_at if base_queryset.exists() else timezone.now()

        total = base_queryset.count()
        active = base_queryset.filter(status='active').count()
        trialing = base_queryset.filter(status='trialing').count()
        past_due = base_queryset.filter(status='past_due').count()
        cancelled = base_queryset.filter(status='cancelled').count()

        # Daily subscription trends
        daily_trends = base_queryset.annotate(
            date=TruncDate('started_at')
        ).values('date').annotate(
            new_subscriptions=Count('id')
        ).order_by('-date')[:30]

        # Trial conversion rate
        trials_ended = base_queryset.filter(
            trial_ends_at__lte=timezone.now(),
            started_at__gte=start_time
        ).count()
        
        converted_trials = base_queryset.filter(
            trial_ends_at__lte=timezone.now(),
            started_at__gte=start_time,
            status='active'
        ).count()

        trial_conversion_rate = (converted_trials / trials_ended * 100) if trials_ended > 0 else 0

        # Revenue metrics
        successful_payments = MpesaPayment.objects.filter(
            status='completed',
            transaction_date__gte=start_time
        )
        
        total_revenue = successful_payments.aggregate(
            total=Sum('amount')
        )['total'] or 0

        avg_revenue_per_subscription = successful_payments.aggregate(
            avg=Avg('amount')
        )['avg'] or 0

        # Retention metrics
        thirty_days_ago = timezone.now() - timedelta(days=30)
        subs_30_days_ago = base_queryset.filter(
            started_at__lte=thirty_days_ago
        ).count()
        
        still_active = base_queryset.filter(
            started_at__lte=thirty_days_ago,
            status='active'
        ).count()

        retention_rate = (still_active / subs_30_days_ago * 100) if subs_30_days_ago > 0 else 0

        # Calculate monthly recurring revenue (MRR)
        active_paid_subs = base_queryset.filter(
            status='active',
            trial_ends_at__lte=timezone.now()
        ).count()
        mrr = active_paid_subs * 999  # KSh 999 per subscription

        return {
            'total_subscriptions': total,
            'active_subscriptions': active,
            'trialing_subscriptions': trialing,
            'past_due_subscriptions': past_due,
            'cancelled_subscriptions': cancelled,
            'active_rate': (active / total * 100) if total > 0 else 0,
            'churn_rate': (cancelled / total * 100) if total > 0 else 0,
            'trial_conversion_rate': trial_conversion_rate,
            'retention_rate': retention_rate,
            'total_revenue': total_revenue,
            'avg_revenue_per_subscription': avg_revenue_per_subscription,
            'mrr': mrr,
            'daily_trends': list(daily_trends),
            'period_start': start_time,
            'days_in_period': (timezone.now() - start_time).days
        }

def alert_on_high_failure_rate(threshold=30):
    """Alert if payment failure rate exceeds threshold"""
    from datetime import timedelta
    
    # Check last hour's failure rate
    failure_rate = 100 - PaymentMonitor.get_payment_success_rate(timedelta(hours=1))
    
    if failure_rate > threshold:
        logger.critical(
            f"High payment failure rate detected: {failure_rate:.2f}% "
            f"(threshold: {threshold}%)"
        )
        # TODO: Implement additional alerting (email, SMS, etc.)