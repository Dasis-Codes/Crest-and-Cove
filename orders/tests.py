from django.test import TestCase
from django.urls import reverse

from accounts.models import Account
from carts.models import CartItem
from category.models import Category
from store.models import Product, Variation


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
		self.assertEqual(response.request['PATH_INFO'], reverse('payments', args=[order.id]))

	def test_invalid_submission_shows_validation_errors(self):
		response = self.client.post(reverse('place_order'), {}, follow=True)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'first_name')
		self.assertFalse(self.user.order_set.exists())

# Create your tests here.
