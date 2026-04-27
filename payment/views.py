import stripe
import json
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Payments
from subscription.models import Plan, Subscriptions
from .serializers import PaymentSerializer
from .helper import create_checkout_session

# Create your views here.

class GetPaymentLinkView(APIView):
    
    def get(self, request):
        plan_id = request.query_params.get("plan")
        
        if not plan_id:
            return Response({"error": "Plan ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            plan = Plan.objects.get(id=plan_id)
        except Plan.DoesNotExist:
            return Response({"error": "Plan not found"}, status=status.HTTP_404_NOT_FOUND)


        payment = Payments.objects.create(
            user=request.user,
            plan=plan,
            status='pending'
        )

        try:
            # Payment link or secret data creation
            payment_data = create_checkout_session(
                request, 
                payment=payment,
                price=float(plan.price),
            )

            return Response({
                "status": True,
                "log": payment_data
            })
        except Exception as e:
            # Delete the pending payment if link creation fails to avoid duplicates
            payment.delete()
            return Response({
                "status": False,
                "error": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

class PaymentSuccessView(APIView):
    permission_classes = []
    def get(self, request):
        return Response({"message": "Payment successful! Your subscription is activated."})

class PaymentCancelView(APIView):
    permission_classes = []
    def get(self, request):
        return Response({"message": "Payment cancelled."})




@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(APIView):
    permission_classes = []

    def post(self, request):
        print("!!! Webhook Path Hit Successfully !!!")
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

        print("--- Stripe Webhook Received ---")

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
            print(f"Event Verified: {event['type']}")
        except ValueError as e:
            print(f"Invalid payload: {str(e)}")
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)
        except stripe.error.SignatureVerificationError as e:
            print(f"Invalid signature: {str(e)}")
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)

        if event['type'] in ['checkout.session.completed', 'payment_intent.succeeded', 'invoice.paid']:
            stripe_obj = event['data']['object']

            def safe_metadata(obj):
                """Safely extract metadata from a Stripe object as a plain Python dict."""
                try:
                    raw = obj.to_dict().get('metadata') or {}
                    return raw if isinstance(raw, dict) else {}
                except Exception:
                    pass
                try:
                    raw = getattr(obj, 'metadata', None)
                    if raw is None:
                        return {}
                    if hasattr(raw, '_data'):
                        return dict(raw._data)
                    return {}
                except Exception:
                    return {}

            metadata = safe_metadata(stripe_obj)

            print(f"😂😂😂😂Metadata: {metadata}")

            if not metadata.get('payment'):
                if getattr(stripe_obj, 'invoice', None):
                    try:
                        inv = stripe.Invoice.retrieve(stripe_obj['invoice'])
                        metadata = safe_metadata(inv)
                    except: pass

                if not metadata.get('payment') and getattr(stripe_obj, 'payment_intent', None):
                    try:
                        pi = stripe.PaymentIntent.retrieve(stripe_obj['payment_intent'])
                        metadata = safe_metadata(pi)
                    except: pass

            payment_id = metadata.get('payment')
            transaction_id = getattr(stripe_obj, 'id', None)

            print(f"Processing Event: {event['type']} | Payment: {payment_id}")

            if payment_id:
                try:
                    payment = Payments.objects.get(id=payment_id)
                    print(f"Update Start: Payment {payment.id}")
                    
                    if payment.status == 'paid':
                        print(f"Skipping: Payment {payment.id} already processed.")
                        return HttpResponse(status=status.HTTP_200_OK)

                    payment.status = 'paid'
                    payment.tnxid = transaction_id
                    
                    # --- Multi-step Invoice/Receipt URL Retrieval ---
                    invoice_url = payment.invoice or "" # Keep existing URL if any
                    
                    # If the event object IS an invoice, get the URL directly
                    if getattr(stripe_obj, 'object', None) == 'invoice':
                        invoice_url = getattr(stripe_obj, 'hosted_invoice_url', None) or getattr(stripe_obj, 'invoice_pdf', None) or invoice_url

                    # Only fetch if we don't have a URL yet
                    if not invoice_url:
                        invoice_id = getattr(stripe_obj, 'invoice', None)
                        
                        # 1. Try to fetch from Stripe Invoice
                        if invoice_id:
                            try:
                                print(f"Fetching invoice from Stripe: {invoice_id}")
                                inv = stripe.Invoice.retrieve(invoice_id)
                                invoice_url = getattr(inv, 'hosted_invoice_url', None) or getattr(inv, 'invoice_pdf', None) or invoice_url
                            except Exception as e:
                                print(f"Stripe webhook - Error fetching invoice: {e}")

                        # 2. Fallback: Try to fetch receipt_url from the charge (via PaymentIntent)
                        if not invoice_url:
                            pi_id = getattr(stripe_obj, 'payment_intent', None) or (getattr(stripe_obj, 'id', None) if getattr(stripe_obj, 'object', None) == 'payment_intent' else None)
                            if pi_id:
                                try:
                                    pi = stripe.PaymentIntent.retrieve(pi_id)
                                    charge_id = getattr(pi, 'latest_charge', None)
                                    if charge_id:
                                        charge = stripe.Charge.retrieve(charge_id)
                                        invoice_url = getattr(charge, 'receipt_url', None) or invoice_url
                                        print(f"Fetched Receipt URL from Charge: {invoice_url}")
                                except Exception as e:
                                    print(f"Stripe webhook - Error fetching receipt: {e}")

                        # 3. Last Fallback: Use success_url or placeholder
                        if not invoice_url:
                            invoice_url = getattr(stripe_obj, 'success_url', None) or invoice_url

                    payment.invoice = invoice_url
                    payment.save()
                    
                    # Deactivate existing active subscriptions for this user
                    Subscriptions.objects.filter(user=payment.user, active=True).update(active=False)
                    
                    # Create/Activate new subscription
                    Subscriptions.objects.create(
                        user=payment.user,
                        plan=payment.plan,
                        active=True
                    )
                    print(f"Subscription activated: User {payment.user.email} | Plan {payment.plan.name}")
                    
                except Exception as e:
                    print(f"Database update error: {str(e)}")
            else:
                print(f"Skipping: Metadata missing for {event['type']}. Available metadata: {metadata}")
        else:
            print(f"Ignoring event type: {event['type']}")

        return HttpResponse(status=status.HTTP_200_OK)