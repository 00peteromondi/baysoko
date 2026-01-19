# storefront/views_subscription.py (updated)
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from .models import Store, Subscription, MpesaPayment
from .forms import SubscriptionPlanForm, UpgradeForm
from .subscription_service import SubscriptionService
from .utils.subscription_states import SubscriptionStateManager
import logging

logger = logging.getLogger(__name__)

# storefront/views_subscription.py (updated)
@login_required
def subscription_plan_select(request, slug):
    """Main entry point with trial tracking"""
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    
    # Get detailed trial status
    trial_status = SubscriptionService.get_user_trial_status(request.user)
    eligibility = SubscriptionService.get_user_eligibility(request.user, store)
    
    # Combine data
    context_data = {
        'store': store,
        'trial_status': trial_status,
        'eligibility': eligibility,
        'can_start_trial': trial_status['can_start_trial'],
        'trial_count': trial_status['trial_count'],
        'trial_limit': trial_status['trial_limit'],
        'remaining_trials': trial_status['summary']['remaining_trials'],
        'has_exceeded_limit': trial_status['summary']['has_exceeded_limit'],
    }
    
    if request.method == 'POST':
        plan_form = SubscriptionPlanForm(request.POST)
        upgrade_form = UpgradeForm(request.POST)
        
        if plan_form.is_valid() and upgrade_form.is_valid():
            plan = plan_form.cleaned_data['plan']
            phone_number = upgrade_form.cleaned_data['phone_number']
            start_trial = request.POST.get('start_trial', False)
            
            if start_trial:
                if not trial_status['can_start_trial']:
                    messages.error(request, 
                        f"❌ Trial Not Available: You have already used {trial_status['trial_count']} "
                        f"out of {trial_status['trial_limit']} allowed trials."
                    )
                    return redirect('storefront:subscription_plan_select', slug=slug)
                
                # Start trial with tracking
                success, result = SubscriptionService.start_trial_with_tracking(
                    store=store,
                    plan=plan,
                    phone_number=phone_number,
                    user=request.user
                )
                
                if success:
                    trial_data = result
                    messages.success(
                        request,
                        f"✅ {plan.capitalize()} trial #{trial_data['trial_number']} started! "
                        f"This is trial {trial_data['trial_number']} of {trial_status['trial_limit']}. "
                        f"You have {trial_data['remaining_trials']} trial(s) remaining."
                    )
                    return redirect('storefront:subscription_payment_options', slug=slug)
                else:
                    messages.error(request, result)
                    return redirect('storefront:subscription_plan_select', slug=slug)
            else:
                # Subscribe immediately
                success, subscription = SubscriptionService.subscribe_immediately(
                    store=store,
                    plan=plan,
                    phone_number=phone_number
                )
                
                if success:
                    payment_success, payment_result = SubscriptionService.process_payment(
                        subscription=subscription,
                        phone_number=phone_number
                    )
                    
                    if payment_success:
                        messages.success(
                            request,
                            f"✅ {plan.capitalize()} subscription started! "
                            "Please complete the M-Pesa payment on your phone."
                        )
                        return redirect('storefront:subscription_manage', slug=slug)
                    else:
                        messages.warning(
                            request,
                            f"Subscription created but payment failed: {payment_result}. "
                            "Please try the payment again from your subscription management page."
                        )
                        return redirect('storefront:subscription_manage', slug=slug)
                else:
                    messages.error(request, subscription)
                    return redirect('storefront:subscription_plan_select', slug=slug)
    
    else:
        plan_form = SubscriptionPlanForm()
        upgrade_form = UpgradeForm()
        
        # Pre-fill phone if available
        if eligibility['active_subscription'] and eligibility['active_subscription'].mpesa_phone:
            last_phone = eligibility['active_subscription'].mpesa_phone.replace('+254', '')
            upgrade_form = UpgradeForm(initial={'phone_number': last_phone})
    
    context_data.update({
        'plan_form': plan_form,
        'phone_form': upgrade_form,
        'plan_details': SubscriptionService.PLAN_DETAILS,
    })
    
    return render(request, 'storefront/subscription_plan_select.html', context_data)

@login_required
def subscription_trial_dashboard(request):
    """Dashboard showing trial usage and limits"""
    trial_status = SubscriptionService.get_user_trial_status(request.user)
    analytics = SubscriptionService.get_trial_usage_analytics(request.user)
    
    context = {
        'trial_status': trial_status,
        'analytics': analytics,
        'trial_history': trial_status['trial_subscriptions'],
        'active_trial': trial_status['active_trial'],
        'can_start_new_trial': trial_status['can_start_trial'],
        'trial_progress': {
            'used': trial_status['trial_count'],
            'total': trial_status['trial_limit'],
            'percentage': (trial_status['trial_count'] / trial_status['trial_limit']) * 100 if trial_status['trial_limit'] > 0 else 0,
        }
    }
    
    return render(request, 'storefront/subscription_trial_dashboard.html', context)

@login_required
def subscription_payment_options(request, slug):
    """Show payment options after plan selection"""
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    
    # Get active trial or subscription
    subscription = Subscription.objects.filter(
        store=store,
        status__in=['trialing', 'active']
    ).order_by('-created_at').first()
    
    if not subscription:
        messages.error(request, "No active subscription found. Please select a plan first.")
        return redirect('storefront:subscription_plan_select', slug=slug)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'pay_now':
            # Process payment for trial user wanting to subscribe
            if subscription.status == 'trialing':
                # Convert trial to paid - this now handles payment internally
                success, result = SubscriptionService.convert_trial_to_paid(
                    subscription=subscription,
                    phone_number=subscription.mpesa_phone.replace('+254', '')
                )

                if success:
                    messages.success(
                        request,
                        f"Payment initiated for {subscription.get_plan_display()} plan. "
                        "Please complete the M-Pesa payment to activate your subscription."
                    )
                else:
                    messages.error(request, f"Payment initiation failed: {result}")

                return redirect('storefront:subscription_manage', slug=slug)
            else:
                # For non-trial subscriptions, process payment
                payment_success, payment_result = SubscriptionService.process_payment(
                    subscription=subscription,
                    phone_number=subscription.mpesa_phone.replace('+254', '')
                )

                if payment_success:
                    messages.success(
                        request,
                        f"Payment initiated. Please complete the M-Pesa payment on your phone."
                    )
                else:
                    messages.error(request, f"Payment initiation failed: {payment_result}")

                return redirect('storefront:subscription_manage', slug=slug)
        
        elif action == 'continue_trial':
            messages.info(
                request,
                f"Enjoy your {subscription.get_plan_display()} trial! "
                "You can subscribe anytime before the trial ends."
            )
            return redirect('storefront:seller_dashboard')
    
    # Calculate trial info
    trial_info = None
    if subscription.status == 'trialing' and subscription.trial_ends_at:
        remaining_days = (subscription.trial_ends_at - timezone.now()).days
        trial_info = {
            'remaining_days': max(0, remaining_days),
            'ends_at': subscription.trial_ends_at,
            'is_expired': remaining_days < 0,
        }
    
    context = {
        'store': store,
        'subscription': subscription,
        'trial_info': trial_info,
        'formatted_amount': f"KSh {subscription.amount:,}",
    }
    
    return render(request, 'storefront/subscription_payment_options.html', context)

# In the subscription_manage function in views_subscription.py
@login_required
def subscription_manage(request, slug):
    """Manage subscription"""
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    
    # Get all subscriptions for history
    subscription_history = Subscription.objects.filter(
        store=store
    ).order_by('-created_at')
    
    # Get active subscription
    current_subscription = subscription_history.first()
    
    if not current_subscription:
        messages.info(request, "No subscription found. Upgrade to unlock premium features.")
        return redirect('storefront:subscription_plan_select', slug=slug)
    
    # Get recent payments for current subscription
    recent_payments = current_subscription.payments.order_by('-created_at')[:5]
    
    # Determine required action
    action_required = None
    now = timezone.now()
    
    if current_subscription.status == 'trialing':
        if current_subscription.trial_ends_at and now > current_subscription.trial_ends_at:
            action_required = 'trial_expired'
        elif current_subscription.trial_ends_at and (current_subscription.trial_ends_at - now).days <= 2:
            action_required = 'trial_ending'
    
    elif current_subscription.status == 'past_due':
        action_required = 'past_due'
    
    elif current_subscription.status == 'canceled':
        action_required = 'renew'
    
    # Calculate trial info
    trial_info = None
    if current_subscription.status == 'trialing' and current_subscription.trial_ends_at:
        remaining_days = (current_subscription.trial_ends_at - now).days
        trial_info = {
            'remaining_days': max(0, remaining_days),
            'ends_at': current_subscription.trial_ends_at,
            'is_expired': remaining_days < 0,
        }
    
    # Format subscription history for display
    formatted_history = []
    for sub in subscription_history:
        formatted_history.append({
            'id': sub.id,
            'plan': sub.get_plan_display(),
            'status': sub.get_status_display(),
            'status_class': sub.status,
            'amount': sub.amount,
            'started_at': sub.started_at,
            'current_period_end': sub.current_period_end,
            'trial_ends_at': sub.trial_ends_at,
            'cancelled_at': sub.canceled_at,
            'created_at': sub.created_at,
            'is_current': sub.id == current_subscription.id,
        })
    
    context = {
        'store': store,
        'subscription': current_subscription,
        'subscription_history': formatted_history,
        'recent_payments': recent_payments,
        'trial_info': trial_info,
        'action_required': action_required,
        'plan_details': SubscriptionService.PLAN_DETAILS.get(current_subscription.plan, {}),
        'is_active': current_subscription.status == 'active',
        'is_trialing': current_subscription.status == 'trialing',
        'is_expired': current_subscription.status in ['past_due', 'canceled'],
        'trial_count': SubscriptionService.get_user_trial_status(request.user)['trial_count'],
        'remaining_trials': SubscriptionService.get_user_trial_status(request.user)['summary']['remaining_trials'],
        'trial_limit': SubscriptionService.get_user_trial_status(request.user)['trial_limit'],
        'trial_available': SubscriptionService.get_user_trial_status(request.user)['can_start_trial'],
        'can_change_plan': current_subscription.status in ['active', 'trialing'],
    }
    
    # Use different template based on state
    if action_required == 'trial_expired':
        return render(request, 'storefront/subscription_trial_expired.html', context)
    elif action_required == 'past_due':
        return render(request, 'storefront/subscription_past_due.html', context)
    elif action_required == 'renew':
        return render(request, 'storefront/subscription_needs_renewal.html', context)
    
    return render(request, 'storefront/subscription_manage.html', context)

@login_required
def subscription_change_plan(request, slug):
    """Change subscription plan"""
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    
    # Get current subscription
    subscription = Subscription.objects.filter(
        store=store,
        status__in=['active', 'trialing']
    ).order_by('-created_at').first()
    
    if not subscription:
        messages.error(request, "No active subscription found.")
        return redirect('storefront:subscription_plan_select', slug=slug)
    
    if request.method == 'POST':
        new_plan = request.POST.get('plan')
        phone_number = request.POST.get('phone_number')
        
        if new_plan not in SubscriptionService.PLAN_DETAILS:
            messages.error(request, "Invalid plan selected.")
            return redirect('storefront:subscription_change_plan', slug=slug)
        
        # For plan changes that require payment, phone number is required
        old_price = SubscriptionService.PLAN_DETAILS[subscription.plan]['price']
        new_price = SubscriptionService.PLAN_DETAILS[new_plan]['price']
        is_upgrade = new_price > old_price
        
        requires_payment = (
            subscription.status in ['canceled', 'past_due'] or  # Always requires payment for inactive
            (subscription.status in ['active', 'trialing'] and is_upgrade)  # Requires payment for upgrades
        )
        
        if requires_payment and not phone_number:
            messages.error(request, "Phone number is required for plan changes that require payment.")
            return redirect('storefront:subscription_change_plan', slug=slug)
        
        # Pass the subscription object and phone number
        success, message = SubscriptionService.change_plan(subscription, new_plan, phone_number)
        
        if success:
            messages.success(request, message)
        else:
            messages.error(request, message)
        
        return redirect('storefront:subscription_manage', slug=slug)
    
    context = {
        'store': store,
        'subscription': subscription,
        'plan_details': SubscriptionService.PLAN_DETAILS,
        'current_plan': subscription.plan,
        'requires_payment': subscription.status in ['canceled', 'past_due'],
    }
    
    return render(request, 'storefront/subscription_change_plan.html', context)

@login_required
def subscription_renew(request, slug):
    """Renew expired subscription"""
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    
    # Get the most recent expired subscription
    subscription = Subscription.objects.filter(
        store=store,
        status__in=['canceled', 'past_due']
    ).order_by('-created_at').first()
    
    if not subscription:
        messages.error(request, "No expired subscription found.")
        return redirect('storefront:subscription_plan_select', slug=slug)
    
    if request.method == 'POST':
        form = UpgradeForm(request.POST)
        
        if form.is_valid():
            phone_number = form.cleaned_data['phone_number']
            
            # Renew subscription - this now handles payment internally
            success, result = SubscriptionService.renew_subscription(
                subscription=subscription,
                phone_number=phone_number
            )
            
            if success:
                renewed_subscription = result
                messages.success(
                    request,
                    f"✅ Payment initiated! Please complete the M-Pesa payment to renew your subscription."
                )
                return redirect('storefront:subscription_manage', slug=slug)
            else:
                messages.error(request, f"❌ Failed to renew subscription: {result}")
                return redirect('storefront:subscription_renew', slug=slug)
    
    else:
        # Pre-fill with last used phone number
        initial = {}
        if subscription.mpesa_phone:
            phone = subscription.mpesa_phone.replace('+254', '')
            initial['phone_number'] = phone
        
        form = UpgradeForm(initial=initial)
    
    context = {
        'store': store,
        'subscription': subscription,
        'form': form,
        'formatted_amount': f"KSh {subscription.amount:,}",
        'trial_count': SubscriptionService.get_user_trial_status(request.user)['trial_count'],
        'trial_limit': SubscriptionService.get_user_trial_status(request.user)['trial_limit'],
    }
    
    return render(request, 'storefront/subscription_renew.html', context)
    
@login_required
def subscription_cancel(request, slug):
    """Cancel subscription"""
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    
    subscription = Subscription.objects.filter(
        store=store,
        status__in=['active', 'trialing']
    ).order_by('-created_at').first()
    
    if not subscription:
        messages.error(request, "No active subscription found.")
        return redirect('storefront:subscription_manage', slug=slug)
    
    if request.method == 'POST':
        success = SubscriptionService.cancel_subscription(subscription, cancel_at_period_end=False)
        
        if success:
            messages.info(
                request,
                f"Your {subscription.get_plan_display()} subscription has been canceled immediately. "
                "Premium features have been disabled for your store."
            )
        else:
            messages.error(request, "Failed to cancel subscription.")
        
        return redirect('storefront:subscription_manage', slug=slug)
    
    context = {
        'store': store,
        'subscription': subscription,
    }
    
    return render(request, 'storefront/subscription_cancel.html', context)