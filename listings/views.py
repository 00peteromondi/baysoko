# listings/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.db.models import Q, Count, Avg, F
from django.db import utils as db_utils
from .models import Listing, Category, Favorite, Activity, RecentlyViewed, Review, Order, OrderItem, Cart, CartItem, Payment, Escrow, ListingImage
from .forms import ListingForm
from storefront.models import Store
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db.models import Q
from blog.models import BlogPost


from notifications.utils import (
    notify_new_order, notify_order_shipped, notify_order_delivered,
    notify_payment_received, notify_listing_favorited, notify_new_review,
    notify_delivery_assigned, notify_delivery_confirmed
)


User = get_user_model()

# In your views.py - Update the ListingListView
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta

# In your listings/views.py - Updated ListingListView class
class ListingListView(ListView):
    model = Listing
    template_name = 'listings/home.html'
    context_object_name = 'listings'
    paginate_by = 12

    def get_queryset(self):
        queryset = Listing.objects.filter(is_active=True).order_by('-date_created')
        
        # Search functionality
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) | 
                Q(description__icontains=query) |
                Q(brand__icontains=query) |
                Q(model__icontains=query)
            )
        
        # Filter by location
        location = self.request.GET.get('location')
        if location:
            queryset = queryset.filter(location=location)
        
        # Filter by category
        category_id = self.request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category__id=category_id)
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Essential counts for stats - UPDATED
        context['total_users'] = User.objects.count()
        context['total_listings'] = Listing.objects.filter(is_active=True).count()
        context['total_orders'] = Order.objects.count()  # All orders, not just delivered
        context['total_stores'] = Store.objects.filter(is_active=True).count()
        
        # Categories data - UPDATED
        context['categories'] = Category.objects.filter(is_active=True)[:8]
        
        # Featured categories (if your Category model has is_featured field)
        # If not, you can use categories with most listings as featured
        try:
            context['featured_categories'] = Category.objects.filter(
                is_active=True
            ).annotate(
                listing_count=Count('listing', filter=Q(listing__is_active=True))
            ).order_by('-listing_count')[:3]
        except:
            # Fallback if is_featured field doesn't exist
            context['featured_categories'] = Category.objects.filter(is_active=True)[:3]
        
        # Categories with listings count
        context['categories_with_listings'] = Category.objects.annotate(
            listing_count=Count('listing', filter=Q(listing__is_active=True))
        ).filter(listing_count__gt=0)[:6]
        
        # Listings data - ENHANCED with all the home function data
        # Featured listings (already existed)
        context['featured_listings'] = Listing.objects.filter(
            is_featured=True, 
            is_active=True,
            is_sold=False
        ).select_related('category', 'seller').order_by('-date_created')[:8]
        
        # Trending listings (based on favorite count as proxy for popularity)
        context['trending_listings'] = Listing.objects.filter(
            is_active=True,
            is_sold=False
        ).annotate(
            favorite_count=Count('favorited_by')
        ).order_by('-favorite_count', '-date_created')[:8]
        
        # New arrivals (similar to existing but properly limited)
        context['new_arrivals'] = Listing.objects.filter(
            is_active=True,
            is_sold=False
        ).order_by('-date_created')[:8]
        
        # Top rated listings
        context['top_rated_listings'] = Listing.objects.filter(
            is_active=True,
            is_sold=False
        ).annotate(
            avg_rating=Avg('reviews__rating')
        ).filter(avg_rating__gte=4.0).order_by('-avg_rating')[:8]
        
        # Flash sale listings (listings with price discounts)
        context['flash_sale_listings'] = Listing.objects.filter(
            is_active=True,
            is_sold=False
        ).exclude(original_price__isnull=True).filter(
            original_price__gt=F('price')
        ).order_by('-date_created')[:4]
        
        user_favorites = set()
        try:
            if self.request.user.is_authenticated:
                # Prefer the reverse related_name 'favorites' if present on User
                if hasattr(self.request.user, 'favorites'):
                    qs = self.request.user.favorites.values_list('pk', flat=True)
                else:
                    # Fallback to explicit Listing lookup (works if Listing has favorited_by M2M)
                    qs = Listing.objects.filter(favorited_by=self.request.user).values_list('pk', flat=True)
                # Force evaluation inside try so DB errors are caught here
                user_favorites = set(int(pk) for pk in qs)
        except (db_utils.OperationalError, db_utils.ProgrammingError, Exception) as exc:
            # Don't raise — log and continue with empty favorites.
            logger.warning("Could not load user favorites (possibly missing migrations / table): %s", exc)
            user_favorites = set()

        context['user_favorites'] = user_favorites
        # Existing functionality that should be preserved
        context['locations'] = Listing.HOMABAY_LOCATIONS
        
        # Popular categories with counts
        context['popular_categories'] = Category.objects.filter(
            is_active=True
        ).annotate(
            listing_count=Count('listing', filter=Q(listing__is_active=True))
        ).filter(listing_count__gt=0).order_by('-listing_count')[:8]
        
        # Recently viewed listings for authenticated users
        if self.request.user.is_authenticated:
            recently_viewed = RecentlyViewed.objects.filter(
                user=self.request.user
            ).select_related('listing').order_by('-viewed_at')[:6]
            context['recently_viewed'] = [rv.listing for rv in recently_viewed]
        
        # Featured users
        context['featured_users'] = User.objects.annotate(
            listing_count=Count('listings', filter=Q(listings__is_active=True))
        ).filter(listing_count__gt=0).order_by('-listing_count')[:3]

        # Seller ratings (average and count) for each listing in the page
        seller_ratings = {}
        seller_reviews_count = {}
        for listing in context['listings']:
            seller = listing.seller
            reviews = Review.objects.filter(listing__seller=seller)
            avg_rating = reviews.aggregate(avg_rating=Avg('rating'))['avg_rating']
            seller_ratings[seller.id] = round(avg_rating, 1) if avg_rating else 0
            seller_reviews_count[seller.id] = reviews.count()
        context['seller_ratings'] = seller_ratings
        context['seller_reviews_count'] = seller_reviews_count
        
        # Blog posts
        try:
            context['blog_posts'] = BlogPost.objects.filter(status="published").order_by('-published_at')[:3]
        except:
            context['blog_posts'] = []

        return context

class ListingDetailView(DetailView):
    model = Listing
    template_name = 'listings/listing_detail.html'
    context_object_name = 'listing'
    
    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        
        # Track recently viewed for authenticated users
        if self.request.user.is_authenticated:
            RecentlyViewed.objects.update_or_create(
                user=self.request.user,
                listing=obj,
                defaults={'viewed_at': timezone.now()}
            )
        
        return obj
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        listing = self.get_object()
        user = self.request.user
        
        # Get all reviews for the listing
        reviews = listing.reviews.select_related('user').all()
        context['reviews'] = reviews
        
        # Calculate average rating
        avg_rating = listing.reviews.aggregate(
            avg_rating=Avg('rating')
        )['avg_rating']
        context['avg_rating'] = round(avg_rating, 1) if avg_rating else 0
        
        # Calculate rating distribution
        rating_counts = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
        for review in reviews:
            if 1 <= review.rating <= 5:
                rating_counts[review.rating] += 1
        
        total_reviews = reviews.count()
        rating_distribution = []
        for rating in [5, 4, 3, 2, 1]:
            count = rating_counts[rating]
            percentage = (count / total_reviews * 100) if total_reviews > 0 else 0
            rating_distribution.append({
                'rating': rating,
                'count': count,
                'percentage': percentage
            })
        
        context['rating_distribution'] = rating_distribution
        
        # Check if the current user has favorited this listing
        if user.is_authenticated:
            context['is_favorited'] = Favorite.objects.filter(
                user=user, 
                listing=listing
            ).exists()
        else:
            context['is_favorited'] = False
            
        # Get similar listings
        context['similar_listings'] = Listing.objects.filter(
            category=listing.category,
            is_active=True,
            is_sold=False
        ).exclude(id=listing.id)[:6]
        
        # Get seller's other listings
        context['seller_other_listings'] = Listing.objects.filter(
            seller=listing.seller,
            is_active=True,
            is_sold=False
        ).exclude(id=listing.id)[:4]
        
        # Get seller statistics
        seller = listing.seller
        seller_listings = Listing.objects.filter(seller=seller, is_active=True)
        seller_reviews = Review.objects.filter(listing__seller=seller)
        
        context['seller_reviews_count'] = seller_reviews.count()
        seller_avg_rating = seller_reviews.aggregate(
            avg_rating=Avg('rating')
        )['avg_rating']
        context['seller_avg_rating'] = round(seller_avg_rating, 1) if seller_avg_rating else 0
        
        # Get FAQs for this listing
        context['faqs'] = listing.faqs.filter(is_active=True).order_by('order')
        
        # Get recently viewed for sidebar
        if user.is_authenticated:
            recently_viewed = RecentlyViewed.objects.filter(
                user=user
            ).exclude(listing=listing).select_related('listing').order_by('-viewed_at')[:4]
            context['recently_viewed_sidebar'] = [rv.listing for rv in recently_viewed]
        
        # Get price history
        context['price_history'] = listing.price_history.all()[:10]
            
        return context

    
class ListingCreateView(LoginRequiredMixin, CreateView):
    model = Listing
    form_class = ListingForm

    def dispatch(self, request, *args, **kwargs):
        # If the user is not authenticated, defer to LoginRequiredMixin's handling
        # (calling super() will let the mixin redirect to login).
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)

        # Check if user has any stores before allowing listing creation
        if not Store.objects.filter(owner=request.user).exists():
            messages.info(request, "You need to create a store first before you can list items for sale.")
            return redirect(reverse('storefront:store_create') + '?from=listing')

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add categories to context for the form
        context['categories'] = Category.objects.filter(is_active=True)
        # Get user's stores for the store selector
        if self.request.user.is_authenticated:
            context['stores'] = Store.objects.filter(owner=self.request.user)
        else:
            context['stores'] = Store.objects.none()
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        from django.conf import settings
        from django.shortcuts import render, redirect

        # Enforce per-user free listing limit (global across all listing creation entrypoints)
        FREE_LISTING_LIMIT = getattr(settings, 'STORE_FREE_LISTING_LIMIT', 5)
        user_listing_count = Listing.objects.filter(seller=self.request.user).count()

        # Get or create the user's single storefront
        user_store = Store.objects.filter(owner=self.request.user).first()

        # If the form included an explicit store choice, prefer that (but ensure ownership)
        selected_store = None
        try:
            selected_store = form.cleaned_data.get('store')
        except Exception:
            selected_store = None

        if selected_store:
            # Ensure the selected store belongs to the current user
            if selected_store.owner != self.request.user:
                messages.error(self.request, "Invalid store selection.")
                return render(self.request, 'listings/listing_form.html', {'form': form, 'categories': Category.objects.filter(is_active=True), 'stores': Store.objects.filter(owner=self.request.user)})
            user_store = selected_store

        # If user reached limit and is not premium, show upgrade prompt
        is_premium = user_store.is_premium if user_store else False
        if not is_premium and user_listing_count >= FREE_LISTING_LIMIT:
            store_for_template = user_store or Store(owner=self.request.user, name=f"{self.request.user.username}'s Store", slug=self.request.user.username)
            messages.warning(self.request, f"You've reached the free listing limit ({FREE_LISTING_LIMIT}). Upgrade to premium to add more listings.")
            return render(self.request, 'storefront/confirm_upgrade.html', {
                'store': store_for_template,
                'limit_reached': True,
                'current_count': user_listing_count,
                'free_limit': FREE_LISTING_LIMIT,
            })

        # If there's still no user_store (and no explicit selection), require the user to create or select a storefront.
        # We intentionally DO NOT auto-create a store here so that the user explicitly chooses where the listing should appear.
        if not user_store:
            messages.info(self.request, "You need to create a storefront before you can list items. Please create a store first.")
            return redirect(reverse('storefront:store_create') + '?from=listing')

        # Attach store to the listing instance
        form.instance.seller = self.request.user
        form.instance.store = user_store
        response = super().form_valid(form)

        # Handle main image
        if 'image' in self.request.FILES:
            form.instance.image = self.request.FILES['image']
            form.instance.save()

        # Handle multiple image uploads for gallery
        images = self.request.FILES.getlist('images')
        for image in images:
            # Validate file type and size
            if image.content_type.startswith('image/') and image.size <= 10 * 1024 * 1024:  # 10MB limit
                ListingImage.objects.create(
                    listing=form.instance,
                    image=image
                )

        # Create activity log
        Activity.objects.create(
            user=self.request.user,
            action=f"Created listing: {form.instance.title}"
        )

        messages.success(self.request, "Listing created successfully!")
        return response

class ListingUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Listing
    form_class = ListingForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.filter(is_active=True)
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def test_func(self):
        listing = self.get_object()
        return self.request.user == listing.seller

    def form_valid(self, form):
        form.instance.seller = self.request.user
        # If the user selected a store, ensure ownership
        try:
            selected_store = form.cleaned_data.get('store')
        except Exception:
            selected_store = None

        if selected_store:
            if selected_store.owner != self.request.user:
                messages.error(self.request, "Invalid store selection.")
                return render(self.request, 'listings/listing_form.html', {'form': form, 'categories': Category.objects.filter(is_active=True), 'stores': Store.objects.filter(owner=self.request.user)})
            form.instance.store = selected_store
        
        # Handle main image update
        if 'image' in self.request.FILES:
            form.instance.image = self.request.FILES['image']
        
        response = super().form_valid(form)
        
        # Handle multiple image uploads
        images = self.request.FILES.getlist('images')
        for image in images:
            if image.content_type.startswith('image/') and image.size <= 10 * 1024 * 1024:
                ListingImage.objects.create(
                    listing=form.instance,
                    image=image
                )
        
        # Create activity log
        Activity.objects.create(
            user=self.request.user,
            action=f"Updated listing: {form.instance.title}"
        )
        
        messages.success(self.request, "Listing updated successfully!")
        return response
        
class ListingDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Listing
    success_url = '/'

    def test_func(self):
        listing = self.get_object()
        return self.request.user == listing.seller


def all_listings(request):
    # Get all active listings
    listings = Listing.objects.filter(is_active=True).order_by('-date_created')
    
    # Get filter parameters
    category_id = request.GET.get('category')
    location = request.GET.get('location')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    search_query = request.GET.get('q')
    sort_by = request.GET.get('sort_by', 'newest')
    
    # Convert categories to JSON-serializable format
    categories_data = [{"id": cat.id, "name": cat.name} for cat in Category.objects.filter(is_active=True)]
    
    # Convert locations to JSON-serializable format 
    locations_data = [{"code": code, "name": name} for code, name in Listing.HOMABAY_LOCATIONS]
    
    # Apply filters
    if category_id and category_id != 'all':
        listings = listings.filter(category__id=category_id)
    
    if location and location != 'all':
        listings = listings.filter(location=location)
    
    if min_price:
        listings = listings.filter(price__gte=min_price)
    
    if max_price:
        listings = listings.filter(price__lte=max_price)
    
    if search_query:
        listings = listings.filter(
            Q(title__icontains=search_query) | 
            Q(description__icontains=search_query) |
            Q(brand__icontains=search_query) |
            Q(model__icontains=search_query)
        )
    
    # Apply sorting
    if sort_by == 'price_low':
        listings = listings.order_by('price')
    elif sort_by == 'price_high':
        listings = listings.order_by('-price')
    elif sort_by == 'oldest':
        listings = listings.order_by('date_created')
    else:  # newest is default
        listings = listings.order_by('-date_created')
    
    # Pagination
    paginator = Paginator(listings, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # For AJAX requests, return JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        listings_data = []
        for listing in page_obj:
                listings_data.append({
                'id': listing.id,
                'title': listing.title,
                'price': str(listing.price),
                'image_url': listing.get_image_url(),
                'category': listing.category.name,
                'category_icon': listing.category.icon,
                'store': listing.store.name if listing.store else '',
                'store_url': listing.store.get_absolute_url() if listing.store else '',
                'location': listing.get_location_display(),
                'date_created': listing.date_created.strftime('%b %d, %Y'),
                'url': listing.get_absolute_url(),
                'stock': listing.stock,
                'is_sold': listing.is_sold,
            })

        return JsonResponse({
            'listings': listings_data,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
            'current_page': page_obj.number,
            'num_pages': paginator.num_pages,
            'total_count': paginator.count,
        })
    
    # For regular requests, return the full page
    # Convert categories to a list of dicts for JSON serialization
    categories_data = [{'id': cat.id, 'name': cat.name} for cat in Category.objects.filter(is_active=True)]
    
    # Get location counts and convert to JSON-serializable format
    locations_count = {}
    for code, name in Listing.HOMABAY_LOCATIONS:
        locations_count[code] = Listing.objects.filter(location=code, is_active=True).count()
    
    # Convert locations to a list of tuples for JSON serialization
    locations_data = [{'code': code, 'name': name, 'count': locations_count.get(code, 0)} 
                     for code, name in Listing.HOMABAY_LOCATIONS]
    
    context = {
        'listings': page_obj,
        'categories': categories_data,
        'locations': locations_data,
        'selected_category': category_id,
        'selected_location': location,
        'min_price': min_price,
        'max_price': max_price,
        'search_query': search_query,
        'sort_by': sort_by,
        'total_listings_count': listings.count(),
        'locations_count': locations_count,
    }
    
    # Add featured listings for carousel
    context['featured_listings'] = Listing.objects.filter(
        is_featured=True, 
        is_active=True,
        is_sold=False
    ).order_by('-date_created')[:6]
    
    # Add popular categories
    context['popular_categories'] = Category.objects.filter(
        is_active=True
    ).annotate(
        listing_count=Count('listing', filter=Q(listing__is_active=True))
    ).filter(listing_count__gt=0).order_by('-listing_count')[:12]
    
    # Add user favorites for template
    if request.user.is_authenticated:
        user_favorites = Favorite.objects.filter(
            user=request.user
        ).values_list('listing_id', flat=True)
        context['user_favorites'] = list(user_favorites)
        
        # Recently viewed
        recently_viewed = RecentlyViewed.objects.filter(
            user=request.user
        ).select_related('listing').order_by('-viewed_at')[:6]
        context['recently_viewed'] = [rv.listing for rv in recently_viewed]
    
    return render(request, 'listings/all_listings.html', context)


@login_required
@require_POST
def toggle_favorite(request, listing_id):
    listing = get_object_or_404(Listing, id=listing_id)
    favorite, created = Favorite.objects.get_or_create(
        user=request.user, 
        listing=listing
    )
    
    if not created:
        favorite.delete()
        is_favorited = False
    else:
        is_favorited = True
        # Notify seller about favorite
        if listing.seller != request.user:
            notify_listing_favorited(listing.seller, request.user, listing)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'is_favorited': is_favorited,
            'favorite_count': listing.favorited_by.count()
        })
    
    return redirect('listing-detail', pk=listing_id)

@login_required
def favorite_listings(request):
    favorites = Favorite.objects.filter(user=request.user).select_related('listing')
    return render(request, 'listings/favorites.html', {'favorites': favorites})

@login_required
def my_listings(request):
    listings = Listing.objects.filter(seller=request.user).order_by('-date_created')
    
    # Calculate statistics
    total_listings = listings.count()
    active_listings = listings.filter(is_active=True, is_sold=False).count()
    sold_listings = listings.filter(is_sold=True).count()
    featured_listings = listings.filter(is_featured=True, is_active=True).count()
    
    context = {
        'listings': listings,
        'total_listings': total_listings,
        'active_listings': active_listings,
        'sold_listings': sold_listings,
        'featured_listings': featured_listings,
    }
    
    return render(request, 'listings/my_listings.html', context)
# In your listings/views.py
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db import transaction
from django.utils import timezone
from .models import Cart, CartItem, Order, OrderItem, Payment, Escrow, Listing
from .forms import CheckoutForm
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json


@login_required
def unread_notifications_count(request):
    """API endpoint to get unread notifications count"""
    # You'll need to implement your notifications system
    # For now, returning a placeholder
    unread_count = 0  # Replace with actual notification count logic
    return JsonResponse({'count': unread_count})

@login_required
@require_POST
def update_cart_item(request, item_id):
    """AJAX endpoint for updating cart item quantity"""
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    quantity = int(request.POST.get('quantity', 1))
    
    # Check if quantity doesn't exceed available stock
    if quantity > cart_item.listing.stock:
        return JsonResponse({
            'success': False,
            'error': f"Only {cart_item.listing.stock} units available."
        })
    
    if quantity <= 0:
        cart_item.delete()
        success = True
        item_count = request.user.cart.items.count() if hasattr(request.user, 'cart') else 0
    else:
        cart_item.quantity = quantity
        cart_item.save()
        success = True
        item_count = request.user.cart.items.count() if hasattr(request.user, 'cart') else 0
    
    cart_total = request.user.cart.get_total_price() if hasattr(request.user, 'cart') else 0
    
    return JsonResponse({
        'success': success,
        'cart_total': float(cart_total),
        'item_count': item_count
    })
@login_required
@require_POST
def remove_from_cart(request, item_id):
    """AJAX endpoint for removing cart items"""
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    cart_item.delete()
    
    item_count = request.user.cart.items.count() if hasattr(request.user, 'cart') else 0
    cart_total = request.user.cart.get_total_price() if hasattr(request.user, 'cart') else 0
    
    return JsonResponse({
        'success': True,
        'cart_total': float(cart_total),
        'item_count': item_count
    })

@login_required
@require_POST
def clear_cart(request):
    """Clear entire cart"""
    cart = get_object_or_404(Cart, user=request.user)
    cart.items.all().delete()
    
    return JsonResponse({'success': True})

# Update the existing view_cart function to handle AJAX
@login_required
def view_cart(request):
    cart, created = Cart.objects.get_or_create(user=request.user)
    
    # Handle AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        cart_data = {
            'items': [],
            'total_price': float(cart.get_total_price()),
            'item_count': cart.items.count()
        }
        
        for item in cart.items.all():
            cart_data['items'].append({
                'id': item.id,
                'listing': {
                    'id': item.listing.id,
                    'title': item.listing.title,
                    'price': float(item.listing.price),
                    # Use the model helper which safely returns Cloudinary or local URLs
                    'image_url': item.listing.get_image_url(),
                    'category': item.listing.category.name
                },
                'quantity': item.quantity,
                'total_price': float(item.get_total_price())
            })
        
        return JsonResponse(cart_data)
    
    return render(request, 'listings/cart.html', {'cart': cart})

# Update the add_to_cart function for AJAX
@login_required
def add_to_cart(request, listing_id):
    listing = get_object_or_404(Listing, id=listing_id, is_sold=False)
    
    # Check if item is in stock
    if listing.stock <= 0:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': "This item is out of stock."})
        messages.warning(request, "This item is out of stock.")
        return redirect('listing-detail', pk=listing_id)
    
    # Users shouldn't add their own listings to cart
    if listing.seller == request.user:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': "You cannot add your own listing to cart."})
        messages.warning(request, "You cannot add your own listing to cart.")
        return redirect('listing-detail', pk=listing_id)
    
    cart, created = Cart.objects.get_or_create(user=request.user)
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        listing=listing,
        defaults={'quantity': 1}
    )
    
    if not created:
        # Check if we're not exceeding available stock
        if cart_item.quantity + 1 > listing.stock:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': f"Only {listing.stock} units available."})
            messages.warning(request, f"Only {listing.stock} units of '{listing.title}' are available.")
            return redirect('listing-detail', pk=listing_id)
        
        cart_item.quantity += 1
        cart_item.save()
        message = f"Updated quantity of {listing.title} in your cart."
    else:
        message = f"Added {listing.title} to your cart."
    
    # Handle AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': message,
            'cart_total': float(cart.get_total_price()),
            'item_count': cart.items.count()
        })
    
    messages.success(request, message)
    return redirect('listing-detail', pk=listing_id)

@login_required
def checkout(request):
    cart = get_object_or_404(Cart, user=request.user)
    
    # Validate stock before checkout
    for cart_item in cart.items.all():
        if cart_item.quantity > cart_item.listing.stock:
            messages.error(request, f"Sorry, only {cart_item.listing.stock} units of '{cart_item.listing.title}' are available.")
            return redirect('view_cart')
    
    if request.method == 'POST':
        # Initialize form with user's existing info
        initial_data = {
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
            'phone_number': getattr(request.user, 'phone_number', ''),
        }
        
        # Get latest successful order for shipping info
        latest_order = Order.objects.filter(
            user=request.user,
            status__in=['delivered', 'shipped']
        ).order_by('-created_at').first()
        
        if latest_order:
            initial_data.update({
                'shipping_address': latest_order.shipping_address,
                'city': latest_order.city,
                'postal_code': latest_order.postal_code,
            })
        
        form = CheckoutForm(request.POST, initial=initial_data)
        
        # Check if using alternate shipping
        use_alternate = request.POST.get('use_alternate_shipping') == 'on'
        if not use_alternate:
            # If not using alternate shipping, copy user's info
            form.data = form.data.copy()  # Make mutable
            form.data.update(initial_data)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Create order
                    order = Order.objects.create(
                        user=request.user,
                        total_price=cart.get_total_price(),
                        first_name=form.cleaned_data['first_name'],
                        last_name=form.cleaned_data['last_name'],
                        email=form.cleaned_data['email'],
                        phone_number=form.cleaned_data['phone_number'],
                        shipping_address=form.cleaned_data['shipping_address'],
                        city=form.cleaned_data['city'],
                        postal_code=form.cleaned_data['postal_code'],
                    )
                    
                    # Create order items
                    for cart_item in cart.items.all():
                        OrderItem.objects.create(
                            order=order,
                            listing=cart_item.listing,
                            quantity=cart_item.quantity,
                            price=cart_item.listing.price
                        )
                    
                    # Create payment record
                    payment = Payment.objects.create(
                        order=order,
                        amount=order.total_price
                    )
                    
                    # Create escrow record
                    Escrow.objects.create(
                        order=order,
                        amount=order.total_price
                    )
                    
                    # Clear cart
                    cart.items.all().delete()
                    
                    messages.success(request, "Order created successfully! Please complete payment.")
                    return redirect('process_payment', order_id=order.id)
                    
            except Exception as e:
                messages.error(request, f"An error occurred during checkout: {str(e)}")
                return render(request, 'listings/checkout.html', {
                    'cart': cart,
                    'form': form,
                    'use_alternate_shipping': use_alternate
                })
        else:
            return render(request, 'listings/checkout.html', {
                'cart': cart,
                'form': form,
                'use_alternate_shipping': use_alternate
            })
    else:
        # Pre-fill form with user's info
        initial_data = {
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
            'phone_number': getattr(request.user, 'phone_number', ''),
        }
        
        # Get latest successful order for shipping info
        latest_order = Order.objects.filter(
            user=request.user,
            status__in=['delivered', 'shipped']
        ).order_by('-created_at').first()
        
        if latest_order:
            initial_data.update({
                'shipping_address': latest_order.shipping_address,
                'city': latest_order.city,
                'postal_code': latest_order.postal_code,
            })
            
        form = CheckoutForm(initial=initial_data)
    
    return render(request, 'listings/checkout.html', {
        'cart': cart,
        'form': form,
        'use_alternate_shipping': False,
        'has_previous_orders': latest_order is not None
    })

from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
import json
from .mpesa_utils import mpesa_gateway

import logging
logger = logging.getLogger(__name__)

# Replace the existing process_payment function with this:
@login_required
def process_payment(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    if order.status != 'pending':
        messages.warning(request, "This order has already been processed.")
        return redirect('order_detail', order_id=order.id)
    
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        
        if payment_method == 'mpesa':
            phone_number = request.POST.get('phone_number')
            
            if not phone_number:
                messages.error(request, "Please provide your M-Pesa phone number.")
                return render(request, 'listings/payment.html', {'order': order})
            
            # Initiate M-Pesa payment
            success, message = order.payment.initiate_mpesa_payment(phone_number)
            
            if success:
                messages.success(request, f"M-Pesa payment initiated: {message}")
                return render(request, 'listings/payment.html', {'order': order})
            else:
                messages.error(request, f"Failed to initiate M-Pesa payment: {message}")
                return render(request, 'listings/payment.html', {'order': order})
                
        elif payment_method == 'cash':
            # For cash on delivery, mark as paid immediately
            order.payment.method = 'cash'
            order.payment.status = 'completed'
            order.payment.transaction_id = f"CASH{order.id}{int(timezone.now().timestamp())}"
            order.payment.completed_at = timezone.now()
            order.payment.save()
            
            # Mark order as paid and notify sellers
            order.mark_as_paid()
            _notify_sellers_after_payment(order)
            
            messages.success(request, "Order confirmed! You will pay with cash on delivery.")
            return redirect('order_detail', order_id=order.id)
            
        elif payment_method == 'card':
            # For card payments (simulated for now)
            order.payment.method = 'card'
            order.payment.status = 'completed'
            order.payment.transaction_id = f"CARD{order.id}{int(timezone.now().timestamp())}"
            order.payment.completed_at = timezone.now()
            order.payment.save()
            
            # Mark order as paid and notify sellers
            order.mark_as_paid()
            _notify_sellers_after_payment(order)
            
            messages.success(request, "Card payment processed successfully!")
            return redirect('order_detail', order_id=order.id)
    
    return render(request, 'listings/payment.html', {'order': order})

def _notify_sellers_after_payment(order):
    """Notify all sellers in an order after successful payment"""
    # Group order items by seller
    from collections import defaultdict
    seller_items = defaultdict(list)
    
    for order_item in order.order_items.all():
        seller_items[order_item.listing.seller].append(order_item)
    
    # Notify each seller
    for seller, items in seller_items.items():
        notify_payment_received(seller, order.user, order)
        
        # Create activity log
        Activity.objects.create(
            user=seller,
            action=f"Payment received for order #{order.id}"
        )

@login_required
def initiate_mpesa_payment(request, order_id):
    """AJAX endpoint to initiate M-Pesa payment"""
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id, user=request.user)
        
        if order.status != 'pending':
            return JsonResponse({
                'success': False,
                'error': 'This order has already been processed.'
            })
        
        phone_number = request.POST.get('phone_number')
        
        if not phone_number:
            return JsonResponse({
                'success': False,
                'error': 'Phone number is required.'
            })
        
        # Format phone number (remove spaces and ensure it starts with 254)
        formatted_phone = phone_number.replace(' ', '')
        if formatted_phone.startswith('0'):
            formatted_phone = '254' + formatted_phone[1:]
        elif not formatted_phone.startswith('254'):
            formatted_phone = '254' + formatted_phone
        
        # Initiate payment
        success, message = order.payment.initiate_mpesa_payment(formatted_phone)
        
        if success:
            return JsonResponse({
                'success': True,
                'message': message,
                'checkout_request_id': order.payment.mpesa_checkout_request_id
            })
        else:
            return JsonResponse({
                'success': False,
                'error': message
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def check_payment_status(request, order_id):
    """AJAX endpoint to check M-Pesa payment status with active MPESA status check"""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    payment = order.payment

    # First check the current payment state in our DB
    if payment.status == 'completed':
        return JsonResponse({
            'success': True,
            'payment_status': 'completed',
            'message': 'Payment completed successfully',
            'redirect_url': reverse('order_detail', args=[order.id])
        })
    elif payment.status == 'failed':
        return JsonResponse({
            'success': True, 
            'payment_status': 'failed',
            'message': payment.mpesa_result_desc or 'Payment failed',
            'redirect_url': reverse('process_payment', args=[order.id])
        })
        
    # If payment was initiated via MPESA, check status with MPESA API
    if (payment.status == 'initiated' and 
        payment.method == 'mpesa' and 
        payment.mpesa_checkout_request_id):
            
        from .mpesa_utils import mpesa_gateway
        status_response = mpesa_gateway.check_transaction_status(
            payment.mpesa_checkout_request_id
        )
        
        if status_response['success']:
            result_code = status_response.get('result_code')
            
            # Update payment record based on MPESA response
            if result_code == '0':  # Success
                payment.mark_as_completed(
                    status_response.get('response_data', {}).get('MpesaReceiptNumber')
                )
                return JsonResponse({
                    'success': True,
                    'payment_status': 'completed',
                    'message': 'Payment completed successfully',
                    'redirect_url': reverse('order_detail', args=[order.id])
                })
                
            elif result_code == '1037':  # Timeout waiting for user input
                payment.status = 'failed'
                payment.mpesa_result_code = result_code
                payment.mpesa_result_desc = 'Transaction timed out waiting for user input'
                payment.save()
                return JsonResponse({
                    'success': True,
                    'payment_status': 'failed',
                    'message': 'Transaction timed out. Please try again.',
                    'redirect_url': reverse('process_payment', args=[order.id])
                })
                
            elif result_code == '1032':  # Cancelled by user
                payment.status = 'failed'
                payment.mpesa_result_code = result_code
                payment.mpesa_result_desc = 'Transaction cancelled by user'
                payment.save()
                return JsonResponse({
                    'success': True,
                    'payment_status': 'failed',
                    'message': 'Transaction was cancelled. Please try again if you want to complete the payment.',
                    'redirect_url': reverse('process_payment', args=[order.id])
                })
                
            elif result_code == '1':  # Still processing
                return JsonResponse({
                    'success': True,
                    'payment_status': 'processing',
                    'message': 'Please complete the payment on your phone...'
                })
            else:
                # Any other failure case
                payment.status = 'failed'
                payment.mpesa_result_code = result_code
                payment.mpesa_result_desc = status_response.get('result_desc', 'Payment failed')
                payment.save()
                return JsonResponse({
                    'success': True,
                    'payment_status': 'failed',
                    'message': status_response.get('result_desc', 'Payment failed. Please try again.'),
                    'redirect_url': reverse('process_payment', args=[order.id])
                })
                
        else:
            # Error checking status - tell frontend to keep trying
            logger.error(f"Error checking MPESA status: {status_response.get('error')}")
            return JsonResponse({
                'success': True,
                'payment_status': 'processing',
                'message': 'Checking payment status...'
            })
    
    # For non-MPESA or non-initiated payments, just return current status
    return JsonResponse({
        'success': True,
        'payment_status': 'processing',
        'message': 'Payment is being processed...'
    })
    
@csrf_exempt
@require_POST
def mpesa_callback(request):
    """
    Handle M-Pesa callback with payment result and trigger notifications
    """
    try:
        callback_data = json.loads(request.body)
        
        # Log the callback for debugging
        logger.info(f"M-Pesa Callback Received: {callback_data}")
        
        # Extract the main body
        stk_callback = callback_data.get('Body', {}).get('stkCallback', {})
        checkout_request_id = stk_callback.get('CheckoutRequestID')
        result_code = stk_callback.get('ResultCode')
        result_desc = stk_callback.get('ResultDesc')
        
        if not checkout_request_id:
            return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Invalid callback data'})
        
        # Find the payment with this checkout request ID
        try:
            payment = Payment.objects.get(mpesa_checkout_request_id=checkout_request_id)
            payment.mpesa_result_code = result_code
            payment.mpesa_result_desc = result_desc
            payment.mpesa_callback_data = callback_data
            
            if result_code == 0:
                # Payment was successful
                callback_metadata = stk_callback.get('CallbackMetadata', {}).get('Item', [])
                
                # Extract transaction details
                transaction_data = {}
                for item in callback_metadata:
                    transaction_data[item.get('Name')] = item.get('Value')
                
                mpesa_receipt_number = transaction_data.get('MpesaReceiptNumber')
                
                if mpesa_receipt_number:
                    payment.mark_as_completed(mpesa_receipt_number)
                    
                    # Notify all sellers in the order
                    _notify_sellers_after_payment(payment.order)
                    
                    # Create activity log
                    Activity.objects.create(
                        user=payment.order.user,
                        action=f"M-Pesa payment completed for Order #{payment.order.id}. Receipt: {mpesa_receipt_number}"
                    )
                    
                    logger.info(f"M-Pesa payment successful for order #{payment.order.id}. Receipt: {mpesa_receipt_number}")
                
            else:
                # Payment failed
                payment.status = 'failed'
                payment.save()
                
                logger.warning(f"M-Pesa payment failed for order #{payment.order.id}. Reason: {result_desc}")
            
            return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Callback processed successfully'})
            
        except Payment.DoesNotExist:
            logger.error(f"Payment not found for checkout request ID: {checkout_request_id}")
            return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Payment not found'})
            
    except Exception as e:
        logger.error(f"Error processing M-Pesa callback: {str(e)}")
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Error processing callback'})

@login_required
def mpesa_debug_info(request):
    """Debug endpoint to check M-Pesa configuration"""
    from .mpesa_utils import mpesa_gateway
    
    debug_info = {
        'has_credentials': mpesa_gateway.has_valid_credentials,
        'environment': mpesa_gateway.environment,
        'business_shortcode': mpesa_gateway.business_shortcode,
        'callback_url': mpesa_gateway.callback_url,
    }
    
    # Test access token (without exposing secrets)
    if mpesa_gateway.has_valid_credentials:
        access_token = mpesa_gateway.get_access_token()
        debug_info['access_token_obtained'] = bool(access_token)
        debug_info['access_token_length'] = len(access_token) if access_token else 0
    
    return JsonResponse(debug_info)

@login_required
def order_list(request):
    """Show orders where user is either buyer or seller"""
    # Get filter parameters
    status_filter = request.GET.get('status')
    role_filter = request.GET.get('role')
    
    # Base queries
    buyer_orders = Order.objects.filter(user=request.user)
    seller_orders = Order.objects.filter(order_items__listing__seller=request.user)
    
    # Apply status filter if provided
    if status_filter and status_filter != 'all':
        buyer_orders = buyer_orders.filter(status=status_filter)
        seller_orders = seller_orders.filter(status=status_filter)
    
    # Apply role filter if provided
    if role_filter == 'buyer':
        all_orders = buyer_orders.distinct()
    elif role_filter == 'seller':
        all_orders = seller_orders.distinct()
    else:
        # Combine using union (proper way to combine distinct queries)
        all_orders = buyer_orders.union(seller_orders).order_by('-created_at')
    
    # Ensure proper ordering
    all_orders = all_orders.order_by('-created_at')
    
    # Get counts for display
    buyer_orders_count = buyer_orders.count()
    seller_orders_count = seller_orders.distinct().count()
    
    # Paginate
    paginator = Paginator(all_orders, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'orders': page_obj,
        'status_filter': status_filter,
        'role_filter': role_filter,
        'buyer_orders_count': buyer_orders_count,
        'seller_orders_count': seller_orders_count,
        'total_orders_count': buyer_orders_count + seller_orders_count,
    }
    
    return render(request, 'listings/order_list.html', context)

@login_required
def order_detail(request, order_id):
    """Order detail view that works for both buyers and sellers"""
    order = get_object_or_404(Order, id=order_id)
    
    # Check if user has permission to view this order
    if order.user != request.user and not order.order_items.filter(listing__seller=request.user).exists():
        messages.error(request, "You don't have permission to view this order.")
        return redirect('order_list')
    
    # Determine user's role in this order
    is_buyer = order.user == request.user
    is_seller = order.order_items.filter(listing__seller=request.user).exists()
    
    # Get items relevant to the user - FIXED FOR MULTI-SELLER
    if is_seller and not is_buyer:
        # Show only items that belong to this seller
        order_items = order.order_items.filter(listing__seller=request.user)
        seller_specific_total = sum(float(item.get_total_price()) for item in order_items)
    else:
        # Show all items for buyer or user who is both buyer and seller
        order_items = order.order_items.all()
        seller_specific_total = order.total_price
    
    context = {
        'order': order,
        'order_items': order_items,
        'is_buyer': is_buyer,
        'is_seller': is_seller,
        'seller_specific_total': seller_specific_total,  # Add this for seller view
        'can_ship': is_seller and order.status == 'paid',
        'can_confirm': is_buyer and order.status == 'shipped',
        'can_dispute': is_buyer and order.status in ['shipped', 'delivered'],
    }
    
    return render(request, 'listings/order_detail.html', context) # Seller views

@login_required
def seller_orders(request):
    # By request: show only orders that contain items exclusively from this seller
    # i.e. total order_items == order_items belonging to this seller
    orders = Order.objects.annotate(
        total_items=Count('order_items'),
        seller_items=Count('order_items', filter=Q(order_items__listing__seller=request.user))
    ).filter(total_items=F('seller_items')).order_by('-created_at')

    return render(request, 'listings/seller_orders.html', {'orders': orders})

@login_required
def mark_order_shipped(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    # Check if the user is the seller of any item in this order
    if not order.order_items.filter(listing__seller=request.user).exists():
        messages.error(request, "You don't have permission to modify this order.")
        return redirect('seller_orders')
    
    # Allow marking shipments when order is paid or already partially shipped
    if order.status not in ['paid', 'partially_shipped']:
        messages.warning(request, "Only paid orders can be marked as shipped.")
        return redirect('seller_orders')

    # Mark only the items that belong to this seller as shipped
    seller_items = order.order_items.filter(listing__seller=request.user, shipped=False)
    if not seller_items.exists():
        messages.info(request, "There are no unshipped items for this order belonging to you.")
        return redirect('seller_orders')

    from django.utils import timezone
    now = timezone.now()

    for item in seller_items:
        item.shipped = True
        item.shipped_at = now
        # Allow seller to provide a tracking number via POST (optional)
        tracking_number = request.POST.get('tracking_number') or ''
        if tracking_number:
            item.tracking_number = tracking_number
        item.save()

    # If any items remain unshipped by other sellers, mark order as partially_shipped
    remaining = order.order_items.filter(shipped=False)
    if remaining.exists():
        order.status = 'partially_shipped'
        order.save()

        # Notify buyer about the partial shipment by this seller
        # Use the first tracking number if provided
        first_tracking = seller_items.filter(tracking_number__isnull=False).first()
        notify_order_shipped(order.user, request.user, order, first_tracking.tracking_number if first_tracking else None)

        messages.success(request, f"Your items for Order #{order.id} have been marked as shipped. Waiting on other sellers to complete their shipments.")

        # Remind remaining sellers when only a few are left
        try:
            from notifications.utils import NotificationService, create_notification
            from django.conf import settings
        except Exception:
            NotificationService = None

        remaining_sellers = set(item.listing.seller for item in remaining)
        REMINDER_THRESHOLD = getattr(settings, 'SELLER_SHIPMENT_REMINDER_THRESHOLD', 2)

        if NotificationService and 0 < len(remaining_sellers) <= REMINDER_THRESHOLD:
            ns = NotificationService()
            for seller in remaining_sellers:
                # SMS reminder if configured
                try:
                    sms_msg = f"Order #{order.id} has most sellers shipped. Please mark your items as shipped so the buyer can receive their order."
                    ns.send_sms(getattr(seller, 'phone_number', ''), sms_msg)
                except Exception:
                    logger.exception("Failed to send shipment reminder SMS")

                # In-app/system notification
                try:
                    create_notification(
                        recipient=seller,
                        notification_type='system',
                        title='Action required: Ship items',
                        message=f'Order #{order.id} still has unshipped items assigned to you. Please mark them as shipped.',
                        sender=request.user,
                        related_object_id=order.id,
                        related_content_type='order',
                        action_url=reverse('order_detail', args=[order.id]),
                        action_text='View Order'
                    )
                except Exception:
                    logger.exception("Failed to create in-app shipment reminder")

        # Activity log
        Activity.objects.create(
            user=request.user,
            action=f"Order #{order.id} items marked as shipped (seller: {request.user.username})"
        )

        return redirect('seller_orders')

    # If no remaining items, finalize order as shipped
    order.status = 'shipped'
    order.shipped_at = now
    order.save()

    # Consolidated delivery request for whole order (for single-seller orders this behaves as before)
    delivery_response = _create_delivery_request(order)

    tracking_number = None
    if delivery_response and delivery_response.get('success'):
        tracking_number = delivery_response.get('tracking_number')
        driver_info = delivery_response.get('driver', {})

        order.tracking_number = tracking_number or order.tracking_number
        order.save()

        # Notify buyer
        notify_order_shipped(order.user, request.user, order, tracking_number)

        if driver_info:
            notify_delivery_assigned(order, driver_info.get('name', 'Delivery Partner'), driver_info.get('estimated_delivery', 'Soon'))

        messages.success(request, f"Order #{order.id} marked as shipped. Tracking: {tracking_number}")
    else:
        # Notify buyer that order is shipped but delivery integration lacked tracking
        notify_order_shipped(order.user, request.user, order, None)
        messages.success(request, f"Order #{order.id} marked as shipped. Delivery system may not have provided tracking.")

    Activity.objects.create(
        user=request.user,
        action=f"Order #{order.id} marked as shipped by {request.user.username}"
    )

    return redirect('seller_orders')

def _create_delivery_request(order):
    """Create delivery request in the delivery system"""
    try:
        try:
            from integrations.delivery import DeliverySystemIntegration
        except ImportError:
            logger.error("DeliverySystemIntegration could not be imported. Delivery integration is unavailable.")
            return None

        delivery_integration = DeliverySystemIntegration()
        return delivery_integration.create_delivery_from_order(order)
        
    except Exception as e:
        logger.error(f"Delivery system integration failed: {str(e)}")
        return None

# Update confirm_delivery to notify seller
@login_required
def confirm_delivery(request, order_id):
    """Buyer confirms delivery - MANDATORY for fund release"""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    if order.status != 'shipped':
        messages.warning(request, "This order has not been shipped yet or has already been delivered.")
        return redirect('order_detail', order_id=order.id)
    
    # Update order status
    order.status = 'delivered'
    order.delivered_at = timezone.now()
    order.save()
    
    # Release escrow funds to all sellers
    _release_escrow_to_sellers(order)
    
    # Notify sellers about delivery confirmation and fund release
    _notify_sellers_delivery_confirmed(order)
    
    # Create activity log
    Activity.objects.create(
        user=request.user,
        action=f"Order #{order.id} delivered and confirmed"
    )
    
    messages.success(request, "Thank you for confirming delivery! Funds have been released to the seller(s).")
    return redirect('order_detail', order_id=order.id)

def _release_escrow_to_sellers(order):
    """Release escrow funds to all sellers in the order"""
    # Group order items by seller to handle multiple sellers
    from collections import defaultdict
    seller_amounts = defaultdict(float)
    
    for order_item in order.order_items.all():
        seller = order_item.listing.seller
        seller_amounts[seller] += float(order_item.get_total_price())
    
    # Release funds to each seller
    for seller, amount in seller_amounts.items():
        # In a real system, you'd actually transfer funds here
        # For now, we'll just mark the escrow as released
        logger.info(f"Releasing KSh {amount} to seller {seller.username} for order #{order.id}")
    
    # Update escrow status
    order.escrow.status = 'released'
    order.escrow.released_at = timezone.now()
    order.escrow.save()

def _notify_sellers_delivery_confirmed(order):
    """Notify all sellers that delivery was confirmed and funds released"""
    sellers = set(item.listing.seller for item in order.order_items.all())
    
    for seller in sellers:
        notify_delivery_confirmed(seller, order.user, order)
        
        # Create activity log for seller
        Activity.objects.create(
            user=seller,
            action=f"Delivery confirmed and funds released for Order #{order.id}"
        )
@login_required
def create_dispute(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    if order.status not in ['shipped', 'delivered']:
        messages.warning(request, "You can only dispute orders that have been shipped or delivered.")
        return redirect('order_detail', order_id=order.id)
    
    order.status = 'disputed'
    order.save()
    
    order.escrow.status = 'disputed'
    order.escrow.save()
    
    # Create activity log
    Activity.objects.create(
        user=request.user,
        action=f"Dispute created for Order #{order.id}"
    )
    
    messages.info(request, "Dispute created. Our team will review your case and contact you shortly.")
    return redirect('order_detail', order_id=order.id)


from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from .models import Review, Order
from .forms import ReviewForm

@login_required
def leave_review(request, listing_id=None, seller_id=None):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    if listing_id:
        listing = get_object_or_404(Listing, id=listing_id)
        seller = listing.seller

        if request.user == seller:
            messages.error(request, "You cannot review your own listing.")
            return redirect('listing-detail', pk=listing.id)

        existing_review = Review.objects.filter(
            user=request.user,
            listing=listing
        ).first()

        if request.method == 'POST':
            form = ReviewForm(request.POST, instance=existing_review)
            if form.is_valid():
                review = form.save(commit=False)
                review.user = request.user
                review.listing = listing
                review.save()
                
                # Notify seller about the new review
                notify_new_review(seller, request.user, review, listing)
                
                messages.success(request, "Thank you for your review!")
                return redirect('listing-detail', pk=listing.id)
        else:
            form = ReviewForm(instance=existing_review)

        return render(request, 'reviews/create_review.html', {
            'form': form,
            'listing': listing,
            'seller': seller,
        })

    elif seller_id:
        seller = get_object_or_404(User, id=seller_id)

        if request.user == seller:
            messages.error(request, "You cannot review yourself.")
            return redirect('profile', pk=seller.id)

        listings = Listing.objects.filter(seller=seller)
        existing_review = Review.objects.filter(
            user=request.user,
            listing__seller=seller
        ).first()

        if request.method == 'POST':
            form = ReviewForm(request.POST, instance=existing_review)
            if form.is_valid():
                review = form.save(commit=False)
                review.user = request.user
                # Use the first listing or let user choose - you might want to improve this
                review.listing = listings.first()
                review.save()
                
                # Use review.listing instead of undefined 'listing' variable
                notify_new_review(seller, request.user, review, review.listing)
                
                messages.success(request, "Thank you for your review!")
                return redirect('profile', pk=seller.id)
        else:
            form = ReviewForm(instance=existing_review)

        return render(request, 'reviews/create_review.html', {
            'form': form,
            'seller': seller,
            'listings': listings,
        })
    else:
        messages.error(request, "No listing or seller specified for review.")
        return redirect('home')