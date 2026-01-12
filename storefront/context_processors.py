# storefront/context_processors.py
from .models import Store, Subscription
from listings.models import Listing
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from .models import Store, InventoryAlert
from django.db import DatabaseError, OperationalError


def store_context(request):
    """Add store-related context to all templates"""
    context = {}
    
    if request.user.is_authenticated:
        # Get user's stores
        user_stores = Store.objects.filter(owner=request.user)
        
        # Get active subscriptions (treat 'trialing' as active only if trial hasn't ended)
        from django.db.models import Q
        now = timezone.now()
        active_subscriptions = Subscription.objects.filter(
            store__owner=request.user
        ).filter(
            Q(status='active') | Q(status='trialing', trial_ends_at__gt=now)
        )
        
        # Check if user has premium store
        has_premium_store = user_stores.filter(is_premium=True).exists()
        
        context.update({
            'user_stores': user_stores,
            'active_subscriptions': active_subscriptions,
            'has_premium_store': has_premium_store,
            'total_user_stores': user_stores.count(),
        })
    
    return context


def subscription_context(request):
    if request.user.is_authenticated:
        free_limit = getattr(settings, 'STORE_FREE_LISTING_LIMIT', 5)
        user_listing_count = Listing.objects.filter(seller=request.user).count()
        remaining_free = max(free_limit - user_listing_count, 0)
        
        return {
            'free_listing_limit': free_limit,
            'user_listing_count': user_listing_count,
            'remaining_free_listings': remaining_free,
            'has_reached_limit': user_listing_count >= free_limit,
        }
    return {}

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