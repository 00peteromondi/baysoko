from django.urls import path
from .views import ListingListView, ListingDetailView, ListingCreateView, ListingUpdateView, ListingDeleteView
from . import views
from . import order_views


urlpatterns = [
    path('', ListingListView.as_view(), name='home'),
    path('listing/<int:pk>/', ListingDetailView.as_view(), name='listing-detail'),
    path('all-listings/', views.all_listings, name='all-listings'),
    path('my-listings/', views.my_listings, name='my-listings'),
    path('favorites/', views.favorite_listings, name='favorites'),
    path('listing/<int:listing_id>/toggle_favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('listing/new/', ListingCreateView.as_view(), name='listing-create'),
    path('listing/<int:pk>/update/', ListingUpdateView.as_view(), name='listing-update'),
    path('listing/<int:pk>/delete/', ListingDeleteView.as_view(), name='listing-delete'),
    path('cart/add/<int:listing_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/', views.view_cart, name='view_cart'),
    path('cart/update/<int:item_id>/', views.update_cart_item, name='update_cart_item'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/clear/', views.clear_cart, name='clear_cart'),
    path('api/cart/clear/', views.clear_cart, name='clear-cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('order/<int:order_id>/payment/', views.process_payment, name='process_payment'),
    path('orders/<int:order_id>/initiate-mpesa/', views.initiate_mpesa_payment, name='initiate_mpesa_payment'),
    path('order/<int:order_id>/check-payment-status/', views.check_payment_status, name='check_payment_status'),
    path('api/mpesa-callback/', views.mpesa_callback, name='mpesa_callback'),
    path('order/<int:order_id>/', views.order_detail, name='order_detail'),
    path('orders/', views.order_list, name='order_list'),
    path('seller/orders/', views.seller_orders, name='seller_orders'),
    path('order/<int:order_id>/ship/', order_views.mark_order_shipped, name='mark_order_shipped'),
    path('order/<int:order_id>/deliver/', order_views.confirm_delivery, name='confirm_delivery'),
    path('order/<int:order_id>/dispute/', order_views.create_dispute, name='create_dispute'),
    path('order/<int:order_id>/update-status/', order_views.update_order_status, name='update_order_status'),
    path('order/<int:order_id>/resolve-dispute/', order_views.resolve_dispute, name='resolve_dispute'),
    path('order/<int:order_id>/mediate-dispute/', order_views.mediate_dispute, name='mediate_dispute'),
    path('listing/<int:listing_id>/review/', views.leave_review, name='leave_listing_review'),
    path('seller/<int:seller_id>/review/', views.leave_review, name='leave_seller_review'),
    
]