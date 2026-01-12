# storefront/urls_inventory.py
from django.urls import path
from . import views_inventory

inventory_patterns = [
    # Inventory Dashboard
    path('dashboard/store/<slug:slug>/inventory/', views_inventory.inventory_dashboard, name='inventory_dashboard'),
    path('dashboard/store/<slug:slug>/inventory/list/', views_inventory.inventory_list, name='inventory_list'),

    # Alerts Management
    path('dashboard/store/<slug:slug>/inventory/alerts/', views_inventory.inventory_alerts, name='inventory_alerts'),
    path('dashboard/store/<slug:slug>/inventory/alerts/<int:alert_id>/delete/', views_inventory.delete_alert, name='delete_inventory_alert'),
    path('dashboard/store/<slug:slug>/inventory/alerts/<int:alert_id>/toggle/', views_inventory.toggle_alert, name='toggle_inventory_alert'),

    # Variants Management
    path('dashboard/store/<slug:slug>/product/<int:product_id>/variants/', views_inventory.manage_variants, name='manage_variants'),
    path('dashboard/store/<slug:slug>/variant/<int:variant_id>/delete/', views_inventory.delete_variant, name='delete_variant'),

    # Stock Operations
    path('dashboard/store/<slug:slug>/inventory/adjust/', views_inventory.adjust_stock, name='adjust_stock'),
    path('dashboard/store/<slug:slug>/inventory/bulk-update/', views_inventory.bulk_stock_update, name='bulk_stock_update'),
    path('dashboard/store/<slug:slug>/inventory/movements/', views_inventory.stock_movements, name='stock_movements'),

    # Import/Export
    path('dashboard/store/<slug:slug>/inventory/export/', views_inventory.export_inventory, name='export_inventory'),
    path('dashboard/store/<slug:slug>/inventory/import/', views_inventory.import_inventory, name='import_inventory'),

    # AJAX Endpoints
    path('dashboard/store/<slug:slug>/product/<int:product_id>/variants/json/', views_inventory.get_product_variants, name='get_product_variants'),
    path('dashboard/store/<slug:slug>/product/<int:product_id>/quick-stock/', views_inventory.quick_stock_update, name='quick_stock_update'),
]