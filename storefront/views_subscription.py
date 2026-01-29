# storefront/views_subscription.py (updated)
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from .models import Store, Subscription, MpesaPayment
from .mpesa import MpesaGateway
from .forms import SubscriptionPlanForm, UpgradeForm
from .subscription_service import SubscriptionService
from .utils.subscription_states import SubscriptionStateManager
from .decorators import store_owner_required
from django.db.models import Q
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
                # Subscribe immediately - creates unpaid subscription
                success, subscription = SubscriptionService.subscribe_immediately(
                    store=store,
                    plan=plan,
                    phone_number=phone_number
                )
                
                if success:
                    # Process payment for the unpaid subscription
                    payment_success, payment_result = SubscriptionService.process_payment(
                        subscription=subscription,
                        phone_number=phone_number
                    )
                    
                    if payment_success:
                        messages.success(
                            request,
                            f"✅ {plan.capitalize()} subscription created! "
                            "Please complete the M-Pesa payment on your phone to activate your subscription."
                        )
                        return redirect('storefront:subscription_manage', slug=slug)
                    else:
                        # Payment failed - subscription remains unpaid
                        messages.error(
                            request,
                            f"Payment initiation failed: {payment_result}. "
                            "Your subscription has been saved but requires payment to activate."
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

@login_required
def subscription_manage(request, slug):
    """Manage subscription with free listing limit warnings"""
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    
    # Get listing limit info
    requires_upgrade, limit_info = check_listing_requires_upgrade(request.user, store)
    
    # Get all subscriptions for history
    subscription_history = Subscription.objects.filter(
        store=store
    ).order_by('-created_at')
    
    # Get active subscription
    current_subscription = subscription_history.first()
    
    # Get recent payments
    recent_payments = []
    if current_subscription:
        recent_payments = current_subscription.payments.order_by('-created_at')[:5]
    
    # Determine required action
    action_required = None
    now = timezone.now()
    
    if not current_subscription:
        if requires_upgrade:
            action_required = 'free_limit_reached'
        else:
            action_required = 'no_subscription'
    elif current_subscription.status == 'trialing':
        if current_subscription.trial_ends_at and now > current_subscription.trial_ends_at:
            action_required = 'trial_expired'
        elif current_subscription.trial_ends_at and (current_subscription.trial_ends_at - now).days <= 2:
            action_required = 'trial_ending'
    elif current_subscription.status == 'past_due':
        action_required = 'past_due'
    elif current_subscription.status == 'canceled':
        action_required = 'renew'
    elif requires_upgrade and current_subscription.plan == 'basic':
        action_required = 'upgrade_needed'
    
    # Calculate trial info
    trial_info = None
    if current_subscription and current_subscription.status == 'trialing' and current_subscription.trial_ends_at:
        remaining_days = (current_subscription.trial_ends_at - now).days
        trial_info = {
            'remaining_days': max(0, remaining_days),
            'ends_at': current_subscription.trial_ends_at,
            'is_expired': remaining_days < 0,
        }
    
    # Format subscription history
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
            'is_current': sub.id == current_subscription.id if current_subscription else False,
        })
    
    context = {
        'store': store,
        'subscription': current_subscription,
        'subscription_history': formatted_history,
        'recent_payments': recent_payments,
        'trial_info': trial_info,
        'action_required': action_required,
        'limit_reached': requires_upgrade,
        'current_count': limit_info['current_count'],
        'free_limit': limit_info['free_limit'],
        'remaining_slots': limit_info['remaining_slots'],
        'percentage_used': limit_info['percentage_used'],
        'plan_details': SubscriptionService.PLAN_DETAILS,
        'is_active': current_subscription and current_subscription.status == 'active',
        'is_trialing': current_subscription and current_subscription.status == 'trialing',
        'is_expired': current_subscription and current_subscription.status in ['past_due', 'canceled'],
        'trial_count': SubscriptionService.get_user_trial_status(request.user)['trial_count'],
        'remaining_trials': SubscriptionService.get_user_trial_status(request.user)['summary']['remaining_trials'],
        'trial_limit': SubscriptionService.get_user_trial_status(request.user)['trial_limit'],
        'trial_available': SubscriptionService.get_user_trial_status(request.user)['can_start_trial'],
        'can_change_plan': current_subscription and current_subscription.status in ['active', 'trialing'],
    }
    
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

# Add at the top
from .utils.subscription_utils import check_listing_requires_upgrade, get_user_listing_limits

@login_required
@store_owner_required
def store_upgrade(request, slug):
    """
    Enhanced upgrade view that handles both subscription upgrades and free listing limit warnings
    """
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    
    # Check if user has reached free listing limit
    requires_upgrade, limit_info = check_listing_requires_upgrade(request.user, store)
    
    # Check trial eligibility
    past_trial_exists = Subscription.objects.filter(
        store__owner=request.user,
        trial_ends_at__isnull=False,
        trial_ends_at__lt=timezone.now()
    ).exists()
    can_start_trial = not past_trial_exists
    
    # Get plan from session or default
    selected_plan = request.session.get('selected_plan', 'basic')
    
    # Plan pricing
    plan_pricing = {
        'basic': 999,
        'premium': 1999,
        'enterprise': 4999
    }
    
    amount = plan_pricing.get(selected_plan, 999)
    
    if request.method == 'POST':
        form = UpgradeForm(request.POST)
        if form.is_valid():
            phone_number = form.cleaned_data['phone_number']
            plan_from_post = request.POST.get('plan', selected_plan)
            
            if plan_from_post in plan_pricing:
                selected_plan = plan_from_post
                amount = plan_pricing[selected_plan]
            
            try:
                mpesa = MpesaGateway()
                
                # Handle start-trial request
                if 'start_trial' in request.POST and request.POST.get('start_trial') == '1':
                    if not can_start_trial:
                        messages.error(request, "You have already used a trial period and cannot start another one.")
                        return redirect('storefront:subscription_manage', slug=slug)
                    
                    subscription = Subscription.objects.filter(store=store).first()
                    # Normalize phone to avoid DB truncation
                    phone_norm = mpesa._normalize_phone(phone_number)
                    if not subscription:
                        subscription = Subscription.objects.create(
                            store=store,
                            plan=selected_plan,
                            status='trialing',
                            amount=amount,
                            trial_ends_at=timezone.now() + timedelta(days=7),
                            mpesa_phone=phone_norm,
                            metadata={'plan_selected': selected_plan}
                        )
                    else:
                        subscription.plan = selected_plan
                        subscription.amount = amount
                        subscription.mpesa_phone = phone_norm
                        subscription.metadata['plan_selected'] = selected_plan
                        subscription.status = 'trialing'
                        subscription.trial_ends_at = timezone.now() + timedelta(days=7)
                        subscription.save()
                    
                    # Activate premium features
                    store.is_premium = True
                    store.save()
                    
                    messages.success(request, "Trial started — premium features are active for 7 days.")
                    return redirect('storefront:seller_dashboard')
                
                # Subscription payment flow
                subscription = Subscription.objects.filter(store=store).filter(
                    Q(status='active') | Q(status='trialing', trial_ends_at__gt=timezone.now())
                ).first()
                
                if not subscription:
                    phone_norm = mpesa._normalize_phone(phone_number)
                    subscription = Subscription.objects.create(
                        store=store,
                        plan=selected_plan,
                        status='trialing',
                        amount=amount,
                        trial_ends_at=timezone.now() + timedelta(days=7),
                        mpesa_phone=phone_norm,
                        metadata={'plan_selected': selected_plan}
                    )
                else:
                    subscription.plan = selected_plan
                    subscription.amount = amount
                    subscription.mpesa_phone = mpesa._normalize_phone(phone_number)
                    subscription.metadata['plan_selected'] = selected_plan
                    subscription.save()
                
                # Initiate M-Pesa payment
                response = mpesa.initiate_stk_push(
                    phone=mpesa._normalize_phone(phone_number),
                    amount=amount,
                    account_reference=f"Store-{store.id}-{selected_plan}"
                )
                
                # Create payment record
                MpesaPayment.objects.create(
                    subscription=subscription,
                    checkout_request_id=response['CheckoutRequestID'],
                    merchant_request_id=response['MerchantRequestID'],
                    phone_number=mpesa._normalize_phone(phone_number),
                    amount=amount,
                    status='pending'
                )
                
                # Activate premium features
                store.is_premium = True
                store.save()
                
                # Clear session data
                if 'selected_plan' in request.session:
                    del request.session['selected_plan']
                
                messages.success(request, 
                    f"✅ Payment of KSh {amount:,} initiated for {selected_plan.capitalize()} plan. "
                    "Please check your phone to complete the M-Pesa payment."
                )
                return redirect('storefront:seller_dashboard')
                
            except Exception as e:
                logger.error(f"Payment initiation failed for store {store.id}: {str(e)}")
                messages.error(request, 
                    f'Payment initiation failed: {str(e)}. '
                    'Please check your phone number and try again.'
                )
                return render(request, 'storefront/subscription_manage.html', {
                    'store': store,
                    'form': form,
                    'selected_plan': selected_plan,
                    'amount': amount,
                    'can_start_trial': can_start_trial,
                    'limit_reached': requires_upgrade,
                    'current_count': limit_info['current_count'],
                    'free_limit': limit_info['free_limit'],
                })
    
    else:
        # GET request
        existing_sub = store.subscriptions.filter(
            Q(status='active') | Q(status='trialing', trial_ends_at__gt=timezone.now())
        ).first()
        
        if existing_sub:
            messages.info(request, 
                f"You already have an active {existing_sub.get_plan_display()} subscription. "
                f"Status: {existing_sub.get_status_display()}"
            )
            return redirect('storefront:subscription_manage', slug=slug)
        
        # Pre-fill phone if available
        initial_data = {}
        last_payment = MpesaPayment.objects.filter(
            subscription__store=store,
            status='completed'
        ).order_by('-created_at').first()
        
        if last_payment:
            phone = last_payment.phone_number
            if phone.startswith('+254'):
                phone = phone[4:]
            elif phone.startswith('254'):
                phone = phone[3:]
            initial_data['phone_number'] = phone
        
        form = UpgradeForm(initial=initial_data)
    
    # Use subscription_manage template instead of confirm_upgrade
    return render(request, 'storefront/subscription_manage.html', {
        'store': store,
        'form': form,
        'selected_plan': selected_plan,
        'amount': amount,
        'can_start_trial': can_start_trial,
        'limit_reached': requires_upgrade,
        'current_count': limit_info['current_count'],
        'free_limit': limit_info['free_limit'],
        'upgrade_mode': True,  # Flag to show upgrade-specific content
    })


@login_required
@store_owner_required
def subscription_invoice(request, slug, payment_id):
    """
    View invoice for a payment
    """
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    payment = get_object_or_404(MpesaPayment, id=payment_id, subscription__store=store)
    
    context = {
        'store': store,
        'payment': payment,
        'subscription': payment.subscription,
    }
    
    return render(request, 'storefront/subscription_invoice.html', context)


@login_required
@store_owner_required
def subscription_settings(request, slug):
    """
    Subscription settings (update payment method, etc.)
    """
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    subscription = Subscription.objects.filter(store=store).order_by('-created_at').first()
    
    if request.method == 'POST':
        # Handle settings update
        phone_number = request.POST.get('phone_number')
        
        if phone_number:
            # Validate phone number
            if len(phone_number) == 9 and phone_number.startswith('7'):
                if subscription:
                    mpesa = MpesaGateway()
                    subscription.mpesa_phone = mpesa._normalize_phone(phone_number)
                    subscription.save()
                    messages.success(request, "Payment method updated successfully.")
                else:
                    messages.error(request, "No subscription found.")
            else:
                messages.error(request, "Please enter a valid Kenyan phone number.")
        
        return redirect('storefront:subscription_settings', slug=slug)
    
    context = {
        'store': store,
        'subscription': subscription,
    }
    
    return render(request, 'storefront/subscription_settings.html', context)


@login_required
@store_owner_required
def retry_payment(request, slug):
    """Retry failed payment"""
    if request.method != 'POST':
        return redirect('storefront:subscription_manage', slug=slug)
        
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    subscription = store.subscriptions.order_by('-started_at').first()
    
    if not subscription or subscription.status not in ['past_due', 'trialing']:
        messages.error(request, 'Invalid subscription status for payment retry.')
        return redirect('storefront:subscription_manage', slug=slug)
    
    # Get last known phone number
    last_payment = subscription.payments.filter(
        Q(status='completed') | Q(phone_number__isnull=False)
    ).order_by('-transaction_date').first()
    
    if not last_payment or not last_payment.phone_number:
        messages.error(request, 'No payment phone number found. Please upgrade again.')
        return redirect('storefront:store_upgrade', slug=slug)
    
    try:
        mpesa = MpesaGateway()
        phone_norm = mpesa._normalize_phone(last_payment.phone_number)
        
        # Use subscription amount, not hardcoded 999
        response = mpesa.initiate_stk_push(
            phone=phone_norm,
            amount=float(subscription.amount),
            account_reference=f"Store-{store.id}-Retry"
        )
        
        MpesaPayment.objects.create(
            subscription=subscription,
            checkout_request_id=response['CheckoutRequestID'],
            merchant_request_id=response['MerchantRequestID'],
            phone_number=phone_norm,
            amount=subscription.amount,
            status='pending'
        )
        
        messages.success(request, 'Payment initiated. Please complete the M-Pesa payment on your phone.')
        
    except Exception as e:
        logger.error(f"Payment retry failed: {str(e)}")
        messages.error(request, f'Failed to initiate payment: {str(e)}')
    
    return redirect('storefront:subscription_manage', slug=slug)




