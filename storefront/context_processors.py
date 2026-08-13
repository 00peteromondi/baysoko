# storefront/context_processors.py
from .models import Store, Subscription
from types import SimpleNamespace
from listings.models import Listing
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from .models import Store, InventoryAlert

# Mapping of plan keys to badge CSS classes used in templates
plan_color_map = {
    'free': 'plan-badge-free',
    'basic': 'plan-badge-basic',
    'premium': 'plan-badge-premium',
    'enterprise': 'plan-badge-enterprise',
}
from django.db import DatabaseError, OperationalError


def store_context(request):
    """Add store-related context to all templates"""
    context = {}
    
    if request.user.is_authenticated:
        # Get user's stores
        user_stores = Store.objects.filter(owner=request.user)
        
        # Annotate each store with current subscription plan
        annotated_stores = []
        
        for store in user_stores:
            # Get effective subscription (may return None for free plan)
            subscription = store.get_effective_subscription(owner=request.user, create_if_missing=False)
            
            # Determine plan
            if subscription:
                plan_key = subscription.plan
                plan_label = subscription.get_plan_display()
                is_trial = subscription.status == 'trialing'
            else:
                # Free plan
                plan_key = 'free'
                plan_label = 'Free'
                is_trial = False
                # Create a dummy subscription object for template
                subscription = SimpleNamespace(
                    plan='free',
                    status='none',
                    amount=0,
                    get_plan_display=lambda: 'Free',
                    get_status_display=lambda: 'Free Plan',
                    trial_ends_at=None,
                    current_period_end=None
                )
            
            # Attach transient attributes
            store.plan = plan_key
            store.current_plan = plan_key
            store.plan_label = plan_label
            store.plan_badge_class = plan_color_map.get(plan_key, 'bg-secondary')
            store.is_trialing_plan = is_trial
            store.subscription = subscription
            
            annotated_stores.append(store)
        
        context.update({
            'user_stores': annotated_stores,
            'total_user_stores': user_stores.count(),
        })
    
    return context

def subscription_context(request):
    """Add subscription information to all templates"""
    context = {}
    
    if request.user.is_authenticated:
        # Get all stores owned by user
        user_stores = request.user.stores.all()
        
        # Get active subscription for each store
        active_subscriptions = []
        for store in user_stores:
            try:
                subscription = store.get_effective_subscription(owner=request.user, create_if_missing=False)
            except Exception:
                subscription = Subscription.objects.filter(store=store).order_by('-created_at').first()

            if subscription and getattr(subscription, 'is_active', lambda: False)():
                active_subscriptions.append({
                    'store': store,
                    'subscription': subscription,
                    'is_trial': getattr(subscription, 'status', None) == 'trialing',
                    'days_remaining': (subscription.trial_ends_at - timezone.now()).days 
                        if getattr(subscription, 'status', None) == 'trialing' and getattr(subscription, 'trial_ends_at', None) 
                        else None,
                })
        
        context.update({
            'has_active_subscription': len(active_subscriptions) > 0,
            'active_subscriptions': active_subscriptions,
            'is_trialing': any(sub['is_trial'] for sub in active_subscriptions),
        })
    
    return context
    # storefront/context_processors.py

def bulk_operations_context(request):
    """
    Add bulk operations and inventory context to all templates.
    This includes:
    - Pending batch jobs
    - Recent exports
    - Inventory alerts
    - Store statistics
    """
    context = {}
    
    if request.user.is_authenticated:
        try:
            # Import batch/export models lazily; they may not exist before migrations
            try:
                from .models_bulk import BatchJob, ExportJob
            except Exception:
                BatchJob = None
                ExportJob = None

            # Get user's stores
            user_stores = Store.objects.filter(owner=request.user)
            
            if user_stores.exists():
                # Count pending batch jobs
                try:
                    pending_jobs = BatchJob.objects.filter(
                        store__in=user_stores,
                        status__in=['pending', 'processing']
                    ).count() if BatchJob else 0
                except (DatabaseError, OperationalError):
                    pending_jobs = 0
                
                # Get recent completed exports (last 7 days)
                try:
                    recent_exports = ExportJob.objects.filter(
                        store__in=user_stores,
                        status='completed',
                        created_at__gte=timezone.now() - timedelta(days=7)
                    ).order_by('-created_at')[:5] if ExportJob else []
                except (DatabaseError, OperationalError):
                    recent_exports = []
                
                # Count active inventory alerts
                try:
                    active_alerts = InventoryAlert.objects.filter(
                        store__in=user_stores,
                        is_active=True
                    ).count()
                except (DatabaseError, OperationalError):
                    active_alerts = 0
                
                # Check for critical alerts
                critical_alerts = []
                for store in user_stores:
                    # Check for low stock items
                    low_stock_items = store.listings.filter(
                        stock__lte=5,
                        stock__gt=0
                    ).count()
                    
                    out_of_stock_items = store.listings.filter(
                        stock=0
                    ).count()
                    
                    if low_stock_items > 10:
                        critical_alerts.append({
                            'store': store.name,
                            'type': 'low_stock',
                            'count': low_stock_items,
                            'message': f'{low_stock_items} products have low stock'
                        })
                    
                    if out_of_stock_items > 5:
                        critical_alerts.append({
                            'store': store.name,
                            'type': 'out_of_stock',
                            'count': out_of_stock_items,
                            'message': f'{out_of_stock_items} products are out of stock'
                        })
                
                # Get recent bulk operations (last 24 hours)
                try:
                    recent_operations = BatchJob.objects.filter(
                        store__in=user_stores,
                        created_at__gte=timezone.now() - timedelta(hours=24)
                    ).select_related('store').order_by('-created_at')[:3] if BatchJob else []
                except (DatabaseError, OperationalError):
                    recent_operations = []
                
                # Calculate inventory health score
                inventory_health_scores = []
                for store in user_stores:
                    total_products = store.listings.count()
                    if total_products > 0:
                        out_of_stock = store.listings.filter(stock=0).count()
                        low_stock = store.listings.filter(stock__lte=5, stock__gt=0).count()
                        
                        # Calculate health percentage (lower out-of-stock is better)
                        out_of_stock_percentage = (out_of_stock / total_products) * 100
                        health_percentage = 100 - min(out_of_stock_percentage, 50)  # Cap at 50% penalty
                        
                        # Adjust for low stock
                        low_stock_percentage = (low_stock / total_products) * 100
                        health_percentage -= min(low_stock_percentage / 2, 25)  # Smaller penalty for low stock
                        
                        inventory_health_scores.append({
                            'store': store,
                            'score': max(health_percentage, 0),  # Ensure non-negative
                            'total_products': total_products,
                            'out_of_stock': out_of_stock,
                            'low_stock': low_stock
                        })
                
                # Add to context
                context.update({
                    'bulk_operations_context': {
                        'pending_jobs_count': pending_jobs,
                        'has_pending_jobs': pending_jobs > 0,
                        'recent_exports': recent_exports,
                        'active_alerts_count': active_alerts,
                        'has_active_alerts': active_alerts > 0,
                        'critical_alerts': critical_alerts,
                        'has_critical_alerts': len(critical_alerts) > 0,
                        'recent_operations': recent_operations,
                        'inventory_health_scores': inventory_health_scores,
                        'total_stores': user_stores.count(),
                    }
                })
                
                # Add store-specific context if we're in a store view
                store_slug = None
                
                # Try to get store slug from URL patterns
                if hasattr(request, 'resolver_match') and request.resolver_match:
                    kwargs = request.resolver_match.kwargs
                    store_slug = kwargs.get('slug') or kwargs.get('store_slug')
                
                if store_slug:
                    try:
                        current_store = Store.objects.get(slug=store_slug, owner=request.user)
                        
                        # Store-specific stats
                        try:
                            store_pending_jobs = BatchJob.objects.filter(
                                store=current_store,
                                status__in=['pending', 'processing']
                            ).count() if BatchJob else 0
                        except (DatabaseError, OperationalError):
                            store_pending_jobs = 0
                        
                        store_low_stock = current_store.listings.filter(
                            stock__lte=5,
                            stock__gt=0
                        ).count()
                        
                        store_out_of_stock = current_store.listings.filter(stock=0).count()
                        
                        context['bulk_operations_context'].update({
                            'current_store': {
                                'name': current_store.name,
                                'slug': current_store.slug,
                                'pending_jobs': store_pending_jobs,
                                'low_stock_count': store_low_stock,
                                'out_of_stock_count': store_out_of_stock,
                                'total_products': current_store.listings.count(),
                                'is_premium': current_store.is_premium,
                            }
                        })
                    except Store.DoesNotExist:
                        pass
        
        except Exception as e:
            # Log error but don't break the site
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in bulk_operations_context: {str(e)}")
    
    return context