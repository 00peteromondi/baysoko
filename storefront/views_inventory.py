# storefront/views_inventory.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.db.models import Q, Sum, F, Count, Case, When, Value, IntegerField, Avg
from django.db import transaction
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
import json
from io import BytesIO
import csv

from .models import Store, InventoryAlert, ProductVariant, StockMovement, InventoryAudit
from .forms_inventory import (
    InventoryAlertForm, ProductVariantForm, 
    StockAdjustmentForm, InventoryAuditForm,
    BulkStockUpdateForm
)
from listings.models import Listing, Category
from .decorators import store_owner_required, plan_required

@login_required
@store_owner_required('inventory')
@plan_required('inventory')
def inventory_dashboard(request, slug):
    """Main inventory dashboard with overview"""
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    
    # Inventory metrics
    total_products = store.listings.count()
    low_stock_items = store.listings.filter(stock__lte=5, stock__gt=0).count()
    out_of_stock_items = store.listings.filter(stock=0).count()
    
    # Stock value
    stock_value = store.listings.aggregate(
        total_value=Sum(F('price') * F('stock'))
    )['total_value'] or 0
    
    # Recent stock movements
    recent_movements = StockMovement.objects.filter(
        store=store
    ).select_related('product', 'created_by')[:10]
    
    # Active alerts
    active_alerts = InventoryAlert.objects.filter(
        store=store,
        is_active=True
    ).count()
    
    # Stock turnover (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    sales_movements = StockMovement.objects.filter(
        store=store,
        movement_type='sale',
        created_at__gte=thirty_days_ago
    ).aggregate(total_sold=Sum('quantity'))['total_sold'] or 0
    
    # Calculate stock turnover rate
    avg_stock = store.listings.aggregate(
        avg_stock=Avg('stock')
    )['avg_stock'] or 0
    turnover_rate = (sales_movements / (avg_stock * 30)) * 100 if avg_stock > 0 else 0
    
    # Category distribution
    category_distribution = store.listings.values(
        'category__name'
    ).annotate(
        count=Count('id'),
        total_stock=Sum('stock')
    ).order_by('-count')[:5]
    
    context = {
        'store': store,
        'total_products': total_products,
        'low_stock_items': low_stock_items,
        'out_of_stock_items': out_of_stock_items,
        'stock_value': stock_value,
        'active_alerts': active_alerts,
        'turnover_rate': round(turnover_rate, 2),
        'recent_movements': recent_movements,
        'category_distribution': category_distribution,
    }
    
    return render(request, 'storefront/inventory/dashboard.html', context)

@login_required
@store_owner_required('inventory')
def inventory_list(request, slug):
    """Detailed inventory listing with filters"""
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    
    # Get filter parameters
    category_id = request.GET.get('category')
    stock_status = request.GET.get('stock_status')
    search_query = request.GET.get('q')
    sort_by = request.GET.get('sort', 'name')
    sort_order = request.GET.get('order', 'asc')
    
    # Base queryset
    products = store.listings.select_related('category').prefetch_related('variants')
    
    # Apply filters
    if category_id:
        products = products.filter(category_id=category_id)
    
    if stock_status:
        if stock_status == 'low':
            products = products.filter(stock__lte=5, stock__gt=0)
        elif stock_status == 'out':
            products = products.filter(stock=0)
        elif stock_status == 'good':
            products = products.filter(stock__gt=10)
    
    if search_query:
        products = products.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(sku__icontains=search_query)
        )
    
    # Apply sorting
    if sort_by == 'name':
        products = products.order_by('title' if sort_order == 'asc' else '-title')
    elif sort_by == 'stock':
        products = products.order_by('stock' if sort_order == 'asc' else '-stock')
    elif sort_by == 'price':
        products = products.order_by('price' if sort_order == 'asc' else '-price')
    elif sort_by == 'sales':
        products = products.annotate(
            sales_count=Count('order_items')
        ).order_by('sales_count' if sort_order == 'asc' else '-sales_count')
    
    # Pagination
    paginator = Paginator(products, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get categories for filter dropdown
    categories = Category.objects.filter(
        listing__store=store
    ).distinct()
    
    context = {
        'store': store,
        'page_obj': page_obj,
        'categories': categories,
        'selected_category': category_id,
        'selected_status': stock_status,
        'search_query': search_query or '',
        'sort_by': sort_by,
        'sort_order': sort_order,
    }
    
    return render(request, 'storefront/inventory/list.html', context)

@login_required
@store_owner_required('inventory')
def inventory_alerts(request, slug):
    """Manage inventory alerts"""
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    
    alerts = InventoryAlert.objects.filter(store=store).select_related('product')
    
    if request.method == 'POST':
        form = InventoryAlertForm(store, request.POST)
        if form.is_valid():
            alert = form.save(commit=False)
            alert.store = store
            alert.save()
            messages.success(request, 'Inventory alert created successfully.')
            return redirect('storefront:inventory_alerts', slug=slug)
    else:
        form = InventoryAlertForm(store)
    
    context = {
        'store': store,
        'alerts': alerts,
        'form': form,
    }
    
    return render(request, 'storefront/inventory/alerts.html', context)

@login_required
@store_owner_required('inventory')
def manage_variants(request, slug, product_id):
    """Manage product variants"""
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    product = get_object_or_404(Listing, id=product_id, store=store)
    
    variants = product.variants.all()
    
    if request.method == 'POST':
        form = ProductVariantForm(request.POST)
        if form.is_valid():
            variant = form.save(commit=False)
            variant.listing = product
            variant.save()
            messages.success(request, 'Product variant added successfully.')
            return redirect('storefront:manage_variants', slug=slug, product_id=product_id)
    else:
        form = ProductVariantForm()
    
    context = {
        'store': store,
        'product': product,
        'variants': variants,
        'form': form,
    }
    
    return render(request, 'storefront/inventory/variants.html', context)

@login_required
@store_owner_required('inventory')
def adjust_stock(request, slug):
    """Adjust stock levels"""
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    
    if request.method == 'POST':
        form = StockAdjustmentForm(store, request.POST)
        if form.is_valid():
            with transaction.atomic():
                data = form.cleaned_data
                product = data['product']
                variant = data['variant']
                quantity = data['quantity']
                notes = data['notes']
                adjustment_type = request.POST.get('adjustment_type', 'add')
                
                # Determine which stock to adjust
                if variant:
                    previous_stock = variant.stock
                    if adjustment_type == 'add':
                        variant.stock += quantity
                    elif adjustment_type == 'remove':
                        variant.stock = max(0, variant.stock - quantity)
                    else:  # set
                        variant.stock = max(0, quantity)
                    variant.save()
                    
                    # Create stock movement record
                    StockMovement.objects.create(
                        store=store,
                        product=product,
                        variant=variant,
                        movement_type='adjustment',
                        quantity=quantity,
                        previous_stock=previous_stock,
                        new_stock=variant.stock,
                        notes=notes,
                        created_by=request.user
                    )
                else:
                    previous_stock = product.stock
                    if adjustment_type == 'add':
                        product.stock += quantity
                    elif adjustment_type == 'remove':
                        product.stock = max(0, product.stock - quantity)
                    else:  # set
                        product.stock = max(0, quantity)
                    product.save()
                    
                    # Create stock movement record
                    StockMovement.objects.create(
                        store=store,
                        product=product,
                        movement_type='adjustment',
                        quantity=quantity,
                        previous_stock=previous_stock,
                        new_stock=product.stock,
                        notes=notes,
                        created_by=request.user
                    )
                
                messages.success(request, 'Stock adjusted successfully.')
                return redirect('storefront:inventory_dashboard', slug=slug)
    
    else:
        form = StockAdjustmentForm(store)
    
    context = {
        'store': store,
        'form': form,
    }
    
    return render(request, 'storefront/inventory/adjust_stock.html', context)

@login_required
@store_owner_required('inventory')
def bulk_stock_update(request, slug):
    """Bulk update stock levels"""
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    
    if request.method == 'POST':
        form = BulkStockUpdateForm(store, request.POST)
        if form.is_valid():
            data = form.cleaned_data
            update_type = data['update_type']
            value = float(data['value'])
            apply_to = data['apply_to']
            
            # Get products to update
            if apply_to == 'all':
                products = store.listings.all()
            elif apply_to == 'category' and data['category']:
                products = store.listings.filter(category=data['category'])
            elif apply_to == 'low_stock':
                products = store.listings.filter(stock__lte=5, stock__gt=0)
            elif apply_to == 'out_of_stock':
                products = store.listings.filter(stock=0)
            else:
                products = store.listings.none()
            
            # Apply updates
            updated_count = 0
            for product in products:
                if update_type == 'percentage':
                    product.stock = max(0, int(product.stock * (1 + value / 100)))
                elif update_type == 'fixed':
                    product.stock = max(0, product.stock + int(value))
                else:  # set
                    product.stock = max(0, int(value))
                
                product.save()
                updated_count += 1
            
            messages.success(request, f'Updated stock for {updated_count} products.')
            return redirect('storefront:inventory_list', slug=slug)
    
    else:
        form = BulkStockUpdateForm(store)
    
    context = {
        'store': store,
        'form': form,
    }
    
    return render(request, 'storefront/inventory/bulk_update.html', context)

@login_required
@store_owner_required('inventory')
def export_inventory(request, slug):
    """Export inventory to CSV"""
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    
    products = store.listings.select_related('category').prefetch_related('variants')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{store.slug}_inventory_{timezone.now().date()}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'SKU', 'Product Name', 'Category', 'Price', 'Stock', 
        'Cost Price', 'Weight (g)', 'Dimensions', 'Status'
    ])
    
    for product in products:
        writer.writerow([
            product.sku or '',
            product.title,
            product.category.name if product.category else '',
            product.price,
            product.stock,
            product.cost_price or '',
            product.weight or '',
            product.dimensions or '',
            'Active' if product.is_active else 'Inactive'
        ])
    
    return response

@login_required
@store_owner_required('inventory')
def import_inventory(request, slug):
    """Import inventory from CSV"""
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        
        try:
            # Import pandas lazily to avoid hard dependency at module import time
            import pandas as pd
            # Read CSV file
            df = pd.read_csv(csv_file)
            required_columns = ['Product Name', 'Price', 'Stock']
            
            if not all(col in df.columns for col in required_columns):
                messages.error(request, 'CSV file must contain required columns.')
                return redirect('storefront:import_inventory', slug=slug)
            
            created_count = 0
            updated_count = 0
            errors = []
            
            for index, row in df.iterrows():
                try:
                    sku = row.get('SKU', '')
                    title = row['Product Name']
                    price = float(row['Price'])
                    stock = int(row['Stock'])
                    category_name = row.get('Category', '')
                    
                    # Get or create category
                    category = None
                    if category_name:
                        category, _ = Category.objects.get_or_create(
                            name=category_name,
                            defaults={'is_active': True}
                        )
                    
                    # Check if product exists
                    if sku:
                        product = Listing.objects.filter(sku=sku, store=store).first()
                    else:
                        product = Listing.objects.filter(
                            title__iexact=title,
                            store=store
                        ).first()
                    
                    if product:
                        # Update existing product
                        product.price = price
                        product.stock = stock
                        if category:
                            product.category = category
                        product.save()
                        updated_count += 1
                    else:
                        # Create new product
                        Listing.objects.create(
                            store=store,
                            title=title,
                            price=price,
                            stock=stock,
                            category=category,
                            sku=sku or None,
                            seller=request.user,
                            is_active=True
                        )
                        created_count += 1
                        
                except Exception as e:
                    errors.append(f"Row {index + 2}: {str(e)}")
            
            # Show results
            if errors:
                messages.warning(request, f'Import completed with {len(errors)} errors.')
                request.session['import_errors'] = errors[:10]  # Store first 10 errors
            else:
                messages.success(request, f'Import successful: {created_count} created, {updated_count} updated.')
            
            return redirect('storefront:inventory_list', slug=slug)
            
        except Exception as e:
            messages.error(request, f'Error processing CSV file: {str(e)}')
    
    return render(request, 'storefront/inventory/import.html', {'store': store})

@login_required
@store_owner_required('inventory')
def stock_movements(request, slug):
    """View stock movement history"""
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    
    movements = StockMovement.objects.filter(store=store).select_related(
        'product', 'variant', 'created_by'
    ).order_by('-created_at')
    
    # Apply filters
    movement_type = request.GET.get('type')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if movement_type:
        movements = movements.filter(movement_type=movement_type)
    
    if date_from:
        movements = movements.filter(created_at__date__gte=date_from)
    
    if date_to:
        movements = movements.filter(created_at__date__lte=date_to)
    
    # Pagination
    paginator = Paginator(movements, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'store': store,
        'page_obj': page_obj,
        'movement_types': StockMovement.MOVEMENT_TYPES,
    }
    
    return render(request, 'storefront/inventory/movements.html', context)

@require_POST
@login_required
@store_owner_required('inventory')
def delete_alert(request, slug, alert_id):
    """Delete inventory alert"""
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    alert = get_object_or_404(InventoryAlert, id=alert_id, store=store)
    
    alert.delete()
    messages.success(request, 'Alert deleted successfully.')
    
    return redirect('storefront:inventory_alerts', slug=slug)

@require_POST
@login_required
@store_owner_required('inventory')
def toggle_alert(request, slug, alert_id):
    """Toggle alert active status"""
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    alert = get_object_or_404(InventoryAlert, id=alert_id, store=store)
    
    alert.is_active = not alert.is_active
    alert.save()
    
    status = "activated" if alert.is_active else "deactivated"
    messages.success(request, f'Alert {status} successfully.')
    
    return redirect('storefront:inventory_alerts', slug=slug)

@require_POST
@login_required
@store_owner_required('inventory')
def delete_variant(request, slug, variant_id):
    """Delete product variant"""
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    variant = get_object_or_404(ProductVariant, id=variant_id, listing__store=store)
    
    variant.delete()
    messages.success(request, 'Variant deleted successfully.')
    
    return redirect('storefront:manage_variants', slug=slug, product_id=variant.listing_id)

# AJAX Views
@require_GET
@login_required
def get_product_variants(request, slug, product_id):
    """Get variants for a product (AJAX)"""
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    product = get_object_or_404(Listing, id=product_id, store=store)
    
    variants = product.variants.filter(is_active=True).values('id', 'name', 'value', 'stock')
    
    return JsonResponse({'variants': list(variants)})

@require_POST
@login_required
def quick_stock_update(request, slug, product_id):
    """Quick stock update via AJAX"""
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    product = get_object_or_404(Listing, id=product_id, store=store)
    
    try:
        data = json.loads(request.body)
        new_stock = int(data.get('stock', 0))
        variant_id = data.get('variant_id')
        
        with transaction.atomic():
            if variant_id:
                variant = get_object_or_404(ProductVariant, id=variant_id, listing=product)
                previous_stock = variant.stock
                variant.stock = max(0, new_stock)
                variant.save()
                
                # Record movement
                StockMovement.objects.create(
                    store=store,
                    product=product,
                    variant=variant,
                    movement_type='adjustment',
                    quantity=new_stock - previous_stock,
                    previous_stock=previous_stock,
                    new_stock=variant.stock,
                    notes='Quick update via dashboard',
                    created_by=request.user
                )
            else:
                previous_stock = product.stock
                product.stock = max(0, new_stock)
                product.save()
                
                # Record movement
                StockMovement.objects.create(
                    store=store,
                    product=product,
                    movement_type='adjustment',
                    quantity=new_stock - previous_stock,
                    previous_stock=previous_stock,
                    new_stock=product.stock,
                    notes='Quick update via dashboard',
                    created_by=request.user
                )
        
        return JsonResponse({
            'success': True,
            'new_stock': new_stock,
            'product_id': product_id,
            'variant_id': variant_id
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

# Celery Tasks
from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string

@shared_task
def check_inventory_alerts():
    """Check and trigger inventory alerts"""
    from .models import InventoryAlert
    
    alerts = InventoryAlert.objects.filter(
        is_active=True,
        product__is_active=True
    ).select_related('product', 'store', 'store__owner')
    
    triggered_alerts = []
    
    for alert in alerts:
        if alert.check_condition():
            # Update last triggered
            alert.last_triggered = timezone.now()
            alert.save()
            
            triggered_alerts.append(alert)
            
            # Send notifications
            if 'email' in alert.notification_method:
                send_stock_alert_email.delay(alert.id)
            
            if 'sms' in alert.notification_method:
                send_stock_alert_sms.delay(alert.id)
    
    return f"Checked {len(alerts)} alerts, triggered {len(triggered_alerts)}"

@shared_task
def send_stock_alert_email(alert_id):
    """Send email notification for stock alert"""
    from .models import InventoryAlert
    
    try:
        alert = InventoryAlert.objects.get(id=alert_id)
        store = alert.store
        product = alert.product
        
        subject = f"Stock Alert: {product.title} is {alert.get_alert_type_display()}"
        
        context = {
            'store': store,
            'product': product,
            'alert': alert,
            'current_stock': product.stock,
        }
        
        html_message = render_to_string('storefront/emails/stock_alert.html', context)
        text_message = render_to_string('storefront/emails/stock_alert.txt', context)
        
        send_mail(
            subject=subject,
            message=text_message,
            from_email='noreply@homabaysouq.com',
            recipient_list=[store.owner.email],
            html_message=html_message,
            fail_silently=True,
        )
        
    except Exception as e:
        print(f"Error sending stock alert email: {e}")

@shared_task
def send_stock_alert_sms(alert_id):
    """Send SMS notification for stock alert"""
    # Implement SMS sending logic using Africa's Talking
    pass