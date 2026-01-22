from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .decorators import store_owner_required, analytics_access_required, store_limit_check
from django.contrib import messages
from django.conf import settings
from .models import Store, Subscription, MpesaPayment
from django.urls import reverse
from django.core.exceptions import ValidationError
from listings.models import Listing, Category, Favorite
from listings.forms import ListingForm
from .forms import StoreForm
from listings.models import ListingImage
from django.db.models import F, Sum, Count, Avg

from django.utils import timezone
from datetime import timedelta
from .mpesa import MpesaGateway
from .forms import UpgradeForm
from django.db.models import Q, Sum, Count, Avg
from django.contrib.admin.views.decorators import staff_member_required
from .monitoring import PaymentMonitor
from reviews.models import Review
from listings.models import OrderItem
from .utils import dumps_with_decimals
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseRedirect




from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import transaction
import logging


logger = logging.getLogger(__name__)


def store_list(request):
    stores = Store.objects.filter()
    premium_count = Store.objects.filter(is_premium=True).count()
    total_products = sum(store.listings.count() for store in stores)
    
    context = {
        'stores': stores,
        'premium_count': premium_count,
        'total_products': total_products
    }
    
    # Add plan-related context for authenticated users
    if request.user.is_authenticated:
        from .utils.plan_permissions import PlanPermissions
        context['plan_limits'] = PlanPermissions.get_plan_limits(request.user)
        context['can_create_store'] = PlanPermissions.can_create_store(request.user)
    
    return render(request, 'storefront/store_list.html', context)

def store_detail(request, slug):
    store = get_object_or_404(Store, slug=slug)
    # Only show listings associated with this specific store
    products = Listing.objects.filter(store=store, is_active=True)
    user_favorites = []
    if request.user.is_authenticated:
        user_favorites = Favorite.objects.filter(
            user=request.user, 
            listing__in=store.listings.all()
        ).values_list('listing_id', flat=True)
    
    context = {'store': store, 'products': products, 'user_favorites': user_favorites}
    
    # Add plan-related context for authenticated users
    if request.user.is_authenticated:
        from .utils.plan_permissions import PlanPermissions
        context['plan_limits'] = PlanPermissions.get_plan_limits(request.user, store)
        context['can_create_listing'] = PlanPermissions.can_create_listing(request.user, store)
    
    return render(request, 'storefront/store_detail.html', context)


def product_detail(request, store_slug, slug):

    store = get_object_or_404(Store, slug=store_slug)
    # Only show products associated with this specific store
    product = get_object_or_404(Listing, store=store, slug=slug, is_active=True)
    user_favorites = []
    if request.user.is_authenticated:
        user_favorites = Favorite.objects.filter(
            user=request.user, 
            listing__in=store.listings.all()
        ).values_list('listing_id', flat=True)

    return render(request, 'storefront/product_detail.html', {'store': store, 'product': product, 'user_favorites': user_favorites})

@login_required
def seller_dashboard(request):
    from .utils.plan_permissions import PlanPermissions
    
    # Get visible stores based on plan
    stores = PlanPermissions.get_visible_stores(request.user)
    
    # Get visible listings based on plan
    user_listings = PlanPermissions.get_visible_listings(request.user)
    
    # Compute metrics only for visible stores/listings
    total_listings = user_listings.count()
    premium_stores = stores.filter(is_premium=True).count()
    total_views = user_listings.aggregate(total=Sum('views'))['total'] or 0

    # Get plan limits for display
    limits = PlanPermissions.get_plan_limits(request.user)
    free_limit = limits['max_products']
    remaining = max(free_limit - total_listings, 0)
    percentage_used = (total_listings / free_limit * 100) if free_limit > 0 else 0

    store_with_slug = stores.filter(slug__isnull=False).exclude(slug='').first()

    return render(request, 'storefront/dashboard.html', {
        'stores': stores,
        'total_listings': total_listings,
        'premium_stores': premium_stores,
        'total_views': total_views,
        'free_limit': free_limit,
        'remaining_slots': remaining,
        'percentage_used': min(percentage_used, 100),
        'user_listings': user_listings,
        'store_with_slug': store_with_slug,
        'plan_limits': limits,
        'plan_status': PlanPermissions.get_user_plan_status(request.user)
    })

@login_required
@login_required
@store_limit_check
def store_create(request):
    """
    Create a new store with enforced subscription-based limits.
    Users can only create multiple stores if they have a premium store or active subscription.
    """
    # Check existing stores and subscription status
    existing_stores = Store.objects.filter(owner=request.user)
    has_premium = existing_stores.filter(is_premium=True).exists()
    has_active_subscription = Subscription.objects.filter(store__owner=request.user, status='active').exists()

    # Enforce store limit for free users
    if existing_stores.exists() and not (has_premium or has_active_subscription):
        first_store = existing_stores.first()
        messages.warning(request, 'You must upgrade to Pro (subscribe) to create additional storefronts.')
        return redirect('storefront:store_edit', slug=first_store.slug)

    # Show store creation confirmation for users coming from listing creation
    if request.GET.get('from') == 'listing':
        return render(request, 'storefront/confirm_store_create.html')

    if request.method == 'POST':
        form = StoreForm(request.POST, request.FILES, user=request.user)  # Pass user to form
        if form.is_valid():
            store = form.save(commit=False)
            store.owner = request.user
            
            # For new stores, is_featured should always be False initially
            store.is_featured = False
            
            try:
                # This will trigger the clean() method which enforces store limits
                store.full_clean()
                store.save()

                # Process logo and cover image
                if 'logo' in request.FILES:
                    store.logo = request.FILES['logo']
                if 'cover_image' in request.FILES:
                    store.cover_image = request.FILES['cover_image']
                store.save()

                messages.success(request, 'Store created successfully!')
                return redirect('storefront:seller_dashboard')
                
            except ValidationError as e:
                # Handle all validation errors
                messages.error(request, str(e))
                # Also add to form errors so they display in the template
                for field, errors in e.message_dict.items():
                    if field == '__all__':  # Non-field errors
                        form.add_error(None, errors[0])
                    else:
                        form.add_error(field, errors[0])
        
        # If form is invalid, add all errors to messages
        for field, errors in form.errors.items():
            if field == '__all__':
                messages.error(request, errors[0])
            else:
                messages.error(request, f"{field.title()}: {errors[0]}")

    else:
        form = StoreForm(user=request.user)

    context = {
        'form': form,
        'creating_store': True,
        'has_existing_store': existing_stores.exists(),
        'has_premium': has_premium,
        'has_active_subscription': has_active_subscription,
        'can_be_featured': False,  # New stores cannot be featured
        'is_enterprise': False,     # New stores are not enterprise
    }
    return render(request, 'storefront/store_form.html', context)


@login_required
@store_owner_required
def store_edit(request, slug):
    """
    Edit an existing store with proper form handling and validation.
    """
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    
    # Check if store can be featured (has active subscription or valid trial)
    can_be_featured = False
    is_enterprise = False
    
    # Only check if store has a primary key
    if store.pk:
        try:
            has_active = Subscription.objects.filter(
                store=store, 
                status='active'
            ).exists()
            has_valid_trial = Subscription.objects.filter(
                store=store,
                status='trialing',
                trial_ends_at__gt=timezone.now()
            ).exists()
            can_be_featured = has_active or has_valid_trial
            
            # Check if it's enterprise
            if can_be_featured:
                is_enterprise = Subscription.objects.filter(
                    store=store,
                    status='active',
                    plan='enterprise'
                ).exists()
        except Exception as e:
            # If there's any error with subscription check, default to not featured
            print(f"Error checking subscription: {e}")
            can_be_featured = False
            is_enterprise = False
    
    if request.method == 'POST':
        form = StoreForm(request.POST, request.FILES, instance=store, user=request.user)
        
        if form.is_valid():
            try:
                store = form.save()
                
                messages.success(request, "Store updated successfully!")
                return redirect('storefront:store_detail', slug=store.slug)
                
            except ValidationError as e:
                messages.error(request, f"Validation error: {str(e)}")
                return render(request, 'storefront/store_form.html', {
                    'form': form,
                    'store': store,
                    'creating_store': False,
                    'can_be_featured': can_be_featured,
                    'is_enterprise': is_enterprise,
                })
            except Exception as e:
                messages.error(request, f"Error updating store: {str(e)}")
                return render(request, 'storefront/store_form.html', {
                    'form': form,
                    'store': store,
                    'creating_store': False,
                    'can_be_featured': can_be_featured,
                    'is_enterprise': is_enterprise,
                })
        else:
            # Form is invalid, show errors
            messages.error(request, "Please correct the errors below.")
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    
    else:
        # GET request - initialize form with instance
        form = StoreForm(instance=store, user=request.user)
    
    context = {
        'form': form,
        'store': store,
        'creating_store': False,
        'can_be_featured': can_be_featured,
        'is_enterprise': is_enterprise,
    }
    
    return render(request, 'storefront/store_form.html', context)

@login_required
@store_owner_required
def product_create(request, store_slug):
    """
    Create a listing for the user's storefront. Behavior:
    - Enforce a per-user free listing limit (FREE_LISTING_LIMIT).
    - Auto-create a single Store for the user if they don't have one yet.
    - If the provided store_slug doesn't match the user's store, redirect to the correct store slug.
    """
    FREE_LISTING_LIMIT = getattr(settings, 'STORE_FREE_LISTING_LIMIT', 5)

    # Count all listings created by this user (global per-user limit)
    user_listing_count = Listing.objects.filter(seller=request.user).count()

    # Get or create the user's single storefront
    user_store = Store.objects.filter(owner=request.user).first()

    # If user reached limit and is not premium, prompt upgrade
    is_premium = user_store.is_premium if user_store else False
    if not is_premium and user_listing_count >= FREE_LISTING_LIMIT:
        store_for_template = user_store or Store(owner=request.user, name=f"{request.user.username}'s Store", slug=request.user.username)
        messages.warning(request, f"You've reached the free listing limit ({FREE_LISTING_LIMIT}). Upgrade to premium to add more listings.")
        return render(request, 'storefront/subscription_manage.html', {
            'store': store_for_template,
            'limit_reached': True,
            'current_count': user_listing_count,
            'free_limit': FREE_LISTING_LIMIT,
        })

    # If the user does not have a store, require they create one first instead of auto-creating it.
    if not user_store:
        messages.info(request, 'Please create a storefront before creating products.')
        return redirect(reverse('storefront:store_create') + '?from=listing')

    # Ensure the route matches the user's storefront; if not, redirect
    if store_slug != user_store.slug:
        return redirect('storefront:product_create', store_slug=user_store.slug)

    store = user_store
    user_stores = Store.objects.filter(owner=request.user)

    if request.method == 'POST':
        form = ListingForm(request.POST, request.FILES)
        if form.is_valid():
            listing = form.save(commit=False)
            listing.seller = request.user
            listing.store = store
            
            # Set is_featured automatically based on store's subscription
            from storefront.models import Subscription
            from django.utils import timezone
            from django.db.models import Q
            active_premium_subscription = Subscription.objects.filter(
                store=store,
                plan__in=['premium', 'enterprise']
            ).filter(
                Q(status='active') | Q(status='trialing', trial_ends_at__gt=timezone.now())
            ).exists()
            listing.is_featured = active_premium_subscription
            
            listing.save()
            # Handle multiple uploaded images robustly
            images = request.FILES.getlist('images')
            failed_images = []
            max_size = getattr(settings, 'MAX_IMAGE_UPLOAD_SIZE', 5 * 1024 * 1024)
            for img in images:
                try:
                    # Basic validation: content type and size
                    content_type = getattr(img, 'content_type', '')
                    size = getattr(img, 'size', None)
                    if content_type and not content_type.startswith('image/'):
                        raise ValueError('Invalid file type')
                    if size is not None and size > max_size:
                        raise ValueError('File too large')

                    ListingImage.objects.create(listing=listing, image=img)
                except Exception as e:
                    # Log and track failed image; continue processing
                    failed_images.append({'name': getattr(img, 'name', 'unknown'), 'error': str(e)})

            if failed_images:
                # Keep the listing but inform the user which images failed to upload.
                err_msgs = '; '.join([f"{f['name']}: {f['error']}" for f in failed_images])
                messages.warning(request, f"Listing created but some images failed to upload: {err_msgs}")
            else:
                messages.success(request, 'Listing created successfully')
            return redirect('storefront:store_detail', slug=store.slug)
    else:
        form = ListingForm()

    # Render using the same template as the generic ListingCreateView so users see the identical "Sell Item" form
    categories = Category.objects.filter(is_active=True)
    return render(request, 'listings/listing_form.html', {'form': form, 'store': store, 'categories': categories, 'stores': user_stores})


@login_required
@store_owner_required
def product_edit(request, pk):
    product = get_object_or_404(Listing, pk=pk)
    # Allow the listing seller, the store owner, or staff to edit
    user = request.user
    store_owner_id = product.store.owner_id if product.store else None
    if not (product.seller == user or store_owner_id == getattr(user, 'id', None) or getattr(user, 'is_staff', False)):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("You don't have permission to edit this listing.")
    if request.method == 'POST':
        # Handle removal of the main listing image via a small separate POST
        if request.POST.get('remove_main_image'):
            # Ensure owner
            if product.seller == request.user:
                if product.image:
                    try:
                        product.image.delete(save=False)
                    except Exception:
                        pass
                    product.image = None
                    product.save()
                    messages.success(request, 'Main image removed successfully.')
                else:
                    messages.info(request, 'No main image to remove.')
            return redirect('storefront:product_edit', pk=product.pk)

        form = ListingForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            listing = form.save(commit=False)
            
            # Ensure the listing has a store associated
            if not listing.store:
                # Try to get the seller's store
                store = Store.objects.filter(owner=listing.seller).first()
                if store:
                    listing.store = store
                else:
                    # Create a new store for the seller if they don't have one
                    store_name = f"{listing.seller.username}'s Store"
                    store_slug = listing.seller.username.lower()
                    store = Store.objects.create(
                        owner=listing.seller,
                        name=store_name,
                        slug=store_slug
                    )
                    listing.store = store
                    messages.info(request, "A new store was created for your listings.")
            
            # Set is_featured automatically based on store's subscription
            from storefront.models import Subscription
            from django.utils import timezone
            from django.db.models import Q
            if listing.store:
                active_premium_subscription = Subscription.objects.filter(
                    store=listing.store,
                    plan__in=['premium', 'enterprise']
                ).filter(
                    Q(status='active') | Q(status='trialing', trial_ends_at__gt=timezone.now())
                ).exists()
                listing.is_featured = active_premium_subscription
            
            listing.save()
            
            # Handle additional uploaded images
            images = request.FILES.getlist('images')
            failed_images = []
            max_size = getattr(settings, 'MAX_IMAGE_UPLOAD_SIZE', 5 * 1024 * 1024)
            for img in images:
                try:
                    content_type = getattr(img, 'content_type', '')
                    size = getattr(img, 'size', None)
                    if content_type and not content_type.startswith('image/'):
                        raise ValueError('Invalid file type')
                    if size is not None and size > max_size:
                        raise ValueError('File too large')
                    ListingImage.objects.create(listing=listing, image=img)
                except Exception as e:
                    failed_images.append({'name': getattr(img, 'name', 'unknown'), 'error': str(e)})

            if failed_images:
                err_msgs = '; '.join([f"{f['name']}: {f['error']}" for f in failed_images])
                messages.warning(request, f"Some images failed to upload: {err_msgs}")
            else:
                messages.success(request, "Listing updated successfully!")

            # Redirect to store detail if store exists, otherwise to dashboard
            if listing.store:
                return redirect('storefront:store_detail', slug=listing.store.slug)
            return redirect('storefront:seller_dashboard')
        else:
            # Add form-level error if there are any
            if form.non_field_errors():
                messages.error(request, form.non_field_errors()[0])
            # Add field-specific errors
            for field, errors in form.errors.items():
                messages.error(request, f"{field}: {errors[0]}")
    else:
        form = ListingForm(instance=product)
    
    # Add categories for form and editing flag
    context = {
        'form': form, 
        'product': product,
        'categories': Category.objects.filter(is_active=True),
        'editing': True,
    }
    return render(request, 'listings/listing_form.html', context)


@login_required
@store_owner_required
def product_delete(request, pk):
    product = get_object_or_404(Listing, pk=pk)
    # Allow seller, store owner, or staff to delete
    user = request.user
    store_slug = request.POST.get('store_slug') or (product.store.slug if product.store else (product.seller.stores.first().slug if product.seller.stores.exists() else ''))
    if not (product.seller == user or (product.store and product.store.owner == user) or getattr(user, 'is_staff', False)):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("You don't have permission to delete this listing.")
    if request.method == 'POST':
        product.delete()
        if store_slug:
            return redirect('storefront:store_detail', slug=store_slug)
        return redirect('storefront:seller_dashboard')
    return render(request, 'storefront/product_confirm_delete.html', {'product': product})


@login_required
@store_owner_required
def image_delete(request, pk):
    # Delete a ListingImage
    img = get_object_or_404(ListingImage, pk=pk)
    # Ensure the requesting user owns the listing or is store owner/staff
    user = request.user
    listing = img.listing
    if not (listing.seller == user or (listing.store and listing.store.owner == user) or getattr(user, 'is_staff', False)):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("You don't have permission to delete this image.")
    if request.method == 'POST':
        # Allow a "next" parameter to return to a specific URL (e.g., edit page)
        next_url = request.POST.get('next') or request.GET.get('next')
        img.delete()
        if next_url:
            # Only allow relative URLs for safety
            if next_url.startswith('/'):
                return redirect(next_url)
        # Fallback to store detail if available
        store_slug = img.listing.store.slug if img.listing.store else (img.listing.seller.stores.first().slug if img.listing.seller.stores.exists() else '')
        if store_slug:
            return redirect('storefront:store_detail', slug=store_slug)
        return redirect('storefront:seller_dashboard')
    return render(request, 'storefront/image_confirm_delete.html', {'image': img})

@login_required
@store_owner_required
def delete_logo(request, slug):
    """Delete a store's logo."""
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    if request.method == 'POST':
        # Delete the actual file
        if store.logo:
            store.logo.delete(save=False)
        store.logo = None
        store.save()
        messages.success(request, 'Store logo removed successfully.')
        return redirect('storefront:store_edit', slug=store.slug)
    return redirect('storefront:store_edit', slug=store.slug)

@login_required
@store_owner_required
def delete_cover(request, slug):
    """Delete a store's cover image."""
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    if request.method == 'POST':
        # Delete the actual file
        if store.cover_image:
            store.cover_image.delete(save=False)
        store.cover_image = None
        store.save()
        messages.success(request, 'Store cover image removed successfully.')
        return redirect('storefront:store_edit', slug=store.slug)
    return redirect('storefront:store_edit', slug=store.slug)




@login_required
@store_owner_required
def cancel_subscription(request, slug):
    """Cancel subscription"""
    if request.method != 'POST':
        return redirect('storefront:subscription_manage', slug=slug)
        
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    subscription = store.subscriptions.order_by('-started_at').first()
    
    if not subscription or not subscription.is_active():
        messages.error(request, 'No active subscription found.')
        return redirect('storefront:subscription_manage', slug=slug)
    
    try:
        subscription.cancel()
        messages.success(request, 'Subscription cancelled successfully. Premium features will be available until the end of your current billing period.')
    except Exception as e:
        messages.error(request, f'Failed to cancel subscription: {str(e)}')
    
    return redirect('storefront:subscription_manage', slug=slug)

@login_required
def payment_monitor(request):
    """
    Comprehensive payment dashboard for sellers showing all payment types:
    - Subscription payments
    - Order payments (customer purchases)
    - Escrow releases to sellers
    """
    # Get user's stores
    user_stores = Store.objects.filter(owner=request.user)

    # Get time period from query params
    period = request.GET.get('period', '30d')
    time_period = None
    if period != 'all':
        days = int(period.rstrip('d'))
        time_period = timezone.now() - timedelta(days=days)

    # ===== SUBSCRIPTION PAYMENTS =====
    subscription_payments = MpesaPayment.objects.filter(
        subscription__store__in=user_stores
    ).select_related('subscription', 'subscription__store')

    if time_period:
        subscription_payments = subscription_payments.filter(created_at__gte=time_period)

    subscription_payments = subscription_payments.order_by('-created_at')[:50]

    # ===== ORDER PAYMENTS (Customer purchases) =====
    from listings.models import Payment as OrderPayment
    order_payments = OrderPayment.objects.filter(
        order__order_items__listing__store__in=user_stores
    ).select_related(
        'order',
        'order__user'
    ).prefetch_related('order__order_items__listing').distinct()

    if time_period:
        order_payments = order_payments.filter(created_at__gte=time_period)

    order_payments = order_payments.order_by('-created_at')[:50]

    # ===== ESCROW RELEASES =====
    escrow_releases = OrderPayment.objects.filter(
        order__order_items__listing__store__in=user_stores,
        status='completed',
        seller_payout_reference__isnull=False
    ).exclude(seller_payout_reference='').select_related(
        'order',
        'order__user'
    ).prefetch_related('order__order_items__listing').distinct()

    if time_period:
        escrow_releases = escrow_releases.filter(actual_release_date__gte=time_period)

    escrow_releases = escrow_releases.order_by('-actual_release_date')[:50]

    # ===== PAYMENT STATISTICS =====
    # Total earnings from completed orders
    total_earnings = OrderPayment.objects.filter(
        order__order_items__listing__store__in=user_stores,
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or 0

    # Pending escrow funds
    pending_escrow = OrderPayment.objects.filter(
        order__order_items__listing__store__in=user_stores,
        status='completed',
        is_held_in_escrow=True,
        actual_release_date__isnull=True
    ).aggregate(total=Sum('amount'))['total'] or 0

    # Released escrow funds
    released_escrow = OrderPayment.objects.filter(
        order__order_items__listing__store__in=user_stores,
        status='completed',
        is_held_in_escrow=True,
        actual_release_date__isnull=False
    ).aggregate(total=Sum('amount'))['total'] or 0

    # Subscription revenue
    subscription_revenue = MpesaPayment.objects.filter(
        subscription__store__in=user_stores,
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or 0

    # Recent failed payments
    failed_payments = []
    failed_subs = MpesaPayment.objects.filter(
        subscription__store__in=user_stores,
        status='failed'
    ).order_by('-created_at')[:10]
    failed_orders = OrderPayment.objects.filter(
        order__order_items__listing__store__in=user_stores,
        status='failed'
    ).order_by('-created_at')[:10]

    failed_payments = list(failed_subs) + list(failed_orders)
    failed_payments.sort(key=lambda x: x.created_at, reverse=True)
    failed_payments = failed_payments[:20]

    context = {
        'period': period,
        'user_stores': user_stores,

        # Payment collections
        'subscription_payments': subscription_payments,
        'order_payments': order_payments,
        'escrow_releases': escrow_releases,
        'failed_payments': failed_payments,

        # Statistics
        'total_earnings': total_earnings,
        'pending_escrow': pending_escrow,
        'released_escrow': released_escrow,
        'subscription_revenue': subscription_revenue,
        'available_balance': released_escrow,  # Funds available for withdrawal

        # Counts
        'subscription_count': subscription_payments.count(),
        'order_count': order_payments.count(),
        'escrow_count': escrow_releases.count(),
        'failed_count': len(failed_payments),
    }

    return render(request, 'storefront/payment_monitor_enhanced.html', context)


@login_required
@store_owner_required
@login_required
@analytics_access_required('basic')
def seller_analytics(request):
    """
    Seller analytics dashboard showing aggregated metrics across all stores.
    """
    # Get all stores owned by the user
    stores = Store.objects.filter(owner=request.user)
    
    # Get time period from query params
    period = request.GET.get('period', '24h')
    time_period = None
    previous_period = None
    
    if period == '24h':
        time_period = timezone.now() - timedelta(hours=24)
        previous_period = timezone.now() - timedelta(hours=48)
    elif period == '7d':
        time_period = timezone.now() - timedelta(days=7)
        previous_period = timezone.now() - timedelta(days=14)
    elif period == '30d':
        time_period = timezone.now() - timedelta(days=30)
        previous_period = timezone.now() - timedelta(days=60)
    
    # Base queryset for orders across all stores - FIXED: Include both paid and delivered
    orders_qs = OrderItem.objects.filter(
        listing__store__in=stores,
        order__status__in=['paid', 'delivered']  # Include both statuses
    )
    
    # Current period metrics
    if time_period:
        current_orders = orders_qs.filter(added_at__gte=time_period)
        current_revenue = current_orders.aggregate(
            total=Sum(F('price') * F('quantity'), default=0)
        )['total']
        current_order_count = current_orders.count()
        
        # Previous period for trend calculation
        previous_orders = orders_qs.filter(
            added_at__gte=previous_period,
            added_at__lt=time_period
        )
        previous_revenue = previous_orders.aggregate(
            total=Sum(F('price') * F('quantity'), default=0)
        )['total']
        previous_order_count = previous_orders.count()
        
        # Calculate trends
        revenue_trend = (
            ((current_revenue - previous_revenue) / previous_revenue * 100)
            if previous_revenue else 0
        )
        orders_trend = (
            ((current_order_count - previous_order_count) / previous_order_count * 100)
            if previous_order_count else 0
        )
    else:
        # All time metrics
        current_revenue = orders_qs.aggregate(
            total=Sum(F('price') * F('quantity'), default=0)
        )['total']
        current_order_count = orders_qs.count()
        revenue_trend = 0
        orders_trend = 0
    
    # Store metrics
    active_stores = stores.count()
    premium_stores = stores.filter(is_premium=True).count()
    active_listings = Listing.objects.filter(
        store__in=stores,
        is_active=True
    ).count()
    
    # Revenue & Orders trend data
    trend_days = 30 if period == '30d' else (7 if period == '7d' else 1)
    revenue_data = []
    orders_data = []
    labels = []
    
    for i in range(trend_days):
        day = timezone.now() - timedelta(days=i)
        day_orders = orders_qs.filter(added_at__date=day.date())
        
        revenue = day_orders.aggregate(
            total=Sum(F('price') * F('quantity'), default=0)
        )['total']
        orders = day_orders.count()
        
        revenue_data.insert(0, revenue)
        orders_data.insert(0, orders)
        labels.insert(0, day.strftime('%b %d'))
    
    revenue_orders_trend_data = {
        'labels': labels,
        'datasets': [
            {
                'label': 'Revenue',
                'data': revenue_data,
                'borderColor': '#4CAF50',
                'yAxisID': 'y',
            },
            {
                'label': 'Orders',
                'data': orders_data,
                'borderColor': '#2196F3',
                'yAxisID': 'y1',
            }
        ]
    }
    
    # Store performance distribution
    store_performance = []
    for store in stores:
        store_revenue = orders_qs.filter(
            listing__store=store
        ).aggregate(total=Sum(F('price') * F('quantity'), default=0))['total']
        store_performance.append({
            'name': store.name,
            'revenue': store_revenue
        })
    

    store_performance.sort(key=lambda x: x['revenue'], reverse=True)
    
    # Create store_performance_data for chart - ADDED THIS SECTION
    store_performance_data = {
        'labels': [s['name'] for s in store_performance],
        'datasets': [{
            'data': [s['revenue'] for s in store_performance],
            'backgroundColor': [
                '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF'
            ]
        }]
    }

    # Top performing stores
    top_stores = []
    for store in stores:
        store_orders = orders_qs.filter(listing__store=store)
        store_revenue = store_orders.aggregate(
            total=Sum(F('price') * F('quantity'), default=0)
        )['total']
        
        # Calculate average rating
        store_ratings = Review.objects.filter(
            seller=store.owner
        ).aggregate(avg_rating=Avg('rating', default=0))
        
        top_stores.append({
            'name': store.name,
            'slug': store.slug,
            'revenue': store_revenue,
            'orders': store_orders.count(),
            'rating': store_ratings['avg_rating']
        })
    
    top_stores.sort(key=lambda x: x['revenue'], reverse=True)
    
    # Top categories
    top_categories = []
    categories = Category.objects.filter(
        listing__store__in=stores
    ).distinct()
    
    for category in categories:
        category_orders = orders_qs.filter(
            listing__category=category
        )
        revenue = category_orders.aggregate(
            total=Sum(F('price') * F('quantity'), default=0)
        )['total']
        
        top_categories.append({
            'name': category.name,
            'revenue': revenue,
            'orders': category_orders.count(),
            'listings': Listing.objects.filter(
                store__in=stores,
                category=category,
                is_active=True
            ).count()
        })
    
    top_categories.sort(key=lambda x: x['revenue'], reverse=True)
    top_categories = top_categories[:5]
    
    # Recent activity across all stores
    recent_activity = []
    
    # Recent orders
    recent_orders = orders_qs.order_by('-added_at')[:5]
    for order in recent_orders:
        recent_activity.append({
            'timestamp': order.added_at,
            'store': order.listing.store.name,
            'type': 'Order',
            'description': f'New order for {order.listing.title} (Qty: {order.quantity}) - Status: {order.order.status}'
        })
    
    # Recent reviews
    recent_reviews = Review.objects.filter(
        seller__in=[store.owner for store in stores]
    ).order_by('-created_at')[:5]
    
    for review in recent_reviews:
        if review.seller.stores.exists():
            recent_activity.append({
                'timestamp': review.created_at,
                'store': review.seller.stores.first().name if review.seller.stores.exists() else 'Unknown Store',
                'type': 'Review',
                'description': f'{review.rating}★ reviewed by {review.user.username} - "{review.comment[:50]}{"..." if len(review.comment) > 50 else ""}"'
            })
    
    # Recent listings
    recent_listings = Listing.objects.filter(
        store__in=stores
    ).order_by('-date_created')[:5]
    
    for listing in recent_listings:
        recent_activity.append({
            'timestamp': listing.date_created,
            'store': listing.store.name,
            'type': 'Listing',
            'description': f'New listing: {listing.title}'
        })
    
    recent_activity.sort(key=lambda x: x['timestamp'], reverse=True)
    recent_activity = recent_activity[:10]
    
    # Customer location data
    customer_locations = orders_qs.values(
        'order__city'
    ).annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    customer_map_data = {
        'labels': [loc['order__city'] for loc in customer_locations],
        'datasets': [{
            'data': [loc['count'] for loc in customer_locations],
            'backgroundColor': [
                '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF'
            ]
        }]
    }
    
    context = {
        'period': period,
        'total_revenue': current_revenue,
        'total_orders': current_order_count,
        'revenue_trend': round(revenue_trend, 1),
        'orders_trend': round(orders_trend, 1),
        'active_stores': active_stores,
        'premium_stores': premium_stores,
        'active_listings': active_listings,
        'revenue_orders_trend_data': dumps_with_decimals(revenue_orders_trend_data),
        'store_performance_data': dumps_with_decimals(store_performance_data),
        'top_stores': top_stores[:5],
        'top_categories': top_categories,
        'recent_activity': recent_activity,
        'customer_map_data': dumps_with_decimals(customer_map_data)
    }
    
    return render(request, 'storefront/seller_analytics.html', context)


@login_required
@store_owner_required
@analytics_access_required('basic')
def store_analytics(request, slug):
    """
    Store analytics view with comprehensive metrics and visualizations.
    """
    # Fetch the store by slug first, then ensure the requesting user is the owner.
    store = get_object_or_404(Store, slug=slug)
    if store.owner != request.user and not request.user.is_staff:
        message = "You do not have permission to view analytics for a store you do not own."
        context = {'message': message, 'store': store}
        return render(request, 'storefront/forbidden.html', context, status=403)
    
    # Get time period from query params
    period = request.GET.get('period', '24h')
    time_period = None
    
    if period == '24h':
        time_period = timezone.now() - timedelta(hours=24)
    elif period == '7d':
        time_period = timezone.now() - timedelta(days=7)
    elif period == '30d':
        time_period = timezone.now() - timedelta(days=30)
    
    # Base queryset for the store's listings
    listings_qs = Listing.objects.filter(store=store)
    # FIXED: Include both paid and delivered orders
    orders_qs = OrderItem.objects.filter(
        listing__store=store,
        order__status__in=['paid', 'delivered']  # Include both statuses
    )
    
    if time_period:
        orders_qs = orders_qs.filter(added_at__gte=time_period)
    
    # Basic metrics
    revenue = orders_qs.aggregate(
        total=Sum(F('price') * F('quantity'), default=0)
    )['total']
    
    orders_count = orders_qs.count()
    active_listings = listings_qs.filter(is_active=True).count()
    avg_order_value = orders_qs.aggregate(
        avg=Avg(F('price') * F('quantity'), default=0)
    )['avg']
    
    # Revenue trend (daily data points)
    trend_days = 30 if period == '30d' else (7 if period == '7d' else 1)
    revenue_trend = []
    labels = []
    
    for i in range(trend_days):
        day = timezone.now() - timedelta(days=i)
        day_revenue = orders_qs.filter(
            added_at__date=day.date()
        ).aggregate(total=Sum(F('price') * F('quantity'), default=0))['total']
        
        revenue_trend.insert(0, day_revenue)
        labels.insert(0, day.strftime('%b %d'))
    
    revenue_trend_data = {
        'labels': labels,
        'datasets': [{
            'label': 'Daily Revenue',
            'data': revenue_trend,
            'fill': False,
            'borderColor': '#4CAF50',
            'tension': 0.1
        }]
    }
    
    # Top categories by sales
    category_sales = orders_qs.values(
        'listing__category__name'
    ).annotate(
        total_sales=Count('id'),
        revenue=Sum(F('price') * F('quantity'))
    ).order_by('-total_sales')[:5]
    
    category_data = {
        'labels': [item['listing__category__name'] for item in category_sales],
        'datasets': [{
            'data': [item['total_sales'] for item in category_sales],
            'backgroundColor': [
                '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF'
            ]
        }]
    }
    
    # Top performing products
    top_products = orders_qs.values(
        'listing__title'
    ).annotate(
        sales_count=Sum('quantity'),
        revenue=Sum(F('price') * F('quantity'))
    ).order_by('-revenue')[:5]
    
    # Recent activity (orders, reviews, listings)
    recent_activity = []
    
    # Add recent orders
    recent_orders = orders_qs.order_by('-added_at')[:5]
    for order in recent_orders:
        recent_activity.append({
            'timestamp': order.added_at,
            'type': 'Order',
            'description': f'New order for {order.listing.title} (Qty: {order.quantity}) - Status: {order.order.status}'
        })
    
    # Add recent reviews
    recent_reviews = Review.objects.filter(
        seller=store.owner
    ).order_by('-created_at')[:5]
    
    for review in recent_reviews:
        recent_activity.append({
            'timestamp': review.created_at,
            'type': 'Review',
            'description': f'{review.rating}★ review by {review.user.username}'
        })
    
    # Add recent listings
    recent_listings = listings_qs.order_by('-date_created')[:5]
    for listing in recent_listings:
        recent_activity.append({
            'timestamp': listing.date_created,
            'type': 'Listing',
            'description': f'New listing: {listing.title}'
        })
    
    # Sort combined activity by timestamp
    recent_activity.sort(key=lambda x: x['timestamp'], reverse=True)
    recent_activity = recent_activity[:10]  # Keep top 10
    
    context = {
        'store': store,
        'period': period,
        'revenue': revenue,
        'orders_count': orders_count,
        'active_listings': active_listings,
        'avg_order_value': avg_order_value,
        'revenue_trend_data': dumps_with_decimals(revenue_trend_data),
        'category_data': dumps_with_decimals(category_data),
        'top_products': top_products,
        'recent_activity': recent_activity,
    }
    
    return render(request, 'storefront/store_analytics.html', context)


# storefront/views.py - Add these views

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q, Count, Avg
from django.http import JsonResponse
from .decorators import store_owner_required
from .models import Store, StoreReview, Subscription, MpesaPayment, ReviewHelpful
from .forms import StoreReviewForm, UpgradeForm, CancelSubscriptionForm, SubscriptionPlanForm
from .mpesa import MpesaGateway
from listings.models import Listing
from listings.models import Review  


# Store Review Views

@login_required
def store_review_create(request, slug):
    """
    Create or update a store review
    """
    store = get_object_or_404(Store, slug=slug)
    
    # Check if user owns the store
    if store.owner == request.user:
        messages.error(request, "You cannot review your own store.")
        return redirect('storefront:store_detail', slug=slug)
    
    # Check if user already reviewed
    existing_review = StoreReview.objects.filter(store=store, reviewer=request.user).first()

    from listings.models import Review
    has_product_review = Review.objects.filter(
        listing__store=store,
        user=request.user
    ).exists()
    
    if has_product_review and not existing_review:
        messages.info(request, "You've already reviewed products from this store. You can still leave a direct store review.")
    
    if request.method == 'POST':
        form = StoreReviewForm(request.POST, instance=existing_review)
        if form.is_valid():
            review = form.save(commit=False)
            review.store = store
            review.reviewer = request.user
            
            if existing_review:
                messages.success(request, "Your review has been updated.")
            else:
                messages.success(request, "Thank you for your review!")
            
            review.save()
            
            # Redirect back to the product page if coming from there
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('storefront:store_reviews', slug=slug)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = StoreReviewForm(instance=existing_review)
    
    context = {
        'store': store,
        'form': form,
        'existing_review': existing_review,
        'editing': bool(existing_review),
    }
    
    # If coming from product page, show product-specific template
    if request.GET.get('from') == 'product':
        return render(request, 'storefront/store_review_product.html', context)
    return render(request, 'storefront/store_review_form.html', context)



def store_reviews(request, slug):
    """
    Display all reviews for a store (both product reviews and direct store reviews)
    """
    store = get_object_or_404(Store, slug=slug)
    
    # Get page number from query params
    page = request.GET.get('page', 1)
    
    # Get paginated reviews
    reviews_page = store.get_all_reviews_paginated(page=page, per_page=10)
    
    # Calculate rating distribution for all reviews
    from collections import defaultdict
    rating_distribution = defaultdict(int)
    all_reviews = store.get_all_reviews()
    
    for review in all_reviews:
        rating_distribution[review['rating']] += 1
    
    # Get average rating
    avg_rating = store.get_rating()
    
    # Check if user has reviewed
    user_has_reviewed = False
    user_review = None
    
    if request.user.is_authenticated:
        user_has_reviewed = store.has_user_reviewed(request.user)
        if user_has_reviewed:
            # Try to get user's direct store review
            user_review = store.reviews.filter(reviewer=request.user).first()
    
    context = {
        'store': store,
        'reviews': reviews_page,
        'avg_rating': avg_rating,
        'rating_distribution': dict(sorted(rating_distribution.items())),
        'user_has_reviewed': user_has_reviewed,
        'user_review': user_review,
        'total_reviews': len(all_reviews),
    }
    
    return render(request, 'storefront/store_reviews.html', context)

@login_required
def store_review_update(request, slug, review_id):
    """
    Update an existing review
    """
    review = get_object_or_404(StoreReview, id=review_id, reviewer=request.user)
    store = review.store
    
    if request.method == 'POST':
        form = StoreReviewForm(request.POST, instance=review)
        if form.is_valid():
            form.save()
            messages.success(request, "Your review has been updated.")
            return redirect('storefront:store_reviews', slug=slug)
    else:
        form = StoreReviewForm(instance=review)
    
    context = {
        'store': store,
        'form': form,
        'review': review,
        'editing': True,
    }
    
    return render(request, 'storefront/store_review_form.html', context)


@login_required
def store_review_delete(request, slug, review_id):
    """
    Delete a review
    """
    review = get_object_or_404(StoreReview, id=review_id, reviewer=request.user)
    
    if request.method == 'POST':
        review.delete()
        messages.success(request, "Your review has been deleted.")
        return redirect('storefront:store_reviews', slug=slug)
    
    context = {
        'store': review.store,
        'review': review,
    }
    
    return render(request, 'storefront/store_review_confirm_delete.html', context)


@login_required
def mark_review_helpful(request, slug, review_id):
    """
    Mark a review as helpful (AJAX)
    """
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        review = get_object_or_404(StoreReview, id=review_id)
        success = review.mark_helpful(request.user)
        
        return JsonResponse({
            'success': success,
            'helpful_count': review.helpful_count,
        })
    
    return JsonResponse({'success': False}, status=400)



@login_required
@store_owner_required
def subscription_plan_select(request, slug):
    """
    Select subscription plan before payment - FIXED VERSION
    """
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    
    # Check if already has active subscription (treat 'trialing' as active only if trial hasn't ended)
    active_subscription = Subscription.objects.filter(store=store).filter(
        Q(status='active') | Q(status='trialing', trial_ends_at__gt=timezone.now())
    ).first()

    if active_subscription and active_subscription.is_active():
        messages.info(request, "You already have an active subscription.")
        return redirect('storefront:subscription_manage', slug=slug)
    
    if request.method == 'POST':
        # Handle direct form submission
        plan_form = SubscriptionPlanForm(request.POST)
        upgrade_form = UpgradeForm(request.POST)
        
        if plan_form.is_valid() and upgrade_form.is_valid():
            # Store plan selection in session
            request.session['selected_plan'] = plan_form.cleaned_data['plan']
            request.session.modified = True  # Ensure session is saved
            
            # Get phone number from form
            phone_number = upgrade_form.cleaned_data['phone_number']
            
            # Redirect to payment page with parameters
            return redirect('storefront:store_upgrade', slug=slug)
        else:
            # Form validation failed
            messages.error(request, "Please correct the errors below.")
    else:
        plan_form = SubscriptionPlanForm()
        upgrade_form = UpgradeForm()
    
    # Plan details - MUST MATCH pricing in store_upgrade view
    plan_details = {
        'basic': {
            'price': 999,
            'features': [
                'Priority Listing',
                'Basic Analytics',
                'Store Customization',
                'Verified Badge',
                'Up to 50 products'
            ]
        },
        'premium': {
            'price': 1999,
            'features': [
                'Everything in Basic',
                'Advanced Analytics',
                'Bulk Product Upload',
                'Marketing Tools',
                'Up to 200 products',
                'Dedicated Support'
            ]
        },
        'enterprise': {
            'price': 4999,
            'features': [
                'Everything in Premium',
                'Custom Integrations',
                'API Access',
                'Unlimited Products',
                'Priority Support',
                'Custom Domain'
            ]
        }
    }
    
    context = {
        'store': store,
        'plan_form': plan_form,
        'upgrade_form': upgrade_form,
        'plan_details': plan_details,
    }
    
    return render(request, 'storefront/subscription_plan_select.html', context)



@login_required
def admin_subscription_list(request):
    """
    Admin view to list all subscriptions
    """
    if not request.user.is_staff:
        return redirect('storefront:seller_dashboard')
    
    subscriptions = Subscription.objects.all().order_by('-created_at')
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        subscriptions = subscriptions.filter(status=status_filter)
    
    # Search
    search_query = request.GET.get('q')
    if search_query:
        subscriptions = subscriptions.filter(
            Q(store__name__icontains=search_query) |
            Q(store__owner__username__icontains=search_query) |
            Q(mpesa_phone__icontains=search_query)
        )
    
    context = {
        'subscriptions': subscriptions,
        'status_filter': status_filter,
        'search_query': search_query,
    }
    
    return render(request, 'storefront/admin_subscription_list.html', context)


@login_required
def admin_subscription_detail(request, subscription_id):
    """
    Admin view for subscription details
    """
    if not request.user.is_staff:
        return redirect('storefront:seller_dashboard')
    
    subscription = get_object_or_404(Subscription, id=subscription_id)
    payments = subscription.payments.all().order_by('-created_at')
    
    context = {
        'subscription': subscription,
        'payments': payments,
    }
    
    return render(request, 'storefront/admin_subscription_detail.html', context)
