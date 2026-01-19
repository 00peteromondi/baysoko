# storefront/views_subscription.py (updated)
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from .models import Store, Subscription, MpesaPayment
from .forms import SubscriptionPlanForm, UpgradeForm
from .mpesa import MpesaGateway
from .utils.subscription_states import SubscriptionStateManager


import logging

logger = logging.getLogger(__name__)

@login_required
def subscription_plan_select(request, slug):
    """
    Handle all subscription states: new, trial, active, expired, cancelled
    """
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    
    # Get comprehensive subscription state
    state = SubscriptionStateManager.get_user_subscription_state(request.user, store)
    
    # Plan details
    plan_details = {
        'basic': {
            'name': 'Basic',
            'price': 999,
            'period': 'month',
            'features': [
                'Priority listing',
                'Basic analytics',
                'Store customization',
                'Verified badge',
                'Up to 50 products',
                '1 storefront',
                'Email support',
            ],
            'icon': 'bi-star',
            'color': 'primary',
        },
        'premium': {
            'name': 'Premium',
            'price': 1999,
            'period': 'month',
            'features': [
                'Everything in Basic',
                'Advanced analytics',
                'Bulk product upload',
                'Inventory management',
                'Product bundles',
                'Up to 200 products',
                '3 storefronts',
                'Priority support',
            ],
            'icon': 'bi-award',
            'color': 'warning',
            'popular': True,
        },
        'enterprise': {
            'name': 'Enterprise',
            'price': 4999,
            'period': 'month',
            'features': [
                'Everything in Premium',
                'Custom integrations',
                'API access',
                'Unlimited products',
                'Unlimited storefronts',
                'Custom domain',
                'Dedicated support',
                'White-label options',
            ],
            'icon': 'bi-building',
            'color': 'danger',
        }
    }
    
    # Handle different states
    if state['has_active_subscription']:
        messages.info(request, f"You already have an active {state['subscription'].get_plan_display()} subscription.")
        return redirect('storefront:subscription_manage', slug=slug)
    
    if request.method == 'POST':
        plan_form = SubscriptionPlanForm(request.POST)
        upgrade_form = UpgradeForm(request.POST)
        
        if plan_form.is_valid() and upgrade_form.is_valid():
            plan = plan_form.cleaned_data['plan']
            phone_number = upgrade_form.cleaned_data['phone_number']
            start_trial = 'start_trial' in request.POST
            
            # Check if user wants to start trial
            if start_trial:
                if not state['can_start_trial']:
                    messages.error(request, "You are not eligible for a free trial.")
                    return redirect('storefront:subscription_plan_select', slug=slug)
                
                # Start trial
                return _start_trial(request, store, plan, phone_number, plan_details[plan]['price'])
            else:
                # Skip trial and subscribe immediately
                return _subscribe_immediately(request, store, plan, phone_number, plan_details[plan]['price'])
        
        else:
            messages.error(request, "Please correct the errors below.")
    
    else:
        # GET request - pre-fill forms
        plan_form = SubscriptionPlanForm()
        upgrade_form = UpgradeForm()
        
        # Pre-fill with last used phone if available
        if state['subscription'] and state['subscription'].mpesa_phone:
            last_phone = state['subscription'].mpesa_phone.replace('+254', '')
            upgrade_form = UpgradeForm(initial={'phone_number': last_phone})
        
        # Pre-select current plan if exists
        if state['subscription']:
            plan_form = SubscriptionPlanForm(initial={'plan': state['subscription'].plan})
    
    # Determine what action buttons to show
    show_trial_button = state['can_start_trial']
    show_subscribe_button = True
    
    # If user has expired trial, show different message
    if state['has_expired_trial']:
        show_trial_button = False
        messages.info(request, "Your free trial has ended. Please subscribe to continue using premium features.")
    
    # If user has past due, show renewal message
    if state['has_past_due']:
        messages.warning(request, "Your subscription is past due. Please renew to restore premium features.")
    
    context = {
        'store': store,
        'plan_form': plan_form,
        'phone_form': upgrade_form,
        'plan_details': plan_details,
        'subscription_state': state,
        'show_trial_button': show_trial_button,
        'show_subscribe_button': show_subscribe_button,
        'action_required': SubscriptionStateManager.get_subscription_action_required(state['subscription']),
    }
    
    # Use different template based on state
    template = 'storefront/subscription_plan_select_streamlined.html'
    
    # If user has specific state, use specialized template
    if state['has_expired_trial'] or state['needs_renewal']:
        template = 'storefront/subscription_renew.html'
    elif not state['can_start_trial'] and state['subscription']:
        template = 'storefront/subscription_change_plan.html'
    
    return render(request, template, context)

def _start_trial(request, store, plan, phone_number, amount):
    """Start a free trial"""
    with transaction.atomic():
        # Create or update subscription
        subscription, created = Subscription.objects.get_or_create(
            store=store,
            defaults={
                'plan': plan,
                'status': 'trialing',
                'amount': amount,
                'trial_ends_at': timezone.now() + timedelta(days=7),
                'mpesa_phone': f"+254{phone_number}",
                'metadata': {
                    'trial_started': timezone.now().isoformat(),
                    'plan_selected': plan,
                    'via_trial': True,
                }
            }
        )
        
        if not created:
            subscription.plan = plan
            subscription.status = 'trialing'
            subscription.trial_ends_at = timezone.now() + timedelta(days=7)
            subscription.mpesa_phone = f"+254{phone_number}"
            subscription.metadata.update({
                'trial_started': timezone.now().isoformat(),
                'plan_selected': plan,
                'via_trial': True,
            })
            subscription.save()
        
        # Enable premium features for trial
        store.is_premium = True
        store.save()
        
        # Store in session for payment flow
        request.session['subscription_data'] = {
            'store_slug': store.slug,
            'plan': plan,
            'phone_number': phone_number,
            'amount': amount,
            'via_trial': True,
        }
        
        messages.success(
            request,
            f"✅ {plan.capitalize()} trial started! "
            f"You have 7 days to experience all premium features."
        )
        
        # Redirect to payment options (with option to pay now or continue trial)
        return redirect('storefront:subscription_payment_options', slug=store.slug)

def _subscribe_immediately(request, store, plan, phone_number, amount):
    """Subscribe immediately (skip trial)"""
    with transaction.atomic():
        # Create subscription
        subscription = Subscription.objects.create(
            store=store,
            plan=plan,
            status='active',
            amount=amount,
            current_period_end=timezone.now() + timedelta(days=30),
            mpesa_phone=f"+254{phone_number}",
            metadata={
                'subscribed_at': timezone.now().isoformat(),
                'plan_selected': plan,
                'via_immediate': True,
                'skipped_trial': True,
            }
        )
        
        # Enable premium features
        store.is_premium = True
        store.save()
        
        # Initiate payment
        try:
            mpesa = MpesaGateway()
            
            response = mpesa.initiate_stk_push(
                phone=f"+254{phone_number}",
                amount=float(amount),
                account_reference=f"SUB-{store.id}-{plan.upper()}"
            )
            
            # Create payment record
            MpesaPayment.objects.create(
                subscription=subscription,
                checkout_request_id=response['CheckoutRequestID'],
                merchant_request_id=response['MerchantRequestID'],
                phone_number=f"+254{phone_number}",
                amount=amount,
                status='pending'
            )
            
            messages.success(
                request,
                f"✅ {plan.capitalize()} subscription started! "
                "Please complete the M-Pesa payment on your phone."
            )
            
            return redirect('storefront:subscription_manage', slug=store.slug)
            
        except Exception as e:
            logger.error(f"Payment initiation failed: {str(e)}")
            
            # Subscription created but payment failed
            subscription.status = 'past_due'
            subscription.save()
            
            messages.warning(
                request,
                f"Subscription created but payment failed: {str(e)}. "
                "Please try the payment again from your subscription management page."
            )
            
            return redirect('storefront:subscription_manage', slug=store.slug)

@login_required
def subscription_payment_options(request, slug):
    """
    Payment options after selecting a plan or starting trial
    """
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    
    # Get subscription data from session
    sub_data = request.session.get('subscription_data', {})
    
    # If no session data, check if user has active trial
    if not sub_data or sub_data.get('store_slug') != slug:
        subscription = Subscription.objects.filter(
            store=store,
            status='trialing'
        ).order_by('-created_at').first()
        
        if subscription and subscription.trial_ends_at and timezone.now() < subscription.trial_ends_at:
            # User is in active trial
            sub_data = {
                'store_slug': slug,
                'plan': subscription.plan,
                'phone_number': subscription.mpesa_phone.replace('+254', ''),
                'amount': float(subscription.amount),
                'via_trial': True,
                'subscription_id': subscription.id,
            }
            request.session['subscription_data'] = sub_data
        else:
            messages.error(request, "Please select a plan first.")
            return redirect('storefront:subscription_plan_select', slug=slug)
    
    plan = sub_data['plan']
    phone_number = sub_data['phone_number']
    amount = sub_data['amount']
    via_trial = sub_data.get('via_trial', False)
    subscription_id = sub_data.get('subscription_id')
    
    # Get subscription if exists
    subscription = None
    if subscription_id:
        subscription = Subscription.objects.filter(id=subscription_id, store=store).first()
    elif via_trial:
        subscription = Subscription.objects.filter(
            store=store,
            status='trialing'
        ).order_by('-created_at').first()
    
    # Get plan details
    plan_names = {
        'basic': 'Basic',
        'premium': 'Premium',
        'enterprise': 'Enterprise',
    }
    
    # Calculate trial info if applicable
    trial_info = None
    if subscription and subscription.status == 'trialing' and subscription.trial_ends_at:
        remaining_days = (subscription.trial_ends_at - timezone.now()).days
        trial_info = {
            'remaining_days': max(0, remaining_days),
            'ends_at': subscription.trial_ends_at,
            'progress_percentage': min(100, ((7 - remaining_days) / 7) * 100) if remaining_days >= 0 else 100,
        }
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'pay_now':
            # Initiate immediate payment
            try:
                mpesa = MpesaGateway()
                
                # Get or create subscription
                if not subscription:
                    subscription = Subscription.objects.create(
                        store=store,
                        plan=plan,
                        status='trialing',
                        amount=amount,
                        trial_ends_at=timezone.now() + timedelta(days=7),
                        mpesa_phone=f"+254{phone_number}",
                        metadata={'plan_selected': plan}
                    )
                
                response = mpesa.initiate_stk_push(
                    phone=f"+254{phone_number}",
                    amount=float(amount),
                    account_reference=f"SUB-{store.id}-{plan.upper()}"
                )
                
                # Create payment record
                MpesaPayment.objects.create(
                    subscription=subscription,
                    checkout_request_id=response['CheckoutRequestID'],
                    merchant_request_id=response['MerchantRequestID'],
                    phone_number=f"+254{phone_number}",
                    amount=amount,
                    status='pending'
                )
                
                # Update subscription to active (payment pending)
                subscription.status = 'active' if not via_trial else 'trialing'
                subscription.save()
                
                # Clear session data
                if 'subscription_data' in request.session:
                    del request.session['subscription_data']
                
                messages.success(
                    request,
                    f"Payment initiated for {plan_names.get(plan, 'Premium')} plan. "
                    "Please complete the M-Pesa payment on your phone."
                )
                
                return redirect('storefront:subscription_manage', slug=slug)
                
            except Exception as e:
                logger.error(f"Payment initiation failed: {str(e)}")
                messages.error(request, f"Payment initiation failed: {str(e)}")
        
        elif action == 'continue_trial':
            # Clear session and continue with trial
            if 'subscription_data' in request.session:
                del request.session['subscription_data']
            
            messages.info(
                request,
                f"Enjoy your {plan_names.get(plan, 'Premium')} trial! "
                "You can subscribe anytime before the trial ends."
            )
            
            return redirect('storefront:seller_dashboard')
        
        elif action == 'skip_for_now':
            # User wants to skip payment for now (continue trial if exists)
            if 'subscription_data' in request.session:
                del request.session['subscription_data']
            
            if via_trial and subscription:
                messages.info(
                    request,
                    f"Your {plan_names.get(plan, 'Premium')} trial is active. "
                    "You have {trial_info['remaining_days']} days remaining."
                )
            else:
                messages.info(request, "You can subscribe anytime from your dashboard.")
            
            return redirect('storefront:seller_dashboard')
    
    context = {
        'store': store,
        'plan': plan,
        'plan_name': plan_names.get(plan, 'Premium'),
        'phone_number': phone_number,
        'amount': amount,
        'formatted_amount': f"KSh {amount:,}",
        'via_trial': via_trial,
        'subscription': subscription,
        'trial_info': trial_info,
        'is_in_trial': via_trial and subscription and subscription.status == 'trialing',
    }
    
    # Use different template based on trial status
    if via_trial:
        template = 'storefront/subscription_trial_payment_options.html'
    else:
        template = 'storefront/subscription_immediate_payment.html'
    
    return render(request, template, context)

@login_required
def subscription_change_plan(request, slug):
    """
    Change subscription plan (upgrade/downgrade)
    """
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    subscription = Subscription.objects.filter(
        store=store,
        status__in=['active', 'trialing']
    ).order_by('-created_at').first()
    
    if not subscription:
        messages.error(request, "No active subscription found.")
        return redirect('storefront:subscription_plan_select', slug=slug)
    
    # Plan details
    plan_details = {
        'basic': {
            'name': 'Basic',
            'price': 999,
            'current': subscription.plan == 'basic',
            'can_change': subscription.plan != 'basic',
        },
        'premium': {
            'name': 'Premium',
            'price': 1999,
            'current': subscription.plan == 'premium',
            'can_change': subscription.plan != 'premium',
        },
        'enterprise': {
            'name': 'Enterprise',
            'price': 4999,
            'current': subscription.plan == 'enterprise',
            'can_change': subscription.plan != 'enterprise',
        }
    }
    
    if request.method == 'POST':
        plan = request.POST.get('plan')
        
        if not plan or plan not in plan_details:
            messages.error(request, "Invalid plan selected.")
            return redirect('storefront:subscription_change_plan', slug=slug)
        
        if plan == subscription.plan:
            messages.info(request, f"You are already on the {plan.capitalize()} plan.")
            return redirect('storefront:subscription_manage', slug=slug)
        
        # Check if this is a downgrade
        is_downgrade = False
        plan_order = ['basic', 'premium', 'enterprise']
        if plan_order.index(plan) < plan_order.index(subscription.plan):
            is_downgrade = True
        
        # Handle plan change
        if is_downgrade:
            # Downgrade takes effect at next billing cycle
            subscription.metadata['pending_downgrade'] = {
                'new_plan': plan,
                'requested_at': timezone.now().isoformat(),
                'effective_date': subscription.current_period_end.isoformat() if subscription.current_period_end else None,
            }
            messages.info(
                request,
                f"Your plan will be downgraded to {plan.capitalize()} "
                f"at the end of your current billing period."
            )
        else:
            # Upgrade takes effect immediately
            old_plan = subscription.plan
            subscription.plan = plan
            subscription.amount = plan_details[plan]['price']
            
            # Calculate prorated amount if needed
            if subscription.status == 'active' and subscription.current_period_end:
                days_used = (timezone.now() - subscription.started_at).days
                total_days = (subscription.current_period_end - subscription.started_at).days
                if total_days > 0:
                    prorated_amount = (plan_details[plan]['price'] - plan_details[old_plan]['price']) * (days_used / total_days)
                    subscription.metadata['upgrade_fee'] = {
                        'prorated_amount': prorated_amount,
                        'old_plan': old_plan,
                        'new_plan': plan,
                        'upgraded_at': timezone.now().isoformat(),
                    }
            
            messages.success(
                request,
                f"Your plan has been upgraded to {plan.capitalize()}! "
                f"The new rate will apply immediately."
            )
        
        subscription.save()
        return redirect('storefront:subscription_manage', slug=slug)
    
    context = {
        'store': store,
        'subscription': subscription,
        'plan_details': plan_details,
        'current_plan': subscription.plan,
    }
    
    return render(request, 'storefront/subscription_change_plan.html', context)

@login_required
def subscription_renew(request, slug):
    """
    Renew expired or canceled subscription
    """
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    
    # Get expired/canceled subscription
    subscription = Subscription.objects.filter(
        store=store,
        status__in=['canceled', 'past_due']
    ).order_by('-created_at').first()
    
    if not subscription:
        messages.error(request, "No subscription found to renew.")
        return redirect('storefront:subscription_plan_select', slug=slug)
    
    # Plan details
    plan_details = {
        'basic': {'price': 999, 'name': 'Basic'},
        'premium': {'price': 1999, 'name': 'Premium'},
        'enterprise': {'price': 4999, 'name': 'Enterprise'},
    }
    
    if request.method == 'POST':
        upgrade_form = UpgradeForm(request.POST)
        
        if upgrade_form.is_valid():
            phone_number = upgrade_form.cleaned_data['phone_number']
            
            # Update subscription
            subscription.status = 'active'
            subscription.current_period_end = timezone.now() + timedelta(days=30)
            subscription.mpesa_phone = f"+254{phone_number}"
            subscription.metadata['renewed_at'] = timezone.now().isoformat()
            subscription.save()
            
            # Enable premium features
            store.is_premium = True
            store.save()
            
            # Initiate payment
            try:
                mpesa = MpesaGateway()
                
                response = mpesa.initiate_stk_push(
                    phone=f"+254{phone_number}",
                    amount=float(subscription.amount),
                    account_reference=f"RENEW-{store.id}-{subscription.plan.upper()}"
                )
                
                # Create payment record
                MpesaPayment.objects.create(
                    subscription=subscription,
                    checkout_request_id=response['CheckoutRequestID'],
                    merchant_request_id=response['MerchantRequestID'],
                    phone_number=f"+254{phone_number}",
                    amount=subscription.amount,
                    status='pending'
                )
                
                messages.success(
                    request,
                    f"Subscription renewed! Please complete the M-Pesa payment."
                )
                
                return redirect('storefront:subscription_manage', slug=slug)
                
            except Exception as e:
                logger.error(f"Payment initiation failed: {str(e)}")
                messages.error(request, f"Payment initiation failed: {str(e)}")
        
        else:
            messages.error(request, "Please correct the errors below.")
    
    else:
        # Pre-fill with last used phone number
        initial = {}
        if subscription.mpesa_phone:
            phone = subscription.mpesa_phone.replace('+254', '')
            initial['phone_number'] = phone
        
        upgrade_form = UpgradeForm(initial=initial)
    
    context = {
        'store': store,
        'subscription': subscription,
        'plan_name': plan_details.get(subscription.plan, {}).get('name', subscription.plan.capitalize()),
        'amount': subscription.amount,
        'form': upgrade_form,
        'formatted_amount': f"KSh {subscription.amount:,}",
    }
    
    return render(request, 'storefront/subscription_renew.html', context)

# Add to views_subscription.py
@login_required
def subscription_manage_streamlined(request, slug):
    """
    Enhanced subscription management view showing all states
    """
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    
    # Get comprehensive subscription state
    state = SubscriptionStateManager.get_user_subscription_state(request.user, store)
    subscription = state['subscription']
    
    if not subscription:
        messages.info(request, "No subscription found. Upgrade to unlock premium features.")
        return redirect('storefront:subscription_plan_select', slug=slug)
    
    # Get action required
    action_required = SubscriptionStateManager.get_subscription_action_required(subscription)
    
    # Get recent payments
    recent_payments = subscription.payments.order_by('-created_at')[:5]
    
    # Calculate trial info if applicable
    trial_info = None
    if subscription.status == 'trialing' and subscription.trial_ends_at:
        remaining_days = (subscription.trial_ends_at - timezone.now()).days
        trial_info = {
            'remaining_days': max(0, remaining_days),
            'ends_at': subscription.trial_ends_at,
            'progress_percentage': min(100, ((7 - remaining_days) / 7) * 100) if remaining_days >= 0 else 100,
            'is_expired': remaining_days < 0,
        }
    
    # Get feature access based on plan
    features = {
        'basic': [
            {'name': 'Featured Placement', 'enabled': True, 'icon': 'bi-star'},
            {'name': 'Basic Analytics', 'enabled': True, 'icon': 'bi-graph-up'},
            {'name': 'Store Customization', 'enabled': True, 'icon': 'bi-palette'},
            {'name': 'Up to 50 Products', 'enabled': True, 'icon': 'bi-box'},
            {'name': 'Email Support', 'enabled': True, 'icon': 'bi-envelope'},
            {'name': 'Bulk Operations', 'enabled': False, 'icon': 'bi-upload'},
            {'name': 'Advanced Analytics', 'enabled': False, 'icon': 'bi-graph-up-arrow'},
            {'name': 'Product Bundles', 'enabled': False, 'icon': 'bi-boxes'},
        ],
        'premium': [
            {'name': 'Featured Placement', 'enabled': True, 'icon': 'bi-star'},
            {'name': 'Advanced Analytics', 'enabled': True, 'icon': 'bi-graph-up-arrow'},
            {'name': 'Bulk Operations', 'enabled': True, 'icon': 'bi-upload'},
            {'name': 'Inventory Management', 'enabled': True, 'icon': 'bi-clipboard-check'},
            {'name': 'Product Bundles', 'enabled': True, 'icon': 'bi-boxes'},
            {'name': 'Up to 200 Products', 'enabled': True, 'icon': 'bi-box'},
            {'name': 'Priority Support', 'enabled': True, 'icon': 'bi-headset'},
            {'name': 'API Access', 'enabled': False, 'icon': 'bi-plug'},
        ],
        'enterprise': [
            {'name': 'All Premium Features', 'enabled': True, 'icon': 'bi-check-all'},
            {'name': 'API Access', 'enabled': True, 'icon': 'bi-plug'},
            {'name': 'Custom Domain', 'enabled': True, 'icon': 'bi-globe'},
            {'name': 'Unlimited Products', 'enabled': True, 'icon': 'bi-infinity'},
            {'name': 'Custom Integrations', 'enabled': True, 'icon': 'bi-puzzle'},
            {'name': 'White-label Options', 'enabled': True, 'icon': 'bi-badge-ad'},
            {'name': 'Dedicated Support', 'enabled': True, 'icon': 'bi-person-badge'},
            {'name': 'SLA Guarantee', 'enabled': True, 'icon': 'bi-shield-check'},
        ]
    }
    
    # Determine available actions
    available_actions = []
    
    if subscription.status == 'active':
        available_actions.extend([
            {'name': 'change_plan', 'label': 'Change Plan', 'url': f'/dashboard/store/{slug}/subscription/change-plan/', 'class': 'btn-primary'},
            {'name': 'cancel', 'label': 'Cancel', 'url': f'/dashboard/store/{slug}/subscription/cancel/', 'class': 'btn-outline-danger'},
        ])
    
    elif subscription.status == 'trialing':
        if trial_info and not trial_info['is_expired']:
            available_actions.extend([
                {'name': 'subscribe_now', 'label': 'Subscribe Now', 'url': f'/dashboard/store/{slug}/subscription/payment-options/', 'class': 'btn-primary'},
                {'name': 'change_plan', 'label': 'Change Plan', 'url': f'/dashboard/store/{slug}/subscription/change-plan/', 'class': 'btn-outline-primary'},
            ])
        else:
            available_actions.extend([
                {'name': 'renew', 'label': 'Renew Subscription', 'url': f'/dashboard/store/{slug}/subscription/renew/', 'class': 'btn-warning'},
            ])
    
    elif subscription.status in ['past_due', 'canceled']:
        available_actions.extend([
            {'name': 'renew', 'label': 'Renew Now', 'url': f'/dashboard/store/{slug}/subscription/renew/', 'class': 'btn-warning'},
            {'name': 'new_subscription', 'label': 'New Subscription', 'url': f'/dashboard/store/{slug}/subscription/plans/', 'class': 'btn-primary'},
        ])
    
    context = {
        'store': store,
        'subscription': subscription,
        'recent_payments': recent_payments,
        'trial_info': trial_info,
        'features': features.get(subscription.plan, []),
        'is_trialing': subscription.status == 'trialing',
        'is_active': subscription.status == 'active',
        'is_expired': subscription.status in ['past_due', 'canceled'],
        'can_upgrade': subscription.plan != 'enterprise',
        'can_downgrade': subscription.plan != 'basic',
        'available_actions': available_actions,
        'action_required': action_required,
        'subscription_state': state,
    }
    
    # Use different template based on state
    if action_required == 'trial_expired':
        template = 'storefront/subscription_trial_expired.html'
    elif action_required == 'past_due':
        template = 'storefront/subscription_past_due.html'
    elif action_required == 'renew':
        template = 'storefront/subscription_needs_renewal.html'
    else:
        template = 'storefront/subscription_manage_streamlined.html'
    
    return render(request, template, context)