from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.conf import settings
from django.db.models import Sum
from django.utils import timezone
from decimal import Decimal

from storefront.models import Store
from listings.mpesa_utils import MpesaGateway

from .models import AffiliateProfile, AffiliateClick, AffiliateAttribution, AffiliateCommission, AffiliateSubscriptionCommission, AffiliatePayout


def _affiliate_totals(profile):
    order_commissions = AffiliateCommission.objects.filter(affiliate=profile)
    subscription_commissions = AffiliateSubscriptionCommission.objects.filter(affiliate=profile)

    total = (order_commissions.aggregate(total=Sum('amount')).get('total') or 0) + (
        subscription_commissions.aggregate(total=Sum('amount')).get('total') or 0
    )
    pending = (order_commissions.filter(status='pending').aggregate(total=Sum('amount')).get('total') or 0) + (
        subscription_commissions.filter(status='pending').aggregate(total=Sum('amount')).get('total') or 0
    )
    approved = (order_commissions.filter(status='approved').aggregate(total=Sum('amount')).get('total') or 0) + (
        subscription_commissions.filter(status='approved').aggregate(total=Sum('amount')).get('total') or 0
    )
    paid = (order_commissions.filter(status='paid').aggregate(total=Sum('amount')).get('total') or 0) + (
        subscription_commissions.filter(status='paid').aggregate(total=Sum('amount')).get('total') or 0
    )

    return {
        'total': total,
        'pending': pending,
        'approved': approved,
        'paid': paid,
    }


@login_required
def affiliate_dashboard(request):
    profile, _ = AffiliateProfile.objects.get_or_create(user=request.user)
    link_base = getattr(settings, 'SITE_URL', '').rstrip('/')
    affiliate_link = f"{link_base}/?{getattr(settings, 'AFFILIATE_QUERY_PARAM', 'aid')}={profile.code}" if link_base else f"/?aid={profile.code}"

    clicks = AffiliateClick.objects.filter(affiliate=profile)
    attributions = AffiliateAttribution.objects.filter(affiliate=profile)
    commissions = AffiliateCommission.objects.filter(affiliate=profile)
    subscription_commissions = AffiliateSubscriptionCommission.objects.filter(affiliate=profile)
    totals = _affiliate_totals(profile)

    stats = {
        'clicks': clicks.count(),
        'referrals': attributions.count(),
        'pending_commissions': commissions.filter(status='pending').count() + subscription_commissions.filter(status='pending').count(),
        'approved_commissions': commissions.filter(status='approved').count() + subscription_commissions.filter(status='approved').count(),
        'paid_commissions': commissions.filter(status='paid').count() + subscription_commissions.filter(status='paid').count(),
        'total_commissions': totals['total'],
        'pending_amount': totals['pending'],
        'paid_amount': totals['paid'],
    }

    recent_commissions = []
    for commission in commissions.select_related('order').order_by('-created_at')[:10]:
        recent_commissions.append({
            'label': f"Order #{commission.order_id}",
            'amount': commission.amount,
            'status': commission.status,
            'created_at': commission.created_at,
            'type': 'order',
        })
    for commission in subscription_commissions.select_related('subscription').order_by('-created_at')[:10]:
        label = f"{commission.get_commission_type_display()} for {commission.subscription.store.name}"
        recent_commissions.append({
            'label': label,
            'amount': commission.amount,
            'status': commission.status,
            'created_at': commission.created_at,
            'type': commission.commission_type,
        })
    recent_commissions = sorted(recent_commissions, key=lambda x: x['created_at'], reverse=True)[:10]

    context = {
        'affiliate_profile': profile,
        'affiliate_link': affiliate_link,
        'stats': stats,
        'recent_commissions': recent_commissions,
    }
    return render(request, 'affiliates/dashboard.html', context)


@login_required
def affiliate_commissions(request):
    profile, _ = AffiliateProfile.objects.get_or_create(user=request.user)
    commissions = AffiliateCommission.objects.filter(affiliate=profile).select_related('order').order_by('-created_at')
    subscription_commissions = AffiliateSubscriptionCommission.objects.filter(affiliate=profile).select_related('subscription').order_by('-created_at')
    payouts = AffiliatePayout.objects.filter(affiliate=profile).order_by('-created_at')[:10]
    totals = _affiliate_totals(profile)
    payout_total = AffiliatePayout.objects.filter(affiliate=profile, status__in=['pending', 'paid']).aggregate(total=Sum('amount')).get('total') or 0
    available_balance = max(Decimal(totals['approved']) - Decimal(payout_total), Decimal('0'))
    is_seller = Store.objects.filter(owner=request.user).exists()
    return render(request, 'affiliates/commissions.html', {
        'affiliate_profile': profile,
        'commissions': commissions,
        'subscription_commissions': subscription_commissions,
        'payouts': payouts,
        'affiliate_available_balance': available_balance,
        'affiliate_min_withdrawal': Decimal('5000'),
        'is_seller': is_seller,
    })


@login_required
def affiliate_request_withdrawal(request):
    if request.method != 'POST':
        return render(request, 'affiliates/commissions.html', {})

    profile, _ = AffiliateProfile.objects.get_or_create(user=request.user)
    totals = _affiliate_totals(profile)
    payout_total = AffiliatePayout.objects.filter(affiliate=profile, status__in=['pending', 'paid']).aggregate(total=Sum('amount')).get('total') or 0
    available_balance = max(Decimal(totals['approved']) - Decimal(payout_total), Decimal('0'))

    try:
        amount = Decimal(request.POST.get('amount', '0'))
    except Exception:
        amount = Decimal('0')

    if amount <= 0 or amount > available_balance:
        return render(request, 'affiliates/commissions.html', {
            'affiliate_profile': profile,
            'commissions': AffiliateCommission.objects.filter(affiliate=profile).select_related('order').order_by('-created_at'),
            'subscription_commissions': AffiliateSubscriptionCommission.objects.filter(affiliate=profile).select_related('subscription').order_by('-created_at'),
            'payouts': AffiliatePayout.objects.filter(affiliate=profile).order_by('-created_at')[:10],
            'affiliate_available_balance': available_balance,
            'affiliate_min_withdrawal': Decimal('5000'),
            'is_seller': Store.objects.filter(owner=request.user).exists(),
            'error_message': 'Invalid withdrawal amount.',
        })

    if amount < Decimal('5000'):
        return render(request, 'affiliates/commissions.html', {
            'affiliate_profile': profile,
            'commissions': AffiliateCommission.objects.filter(affiliate=profile).select_related('order').order_by('-created_at'),
            'subscription_commissions': AffiliateSubscriptionCommission.objects.filter(affiliate=profile).select_related('subscription').order_by('-created_at'),
            'payouts': AffiliatePayout.objects.filter(affiliate=profile).order_by('-created_at')[:10],
            'affiliate_available_balance': available_balance,
            'affiliate_min_withdrawal': Decimal('5000'),
            'is_seller': Store.objects.filter(owner=request.user).exists(),
            'error_message': 'Minimum withdrawal is KSh 5,000.',
        })

    phone = request.POST.get('phone') or ''
    # Sellers can use their verified payout phone
    if not phone:
        store = Store.objects.filter(owner=request.user).first()
        if store and store.payout_verified and store.payout_phone:
            phone = store.payout_phone

    if not phone:
        return render(request, 'affiliates/commissions.html', {
            'affiliate_profile': profile,
            'commissions': AffiliateCommission.objects.filter(affiliate=profile).select_related('order').order_by('-created_at'),
            'subscription_commissions': AffiliateSubscriptionCommission.objects.filter(affiliate=profile).select_related('subscription').order_by('-created_at'),
            'payouts': AffiliatePayout.objects.filter(affiliate=profile).order_by('-created_at')[:10],
            'affiliate_available_balance': available_balance,
            'affiliate_min_withdrawal': Decimal('5000'),
            'is_seller': Store.objects.filter(owner=request.user).exists(),
            'error_message': 'Please provide a valid M-Pesa phone number for withdrawals.',
        })

    gateway = MpesaGateway()
    resp = gateway.initiate_b2c_payout(phone, amount, remarks='Affiliate Withdrawal', occasion=f"AFF-{profile.id}")

    payout = AffiliatePayout.objects.create(
        affiliate=profile,
        amount=amount,
        status='pending',
        phone=phone,
        mpesa_reference=resp.get('originator_conversation_id', ''),
        mpesa_status='processed' if resp.get('simulated') else 'initiated',
        mpesa_response=resp,
        reference=resp.get('originator_conversation_id', '') or resp.get('conversation_id', ''),
    )

    if resp.get('success') and resp.get('simulated'):
        payout.status = 'paid'
        payout.paid_at = timezone.now()
        payout.save(update_fields=['status', 'paid_at'])

    return render(request, 'affiliates/commissions.html', {
        'affiliate_profile': profile,
        'commissions': AffiliateCommission.objects.filter(affiliate=profile).select_related('order').order_by('-created_at'),
        'subscription_commissions': AffiliateSubscriptionCommission.objects.filter(affiliate=profile).select_related('subscription').order_by('-created_at'),
        'payouts': AffiliatePayout.objects.filter(affiliate=profile).order_by('-created_at')[:10],
        'affiliate_available_balance': available_balance,
        'affiliate_min_withdrawal': Decimal('5000'),
        'is_seller': Store.objects.filter(owner=request.user).exists(),
        'success_message': 'Withdrawal request submitted. You will receive M-Pesa confirmation shortly.',
    })


@staff_member_required
def affiliate_admin_dashboard(request):
    stats = {
        'total_affiliates': AffiliateProfile.objects.filter(is_active=True).count(),
        'total_clicks': AffiliateClick.objects.count(),
        'total_referrals': AffiliateAttribution.objects.count(),
        'pending_commissions': (AffiliateCommission.objects.filter(status='pending').aggregate(total=Sum('amount')).get('total') or 0) +
                               (AffiliateSubscriptionCommission.objects.filter(status='pending').aggregate(total=Sum('amount')).get('total') or 0),
        'paid_commissions': (AffiliateCommission.objects.filter(status='paid').aggregate(total=Sum('amount')).get('total') or 0) +
                            (AffiliateSubscriptionCommission.objects.filter(status='paid').aggregate(total=Sum('amount')).get('total') or 0),
    }
    recent_commissions = AffiliateCommission.objects.select_related('affiliate', 'order').order_by('-created_at')[:12]
    recent_payouts = AffiliatePayout.objects.select_related('affiliate').order_by('-created_at')[:8]
    return render(request, 'affiliates/admin_dashboard.html', {
        'stats': stats,
        'recent_commissions': recent_commissions,
        'recent_payouts': recent_payouts,
    })


def affiliate_terms(request):
    return render(request, 'affiliates/terms.html', {})
