from django.core.management.base import BaseCommand
from django.utils import timezone
from storefront.models import Subscription, MpesaPayment
from storefront.mpesa import MpesaGateway
from datetime import timedelta

class Command(BaseCommand):
    help = 'Process subscription renewals and trial expirations'

    def handle(self, *args, **options):
        self.process_trial_expirations()
        self.process_renewals()
        self.handle_past_due_subscriptions()

    def process_trial_expirations(self):
        """Process expired trials that haven't converted to paid subscriptions"""
        expired_trials = Subscription.objects.filter(
            status='trialing',
            trial_ends_at__lte=timezone.now()
        )

        for subscription in expired_trials:
            # Check if there's a successful payment
            has_payment = MpesaPayment.objects.filter(
                subscription=subscription,
                status='completed'
            ).exists()

            if not has_payment:
                # No payment made during trial - deactivate
                subscription.status = 'cancelled'
                subscription.save()

                # Lock stores for the owner except the first created store
                try:
                    owner = subscription.store.owner
                    from storefront.models import Store
                    from listings.models import Listing

                    owner_stores = Store.objects.filter(owner=owner).order_by('created_at')
                    first = owner_stores.first()
                    # Deactivate all other stores and their listings
                    for s in owner_stores:
                        if first and s.id == first.id:
                            # Ensure the first store remains active but not premium
                            s.is_premium = False
                            s.is_active = True
                            s.save()
                            continue
                        s.is_premium = False
                        s.is_active = False
                        s.save()
                        # Disable all listings for this store
                        Listing.objects.filter(store=s).update(is_active=False)
                except Exception as e:
                    print(f"Error locking stores after trial expiry: {e}")
            else:
                # Payment received - convert to active
                subscription.status = 'active'
                subscription.next_billing_date = timezone.now() + timedelta(days=30)
            
            subscription.save()

    def process_renewals(self):
        """Process subscription renewals"""
        due_for_renewal = Subscription.objects.filter(
            status='active',
            next_billing_date__lte=timezone.now()
        )

        mpesa = MpesaGateway()

        for subscription in due_for_renewal:
            # Get last successful payment to get phone number
            last_payment = subscription.payments.filter(status='completed').order_by('-transaction_date').first()
            
            if last_payment:
                try:
                    # Initiate renewal payment
                    phone_norm = mpesa._normalize_phone(last_payment.phone_number)
                    response = mpesa.initiate_stk_push(
                        phone=phone_norm,
                        amount=999,
                        account_reference=f"Store-{subscription.store.id}-Renewal"
                    )

                    # Create new payment record
                    MpesaPayment.objects.create(
                        subscription=subscription,
                        checkout_request_id=response['CheckoutRequestID'],
                        merchant_request_id=response['MerchantRequestID'],
                        phone_number=phone_norm,
                        amount=999,
                        status='pending'
                    )

                except Exception as e:
                    # Mark as past due if payment initiation fails
                    subscription.status = 'past_due'
                    subscription.save()
                    print(f"Failed to initiate renewal for subscription {subscription.id}: {str(e)}")

    def handle_past_due_subscriptions(self):
        """Handle subscriptions that are past due"""
        grace_period = timezone.now() - timedelta(days=7)  # 7 day grace period
        past_due_subs = Subscription.objects.filter(
            status='past_due',
            next_billing_date__lte=grace_period
        )

        for subscription in past_due_subs:
            # After grace period, cancel subscription and remove premium status
            subscription.status = 'cancelled'
            subscription.cancelled_at = timezone.now()
            subscription.save()

            store = subscription.store
            store.is_premium = False
            store.save()