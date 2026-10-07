import hashlib
import hmac
import json
import logging
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.db import transaction
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseServerError,
    JsonResponse,
)
from store.models import Product
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from carts.models import CartItem
from .forms import OrderForm
from .models import Order, OrderProduct, Payment
import datetime

# Create your views here.
logger = logging.getLogger(__name__)

def _complete_paid_order(order, payment, tracker):
    with transaction.atomic():
        locked_order = Order.objects.select_for_update().get(pk=order.pk)
        locked_payment = Payment.objects.select_for_update().get(pk=payment.pk)
        if locked_order.is_ordered and locked_payment.status == 'Completed':
            return

        locked_payment.payment_id = tracker
        locked_payment.status = 'Completed'
        locked_payment.save(update_fields=['payment_id', 'status'])
        locked_order.payment = locked_payment
        locked_order.is_ordered = True
        locked_order.status = 'Accepted'
        locked_order.save(update_fields=['payment', 'is_ordered', 'status', 'updated_at'])

        order_products = locked_order.orderproduct_set.select_related('product').all()
        cart_item_ids = list(
            order_products.exclude(cart_item__isnull=True)
            .values_list('cart_item_id', flat=True)
        )
        order_products.update(payment=locked_payment, ordered=True)
        CartItem.objects.filter(
            id__in=cart_item_ids,
            user=locked_order.user,
        ).delete()


@csrf_exempt
@require_POST
def safepay_webhook(request):
    webhook_secret = getattr(settings, 'SAFEPAY_WEBHOOK_SECRET', '')
    if not webhook_secret:
        logger.error('Safepay webhook rejected: webhook secret is not configured')
        return HttpResponseServerError()

    try:
        body = json.loads(request.body or b'{}')
        data = body.get('data')
        if not isinstance(data, dict):
            logger.warning('Safepay webhook rejected: data field missing or not an object')
            return HttpResponseBadRequest()
    except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
        logger.warning('Safepay webhook rejected: request body is not valid JSON')
        return HttpResponseBadRequest()

    signature = request.headers.get('X-SFPY-SIGNATURE', '')
    signed_payload = json.dumps(data, separators=(',', ':')).encode('utf-8')
    expected_signature = hmac.new(
        webhook_secret.encode('utf-8'),
        msg=signed_payload,
        digestmod=hashlib.sha512,
    ).hexdigest()
    if not signature or not hmac.compare_digest(signature, expected_signature):
        logger.warning('Safepay webhook rejected: signature invalid')
        return HttpResponseForbidden()

    api_key = getattr(settings, 'SAFEPAY_PUBLIC_KEY', '')
    nested_notification = data.get('notification')
    notification = nested_notification if isinstance(nested_notification, dict) else data
    merchant_key = (
        data.get('client_id')
        or notification.get('merchant_api_key')
        or notification.get('client_id')
    )
    if not api_key or merchant_key != api_key:
        logger.warning('Safepay webhook rejected: merchant key mismatch')
        return HttpResponseForbidden()

    if str(notification.get('state', '')).upper() != 'PAID':
        logger.info('Safepay webhook ignored: state is not PAID')
        return HttpResponse(status=200)

    metadata = notification.get('metadata')
    order_number = metadata.get('order_id') if isinstance(metadata, dict) else None
    if not order_number:
        payment_metadata = notification.get('payment_metadata')
        if isinstance(payment_metadata, list):
            order_number = next((
                item.get('meta_value')
                for item in payment_metadata
                if isinstance(item, dict) and item.get('meta_key') == 'order_id'
            ), None)
    tracker = notification.get('tracker')
    if not order_number or not tracker:
        logger.warning(
            'Safepay paid webhook missing order reference or tracker: '
            'order_reference_present=%s tracker_present=%s',
            bool(order_number),
            bool(tracker),
        )
        return HttpResponseBadRequest()

    order = Order.objects.select_related('payment').filter(
        order_number=str(order_number)
    ).first()
    if order is None or order.payment is None:
        logger.warning('Safepay paid webhook has no matching local order')
        return HttpResponse(status=200)

    try:
        received_amount = Decimal(str(notification['amount'])).quantize(Decimal('0.01'))
        expected_amount = Decimal(order.payment.amount_paid).quantize(Decimal('0.01'))
    except (KeyError, ValueError, TypeError, ArithmeticError):
        logger.warning('Safepay webhook amount invalid or missing: order_id=%s', order.id)
        return HttpResponseBadRequest()
    if received_amount <= 0:
        logger.warning('Safepay webhook amount is not positive: order_id=%s', order.id)
        return HttpResponseBadRequest()

    currency = getattr(settings, 'SAFEPAY_CURRENCY', 'USD')
    received_currency = str(notification.get('currency', '')).upper()
    if not received_currency:
        logger.warning('Safepay webhook currency missing: order_id=%s', order.id)
        return HttpResponseBadRequest()
    if received_currency == str(currency).upper() and received_amount != expected_amount:
        logger.warning('Safepay webhook amount mismatch: order_id=%s', order.id)
        return HttpResponse(status=200)
    if received_currency != str(currency).upper():
        logger.info(
            'Safepay webhook uses a different settlement currency: order_id=%s event_currency=%s',
            order.id,
            received_currency,
        )

    _complete_paid_order(order, order.payment, tracker)
    logger.info('Safepay webhook completed order_id=%s', order.id)
    return HttpResponse(status=200)


@login_required(login_url='login')
def payments(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order_products = order.orderproduct_set.select_related('product', 'variation')
    payment_method = order.payment_method or (
        order.payment.payment_method if order.payment_id else ''
    )
    total = order.order_total - order.tax
    context = {
        'order': order,
        'order_products': order_products,
        'payment_method': payment_method,
        'total': total,
        'tax': order.tax,
        'grand_total': order.order_total,
    }
    return render(request, 'orders/payments.html', context)


@login_required(login_url='login')
def payment_result(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'orders/payment_result.html', {
        'order': order,
        'result_status': _payment_result_status(order),
    })


def _payment_result_status(order):
    payment = order.payment
    if order.is_ordered and payment is not None and payment.status == 'Completed':
        return 'succeeded'
    if payment is not None and payment.status == 'Cancelled':
        return 'cancelled'
    return 'pending'


@login_required(login_url='login')
def payment_result_status(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    response = JsonResponse({'status': _payment_result_status(order)})
    response['Cache-Control'] = 'no-store'
    return response


@login_required(login_url='login')
@require_POST
def start_safepay_payment(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    if order.is_ordered:
        messages.info(request, 'This order has already been paid.')
        return redirect('payments', order_id=order.id)

    api_key = getattr(settings, 'SAFEPAY_PUBLIC_KEY', '')
    v1_secret = getattr(settings, 'SAFEPAY_SECRET_KEY', '')
    environment = getattr(settings, 'SAFEPAY_ENVIRONMENT', 'sandbox')
    currency = getattr(settings, 'SAFEPAY_CURRENCY', 'USD')
    api_hosts = {
        'sandbox': 'https://sandbox.api.getsafepay.com',
        'production': 'https://api.getsafepay.com',
    }
    checkout_hosts = {
        'sandbox': 'https://sandbox.api.getsafepay.com/checkout/pay',
        'production': 'https://getsafepay.com/checkout/pay',
    }
    if not api_key or not v1_secret or environment not in api_hosts:
        messages.error(request, 'Safepay is not configured correctly.')
        return redirect('payments', order_id=order.id)

    amount = float(
        Decimal(str(order.order_total)).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
    )
    try:
        response = requests.post(
            f"{api_hosts[environment]}/order/v1/init",
            json={
                'amount': amount,
                'client': api_key,
                'currency': currency,
                'environment': environment,
            },
            headers={'Content-type': 'application/json', 'Accept': 'text/plain'},
            timeout=15,
        )
        response.raise_for_status()
        beacon_token = response.json()['data']['token']
        payment = Payment.objects.create(
            user=request.user,
            payment_id=beacon_token,
            payment_method='Safepay',
            amount_paid=f'{amount:.2f}',
            status='Pending',
        )
        order.payment = payment
        order.payment_method = 'Safepay'
        order.save(update_fields=['payment', 'payment_method'])
    except (requests.RequestException, ValueError, KeyError, TypeError):
        messages.error(request, 'Safepay could not start this payment. Please try again.')
        return redirect('payments', order_id=order.id)

    checkout_params = urlencode({
        'beacon': payment.payment_id,
        'cancel_url': request.build_absolute_uri(
            reverse('safepay_cancel', args=[order.id])
        ),
        'env': environment,
        'order_id': order.order_number,
        'redirect_url': request.build_absolute_uri(
            reverse('safepay_success', args=[order.id])
        ),
        'source': 'custom',
        'webhooks': 'true',
    })
    return redirect(f'{checkout_hosts[environment]}?{checkout_params}')


@require_http_methods(['GET', 'POST'])
@csrf_exempt
def safepay_success(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    payment = order.payment
    callback_data = request.POST
    if request.content_type == 'application/json':
        try:
            callback_data = json.loads(request.body or b'{}')
        except (json.JSONDecodeError, UnicodeDecodeError):
            callback_data = {}

    tracker = callback_data.get('tracker') or request.GET.get('tracker', '')
    signature = callback_data.get('sig') or request.GET.get('sig', '')
    secret = getattr(settings, 'SAFEPAY_SECRET_KEY', '')
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        msg=tracker.encode('utf-8'),
        digestmod=hashlib.sha256,
    ).hexdigest() if secret else ''
    signature_valid = bool(
        signature and secret and hmac.compare_digest(signature, expected_signature)
    )
    tracker_matches = bool(payment and tracker and tracker == payment.payment_id)
    logger.warning(
        'Safepay callback received: order_id=%s method=%s content_type=%s '
        'tracker_present=%s signature_present=%s',
        order.id,
        request.method,
        request.content_type,
        bool(tracker),
        bool(signature),
    )

    if order.is_ordered and payment is not None and payment.status == 'Completed':
        messages.info(request, 'This order has already been paid.')
        return redirect('payment_result', order_id=order.id)
        # print('Order already paid, redirecting to payments page.')

    if (
        payment is None
        or payment.status != 'Pending'
        or not tracker
        or not secret
        or not tracker_matches
        or not signature_valid
    ):
        logger.warning(
            'Safepay callback rejected: order_id=%s payment_exists=%s '
            'payment_pending=%s tracker_matches=%s signature_valid=%s',
            order.id,
            payment is not None,
            payment is not None and payment.status == 'Pending',
            tracker_matches,
            signature_valid,
        )
        messages.error(request, 'Safepay could not verify this payment.')
        return redirect('payment_result', order_id=order.id)
        # print('Safepay could not verify this payment, redirecting to payments page.')

    _complete_paid_order(order, payment, tracker)

    logger.warning('Safepay payment verified: order_id=%s', order.id)
    messages.success(request, 'Your Safepay payment was verified.')
    return redirect('payment_result', order_id=order.id)
    # print('Safepay payment verified, redirecting to payments page.')


def safepay_cancel(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if order.payment is not None and order.payment.status == 'Pending':
        order.payment.status = 'Cancelled'
        order.payment.save(update_fields=['status'])
    messages.info(request, 'Payment was cancelled. You can try again when ready.')
    return redirect('payment_result', order_id=order.id)
    # print('Payment was cancelled, redirecting to payments page.')

@login_required(login_url='login')
def place_order(request, total=0, quantity=0):
    current_user = request.user
    cart_items = CartItem.objects.filter(user=current_user, is_active=True).order_by('-quantity')
    cart_count = cart_items.count()
    if cart_count <= 0:
        return redirect('store')

    tax = 0
    grand_total = 0
    for cart_item in cart_items:
        quantity += cart_item.quantity
        total += cart_item.product.price * cart_item.quantity

    tax = (1.4 * total)/100
    grand_total = total + tax

    if request.method == 'POST':
        form = OrderForm(request.POST)
        current_user = request.user
        if form.is_valid():
            order = form.save(commit=False)
            order.user = current_user
            order.tax = tax
            order.order_total = grand_total
            order.ip = request.META.get('REMOTE_ADDR')
            order.save()


            #GENERATING ORDER NUMBERS
            yr = int(datetime.date.today().strftime("%Y"))
            mt = int(datetime.date.today().strftime("%m"))
            dt = int(datetime.date.today().strftime("%d"))
            d = datetime.date(yr, mt, dt)
            current_date = d.strftime("%d%m%Y")
            order.order_number = current_date + str(order.id)
            order.save(update_fields=['order_number'])

            for cart_item in cart_items:
                variations = list(cart_item.variations.all())
                variation_values = {
                    variation.variation_category.lower(): variation.variation_value
                    for variation in variations
                }
                OrderProduct.objects.create(
                    order=order,
                    cart_item=cart_item,
                    user=current_user,
                    product=cart_item.product,
                    variation=variations[0] if variations else None,
                    color=variation_values.get('color', ''),
                    size=variation_values.get('size', ''),
                    quantity=cart_item.quantity,
                    product_price=cart_item.product.price,
                )

            messages.success(request, f'Order {order.order_number} was placed successfully.')
            return redirect('payments', order_id=order.id)

        else:
            for field, errors in form.errors.items():
                messages.error(request, f'{field}: {", ".join(errors)}')
            return redirect('checkout')

    return redirect('checkout')


# views.py example
def place_cod_order(request, order_id): # or order_id via POST
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    if request.method == 'POST':
        if order.payment_id and order.payment.payment_method != 'Cash on Delivery':
            messages.error(request, 'This order already has another payment attempt.')
            return redirect('payments', order_id=order.id)

        with transaction.atomic():
            amount_paid = Decimal(str(order.order_total)).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            payment, _ = Payment.objects.get_or_create(
                payment_id=f'COD-{order.order_number}',
                defaults={
                    'user': order.user,
                    'payment_method': 'Cash on Delivery',
                    'amount_paid': f'{amount_paid:.2f}',
                    'status': 'Pending',
                },
            )
            order.payment_method = 'Cash on Delivery'
            order.payment = payment
            order.is_ordered = True
            order.status = 'Accepted'
            order.save(update_fields=[
                'payment', 'payment_method', 'is_ordered', 'status', 'updated_at'
            ])

            order_products = order.orderproduct_set.select_related('product').all()
            for op in order_products:
                product = Product.objects.select_for_update().get(pk=op.product.pk)
                if product.stock >= op.quantity:
                    product.stock -= op.quantity
                    product.save(update_fields=['stock'])

            cart_item_ids = list(
                order_products.exclude(cart_item__isnull=True)
                .values_list('cart_item_id', flat=True)
            )
            order_products.update(payment=payment, ordered=True)
            CartItem.objects.filter(
                id__in=cart_item_ids,
                user=order.user,
            ).delete()

        # messages.success(request, f'Order {order.order_number} placed with Cash on Delivery.')
        return redirect('payments', order_id=order.id)


@login_required(login_url='login')
def invoice(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order_products = order.orderproduct_set.select_related('product', 'variation').all()
    subtotal = order.order_total - order.tax

    context = {
        'order': order,
        'order_products': order_products,
        'subtotal': subtotal,
    }
    return render(request, 'orders/invoice.html', context)
