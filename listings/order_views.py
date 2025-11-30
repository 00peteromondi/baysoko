from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Order
from .order_utils import OrderManager
from .dispute_utils import DisputeManager

@login_required
def mark_order_shipped(request, order_id):
    try:
        order = get_object_or_404(Order, id=order_id)
        
        # Check if user is a seller for this order
        if not order.order_items.filter(listing__seller=request.user).exists():
            messages.error(request, "You don't have permission to modify this order.")
            return redirect('seller_orders')

        tracking_number = request.POST.get('tracking_number')
        OrderManager.mark_items_shipped(order, request.user, tracking_number)

        messages.success(request, f"Your items for Order #{order.id} have been marked as shipped.")
        
    except Exception as e:
        messages.error(request, str(e))
    
    return redirect('seller_orders')

@login_required
def confirm_delivery(request, order_id):
    try:
        order = get_object_or_404(Order, id=order_id)
        OrderManager.confirm_delivery(order, request.user)
        
        messages.success(request, "Delivery confirmed successfully! The sellers have been notified.")
        
    except Exception as e:
        messages.error(request, str(e))
    
    return redirect('order_detail', order_id=order.id)

@login_required
@require_POST
def create_dispute(request, order_id):
    try:
        order = get_object_or_404(Order, id=order_id, user=request.user)
        
        reason = request.POST.get('reason')
        description = request.POST.get('description')
        evidence_files = request.FILES.getlist('evidence')

        DisputeManager.create_dispute(
            order=order,
            reason=reason,
            description=description,
            evidence_files=evidence_files
        )

        messages.success(request, "Dispute created successfully. Our team will review your case.")
        
    except Exception as e:
        messages.error(request, str(e))
    
    return redirect('order_detail', order_id=order.id)

@login_required
def update_order_status(request, order_id):
    """
    Admin/Staff only view to update order status
    """
    if not request.user.is_staff:
        messages.error(request, "You don't have permission to perform this action.")
        return redirect('order_detail', order_id=order_id)
        
    try:
        order = get_object_or_404(Order, id=order_id)
        new_status = request.POST.get('status')
        notes = request.POST.get('notes')
        
        OrderManager.update_order_status(
            order=order,
            new_status=new_status,
            actor=request.user,
            notes={'admin_notes': notes} if notes else None
        )
        
        messages.success(request, f"Order status updated to {new_status}")
        
    except Exception as e:
        messages.error(request, str(e))
    
    return redirect('order_detail', order_id=order_id)

@login_required
def resolve_dispute(request, order_id):
    """
    Admin/Staff only view to resolve disputes
    """
    if not request.user.is_staff:
        messages.error(request, "You don't have permission to perform this action.")
        return redirect('order_detail', order_id=order_id)
        
    try:
        order = get_object_or_404(Order, id=order_id)
        resolution = request.POST.get('resolution')
        refund_amount = request.POST.get('refund_amount')
        seller_penalty = request.POST.get('seller_penalty')
        
        if refund_amount:
            refund_amount = float(refund_amount)
        if seller_penalty:
            seller_penalty = float(seller_penalty)
            
        DisputeManager.resolve_dispute(
            order=order,
            resolution=resolution,
            refund_amount=refund_amount,
            seller_penalty=seller_penalty
        )
        
        messages.success(request, "Dispute resolved successfully")
        
    except Exception as e:
        messages.error(request, str(e))
    
    return redirect('order_detail', order_id=order_id)

@login_required
def mediate_dispute(request, order_id):
    """
    Admin/Staff only view to add mediation notes
    """
    if not request.user.is_staff:
        messages.error(request, "You don't have permission to perform this action.")
        return redirect('order_detail', order_id=order_id)
        
    try:
        order = get_object_or_404(Order, id=order_id)
        notes = request.POST.get('mediator_notes')
        proposed_solution = request.POST.get('proposed_solution')
        
        DisputeManager.mediate_dispute(
            order=order,
            mediator_notes={'mediator': request.user, 'notes': notes},
            proposed_solution=proposed_solution
        )
        
        messages.success(request, "Mediation notes added successfully")
        
    except Exception as e:
        messages.error(request, str(e))
    
    return redirect('order_detail', order_id=order_id)