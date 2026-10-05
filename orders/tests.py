import hashlib
import hmac
import json
from unittest.mock import patch

from django.test import Client, TestCase
from django.test import override_settings
from django.urls import reverse

from accounts.models import Account
from carts.models import CartItem
from category.models import Category
from store.models import Product, Variation
from .models import Payment


class PlaceOrderTests(TestCase):
	def setUp(self):
		self.user = Account.objects.create_user(
			first_name='Order',
			last_name='Customer',
			username='order-customer',
			email='order@example.com',
			phone_no='1234567890',
			password='test-password',
		)
		category = Category.objects.create(
			category_name='Order Category',
			slug='order-category',
		)
		product = Product.objects.create(
			product_name='Order Product',
			slug='order-product',
			price=10,
			images='order-product.jpg',
			stock=5,
			category=category,
		)
		variation = Variation.objects.create(
			product=product,
			variation_category='size',
			variation_value='medium',
		)
		cart_item = CartItem.objects.create(
			user=self.user,
			product=product,
			quantity=1,
		)
		cart_item.variations.add(variation)
		self.client.force_login(self.user)
		self.checkout_data = {
			'first_name': 'Order',
			'last_name': 'Customer',
			'email': 'order@example.com',
			'phone': '1234567890',
			'address_line_1': '1 Test Street',
			'address_line_2': '',
			'city': 'Test City',
			'state': 'Test State',
			'country': 'Test Country',
		}

	def test_valid_submission_saves_order_for_signed_in_user(self):
		response = self.client.post(reverse('place_order'), self.checkout_data, follow=True)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'was placed successfully')
		order = self.user.order_set.get()
		self.assertTrue(order.order_number)
		self.assertEqual(order.user, self.user)
		self.assertContains(response, 'Name:</b> Order Customer')
		self.assertContains(response, 'Size: Medium')
		self.assertContains(response, 'Card Number: 5555 5555 5555 4444')
		self.assertNotContains(response, 'no product will be delivered')
		self.assertEqual(response.request['PATH_INFO'], reverse('payments', args=[order.id]))

	def test_cod_payment_page_replaces_test_note_with_demo_notice(self):
		order = self.create_order()
		self.client.post(reverse('place_cod_order', args=[order.id]))

		response = self.client.get(reverse('payments', args=[order.id]))

		self.assertContains(response, 'Thanks for buying from us!')
		self.assertContains(response, 'No payment was collected')
		self.assertContains(response, 'no product will be delivered')
		self.assertNotContains(response, 'Card Number: 5555 5555 5555 4444')

	def test_completed_safepay_page_replaces_test_note_with_demo_notice(self):
		order = self.create_order()
		payment = Payment.objects.create(
			user=self.user,
			payment_id='track_completed',
			payment_method='Safepay',
			amount_paid=f'{order.order_total:.2f}',
			status='Completed',
		)
		order.payment = payment
		order.payment_method = 'Safepay'
		order.is_ordered = True
		order.save(update_fields=['payment', 'payment_method', 'is_ordered'])

		response = self.client.get(reverse('payments', args=[order.id]))

		self.assertContains(response, 'Thanks for buying from us!')
		self.assertContains(response, 'Safepay payment was made in sandbox mode')
		self.assertContains(response, 'no product will be delivered')
		self.assertNotContains(response, 'Card Number: 5555 5555 5555 4444')

	def test_payment_review_uses_saved_order_product_price_for_subtotal(self):
		order = self.create_order()
		order_product = order.orderproduct_set.get()
		order_product.product.price = 99
		order_product.product.save(update_fields=['price'])

		response = self.client.get(reverse('payments', args=[order.id]))

		self.assertContains(response, '$10.00')
		self.assertContains(response, '$10.00 each')

	def test_invalid_submission_shows_validation_errors(self):
		response = self.client.post(reverse('place_order'), {}, follow=True)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'first_name')
		self.assertFalse(self.user.order_set.exists())

	def test_cash_on_delivery_payment_method_is_saved(self):
		order = self.create_order()

		response = self.client.post(reverse('place_cod_order', args=[order.id]))

		order.refresh_from_db()
		self.assertRedirects(response, reverse('payments', args=[order.id]))
		self.assertEqual(order.payment_method, 'Cash on Delivery')
		self.assertIsNotNone(order.payment)
		self.assertEqual(order.payment.payment_method, 'Cash on Delivery')
		self.assertEqual(order.payment.amount_paid, f'{order.order_total:.2f}')
		self.assertEqual(order.payment.status, 'Pending')
		self.assertEqual(
			Payment.objects.filter(payment_id=f'COD-{order.order_number}').count(),
			1,
		)

	def test_payments_page_uses_linked_method_for_older_order(self):
		order = self.create_order()
		payment = Payment.objects.create(
			user=self.user,
			payment_id='track_legacy',
			payment_method='Safepay',
			amount_paid=f'{order.order_total:.2f}',
			status='Completed',
		)
		order.payment = payment
		order.is_ordered = True
		order.save(update_fields=['payment', 'is_ordered'])

		response = self.client.get(reverse('payments', args=[order.id]))

		self.assertContains(response, 'Safepay')
		self.assertNotContains(response, 'Not Selected')
		self.assertContains(response, '(Paid)')

	def test_cash_on_delivery_finalizes_order_items_and_only_clears_order_cart_rows(self):
		order = self.create_order()
		order_product = order.orderproduct_set.get()
		purchased_cart_item_id = order_product.cart_item_id
		new_cart_item = CartItem.objects.create(
			user=self.user,
			product=order_product.product,
			quantity=1,
		)

		response = self.client.post(reverse('place_cod_order', args=[order.id]))

		order.refresh_from_db()
		order_product.refresh_from_db()
		self.assertRedirects(response, reverse('payments', args=[order.id]))
		self.assertEqual(order.payment_method, 'Cash on Delivery')
		self.assertTrue(order.is_ordered)
		self.assertEqual(order.status, 'Accepted')
		self.assertTrue(order_product.ordered)
		self.assertFalse(CartItem.objects.filter(id=purchased_cart_item_id).exists())
		self.assertTrue(CartItem.objects.filter(id=new_cart_item.id).exists())

	@override_settings(
		SAFEPAY_PUBLIC_KEY='sec_test',
		SAFEPAY_SECRET_KEY='test-v1-secret',
		SAFEPAY_ENVIRONMENT='sandbox',
		SAFEPAY_CURRENCY='USD',
	)
	@patch('orders.views.requests.post')
	def test_start_payment_creates_safepay_checkout(self, mock_post):
		mock_post.return_value.json.return_value = {'data': {'token': 'track_test'}}
		order = self.create_order()

		response = self.client.post(reverse('start_safepay_payment', args=[order.id]))

		self.assertEqual(response.status_code, 302)
		self.assertTrue(response.url.startswith('https://sandbox.api.getsafepay.com/checkout/pay?'))
		self.assertIn('beacon=track_test', response.url)
		self.assertIn('webhooks=true', response.url)
		self.assertEqual(mock_post.call_args.kwargs['json'], {
			'amount': 10.14,
			'client': 'sec_test',
			'currency': 'USD',
			'environment': 'sandbox',
		})
		order.refresh_from_db()
		self.assertEqual(order.payment.status, 'Pending')
		self.assertEqual(order.payment.payment_id, 'track_test')
		self.assertEqual(order.payment_method, 'Safepay')

	@override_settings(SAFEPAY_SECRET_KEY='test-v1-secret')
	def test_valid_safepay_signature_marks_order_paid(self):
		order = self.create_order()
		payment = Payment.objects.create(
			user=self.user,
			payment_id='track_test',
			payment_method='Safepay',
			amount_paid=str(order.order_total),
			status='Pending',
		)
		order.payment = payment
		order.save(update_fields=['payment'])
		new_cart_item = CartItem.objects.create(
			user=self.user,
			product=order.orderproduct_set.get().product,
			quantity=2,
		)
		signature = hmac.new(
			b'test-v1-secret', b'track_test', hashlib.sha256
		).hexdigest()

		response = self.client.get(
			reverse('safepay_success', args=[order.id]),
			{'tracker': 'track_test', 'sig': signature},
		)

		order.refresh_from_db()
		payment.refresh_from_db()
		self.assertRedirects(response, reverse('payment_result', args=[order.id]))
		self.assertTrue(order.is_ordered)
		self.assertEqual(payment.status, 'Completed')
		self.assertEqual(payment.payment_id, 'track_test')
		self.assertTrue(order.orderproduct_set.get().ordered)
		result = self.client.get(reverse('payment_result', args=[order.id]))
		self.assertContains(result, 'Payment successful')
		self.assertQuerySetEqual(
			CartItem.objects.filter(user=self.user, is_active=True),
			[new_cart_item],
		)

	@override_settings(SAFEPAY_SECRET_KEY='test-v1-secret')
	def test_valid_safepay_post_signature_marks_order_paid(self):
		order = self.create_order()
		payment = Payment.objects.create(
			user=self.user,
			payment_id='track_test',
			payment_method='Safepay',
			amount_paid=str(order.order_total),
			status='Pending',
		)
		order.payment = payment
		order.save(update_fields=['payment'])
		signature = hmac.new(
			b'test-v1-secret', b'track_test', hashlib.sha256
		).hexdigest()

		csrf_client = Client(enforce_csrf_checks=True)
		csrf_client.force_login(self.user)
		response = csrf_client.post(
			reverse('safepay_success', args=[order.id]),
			{'tracker': 'track_test', 'sig': signature},
		)

		order.refresh_from_db()
		payment.refresh_from_db()
		self.assertRedirects(response, reverse('payment_result', args=[order.id]))
		self.assertTrue(order.is_ordered)
		self.assertEqual(payment.status, 'Completed')
		result = self.client.get(reverse('payment_result', args=[order.id]))
		self.assertContains(result, 'Payment successful')

	@override_settings(SAFEPAY_SECRET_KEY='test-v1-secret')
	def test_valid_safepay_json_post_marks_order_paid(self):
		order = self.create_order()
		payment = Payment.objects.create(
			user=self.user,
			payment_id='track_test',
			payment_method='Safepay',
			amount_paid=str(order.order_total),
			status='Pending',
		)
		order.payment = payment
		order.save(update_fields=['payment'])
		signature = hmac.new(
			b'test-v1-secret', b'track_test', hashlib.sha256
		).hexdigest()

		response = self.client.post(
			reverse('safepay_success', args=[order.id]),
			data=json.dumps({'tracker': 'track_test', 'sig': signature}),
			content_type='application/json',
		)

		order.refresh_from_db()
		payment.refresh_from_db()
		self.assertRedirects(response, reverse('payment_result', args=[order.id]))
		self.assertTrue(order.is_ordered)
		self.assertEqual(payment.status, 'Completed')
		result = self.client.get(reverse('payment_result', args=[order.id]))
		self.assertContains(result, 'Payment successful')

	@override_settings(SAFEPAY_SECRET_KEY='test-v1-secret')
	def test_invalid_safepay_signature_does_not_mark_order_paid(self):
		order = self.create_order()
		payment = Payment.objects.create(
			user=self.user,
			payment_id='beacon_test',
			payment_method='Safepay',
			amount_paid=str(order.order_total),
			status='Pending',
		)
		order.payment = payment
		order.save(update_fields=['payment'])

		self.client.get(
			reverse('safepay_success', args=[order.id]),
			{'tracker': 'track_test', 'sig': 'invalid'},
		)

		order.refresh_from_db()
		payment.refresh_from_db()
		self.assertFalse(order.is_ordered)
		self.assertEqual(payment.status, 'Pending')
		result = self.client.get(reverse('payment_result', args=[order.id]))
		self.assertContains(result, 'Payment status pending')

	def test_payment_result_status_endpoint_reflects_completion(self):
		order = self.create_order()
		payment = Payment.objects.create(
			user=self.user,
			payment_id='track_test',
			payment_method='Safepay',
			amount_paid=f'{order.order_total:.2f}',
			status='Pending',
		)
		order.payment = payment
		order.save(update_fields=['payment'])
		status_url = reverse('payment_result_status', args=[order.id])

		self.assertEqual(self.client.get(status_url).json()['status'], 'pending')

		payment.status = 'Completed'
		payment.save(update_fields=['status'])
		order.is_ordered = True
		order.save(update_fields=['is_ordered'])

		self.assertEqual(self.client.get(status_url).json()['status'], 'succeeded')

	def test_safepay_cancel_marks_payment_cancelled(self):
		order = self.create_order()
		payment = Payment.objects.create(
			user=self.user,
			payment_id='track_test',
			payment_method='Safepay',
			amount_paid=str(order.order_total),
			status='Pending',
		)
		order.payment = payment
		order.save(update_fields=['payment'])

		response = self.client.get(reverse('safepay_cancel', args=[order.id]))

		payment.refresh_from_db()
		self.assertRedirects(response, reverse('payment_result', args=[order.id]))
		self.assertEqual(payment.status, 'Cancelled')
		result = self.client.get(reverse('payment_result', args=[order.id]))
		self.assertContains(result, 'Payment cancelled')

	@override_settings(
		SAFEPAY_PUBLIC_KEY='sec_test',
		SAFEPAY_WEBHOOK_SECRET='webhook-test-secret',
		SAFEPAY_CURRENCY='USD',
	)
	def test_valid_paid_webhook_completes_matching_order(self):
		order = self.create_order()
		payment = Payment.objects.create(
			user=self.user,
			payment_id='beacon_test',
			payment_method='Safepay',
			amount_paid=f'{order.order_total:.2f}',
			status='Pending',
		)
		order.payment = payment
		order.save(update_fields=['payment'])

		response = self.post_paid_webhook(order)

		order.refresh_from_db()
		payment.refresh_from_db()
		self.assertEqual(response.status_code, 200)
		self.assertTrue(order.is_ordered)
		self.assertEqual(payment.status, 'Completed')
		self.assertEqual(payment.payment_id, 'track_webhook')
		self.assertTrue(order.orderproduct_set.get().ordered)
		self.assertContains(
			self.client.get(reverse('payment_result', args=[order.id])),
			'Payment successful',
		)

	@override_settings(
		SAFEPAY_PUBLIC_KEY='sec_test',
		SAFEPAY_WEBHOOK_SECRET='webhook-test-secret',
		SAFEPAY_CURRENCY='USD',
	)
	def test_paid_webhook_replay_is_idempotent(self):
		order = self.create_order()
		payment = Payment.objects.create(
			user=self.user,
			payment_id='beacon_test',
			payment_method='Safepay',
			amount_paid=f'{order.order_total:.2f}',
			status='Pending',
		)
		order.payment = payment
		order.save(update_fields=['payment'])

		first_response = self.post_paid_webhook(order)
		second_response = self.post_paid_webhook(order)

		order.refresh_from_db()
		payment.refresh_from_db()
		self.assertEqual(first_response.status_code, 200)
		self.assertEqual(second_response.status_code, 200)
		self.assertTrue(order.is_ordered)
		self.assertEqual(payment.status, 'Completed')

	@override_settings(
		SAFEPAY_PUBLIC_KEY='sec_test',
		SAFEPAY_WEBHOOK_SECRET='webhook-test-secret',
		SAFEPAY_CURRENCY='USD',
	)
	def test_invalid_paid_webhook_does_not_complete_order(self):
		order = self.create_order()
		payment = Payment.objects.create(
			user=self.user,
			payment_id='beacon_test',
			payment_method='Safepay',
			amount_paid=f'{order.order_total:.2f}',
			status='Pending',
		)
		order.payment = payment
		order.save(update_fields=['payment'])

		response = self.post_paid_webhook(order, signing_secret='wrong-secret')

		order.refresh_from_db()
		payment.refresh_from_db()
		self.assertEqual(response.status_code, 403)
		self.assertFalse(order.is_ordered)
		self.assertEqual(payment.status, 'Pending')

	@override_settings(
		SAFEPAY_PUBLIC_KEY='sec_test',
		SAFEPAY_WEBHOOK_SECRET='webhook-test-secret',
		SAFEPAY_CURRENCY='USD',
	)
	def test_paid_webhook_amount_mismatch_does_not_complete_order(self):
		order = self.create_order()
		payment = Payment.objects.create(
			user=self.user,
			payment_id='beacon_test',
			payment_method='Safepay',
			amount_paid=f'{order.order_total:.2f}',
			status='Pending',
		)
		order.payment = payment
		order.save(update_fields=['payment'])

		response = self.post_paid_webhook(order, amount='999.99')

		order.refresh_from_db()
		payment.refresh_from_db()
		self.assertEqual(response.status_code, 200)
		self.assertFalse(order.is_ordered)
		self.assertEqual(payment.status, 'Pending')

	@override_settings(
		SAFEPAY_PUBLIC_KEY='sec_test',
		SAFEPAY_WEBHOOK_SECRET='webhook-test-secret',
		SAFEPAY_CURRENCY='USD',
	)
	def test_paid_webhook_converted_settlement_currency_completes_order(self):
		order = self.create_order()
		payment = Payment.objects.create(
			user=self.user,
			payment_id='beacon_test',
			payment_method='Safepay',
			amount_paid=f'{order.order_total:.2f}',
			status='Pending',
		)
		order.payment = payment
		order.save(update_fields=['payment'])

		response = self.post_paid_webhook(
			order,
			amount='69576.87',
			currency='PKR',
		)

		order.refresh_from_db()
		payment.refresh_from_db()
		self.assertEqual(response.status_code, 200)
		self.assertTrue(order.is_ordered)
		self.assertEqual(payment.status, 'Completed')

	def post_paid_webhook(
		self,
		order,
		amount=None,
		currency='USD',
		signing_secret='webhook-test-secret',
	):
		data = {
			'amount': amount or f'{order.payment.amount_paid}',
			'currency': currency,
			'merchant_api_key': 'sec_test',
			'payment_metadata': [
				{'meta_key': 'order_id', 'meta_value': order.order_number},
			],
			'state': 'PAID',
			'tracker': 'track_webhook',
		}
		payload = json.dumps({'data': data}, separators=(',', ':'))
		signature = hmac.new(
			signing_secret.encode('utf-8'),
			json.dumps(data, separators=(',', ':')).encode('utf-8'),
			hashlib.sha512,
		).hexdigest()
		return self.client.post(
			reverse('safepay_webhook'),
			data=payload,
			content_type='application/json',
			HTTP_X_SFPY_SIGNATURE=signature,
		)

	def create_order(self):
		response = self.client.post(reverse('place_order'), self.checkout_data)
		self.assertEqual(response.status_code, 302)
		return self.user.order_set.latest('id')

# Create your tests here.
