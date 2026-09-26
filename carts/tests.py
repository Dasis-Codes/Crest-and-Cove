from django.test import TestCase
from django.urls import reverse

from accounts.models import Account
from category.models import Category
from store.models import Product
from .models import Cart, CartItem

# Create your tests here.
class CheckoutCartItemsTests(TestCase):
	def test_checkout_includes_items_from_previous_sessions(self):
		user = Account.objects.create_user(
			first_name='Cart',
			last_name='Customer',
			username='cart-customer',
			email='cart@example.com',
			phone_no='1234567890',
			password='test-password',
		)
		category = Category.objects.create(
			category_name='Test Category',
			slug='test-category',
		)
		older_product = Product.objects.create(
			product_name='Older Item',
			slug='older-item',
			price=10,
			images='older-item.jpg',
			stock=5,
			category=category,
		)
		latest_product = Product.objects.create(
			product_name='Latest Item',
			slug='latest-item',
			price=20,
			images='latest-item.jpg',
			stock=5,
			category=category,
		)
		previous_cart = Cart.objects.create(cart_id='previous-session')

		self.client.force_login(user)
		current_cart = Cart.objects.create(
			cart_id=self.client.session.session_key,
		)
		CartItem.objects.create(
			user=user,
			product=older_product,
			cart=previous_cart,
			quantity=1,
		)
		CartItem.objects.create(
			user=user,
			product=latest_product,
			cart=current_cart,
			quantity=1,
		)

		response = self.client.get(reverse('checkout'))

		self.assertEqual(response.status_code, 200)
		self.assertSetEqual(
			set(response.context['cart_items'].values_list('product__product_name', flat=True)),
			{'Older Item', 'Latest Item'},
		)


class AddToCartTests(TestCase):
	def test_logged_in_plus_increments_item_from_previous_cart(self):
		user = Account.objects.create_user(
			first_name='Cart',
			last_name='Customer',
			username='cart-customer',
			email='cart@example.com',
			phone_no='1234567890',
			password='test-password',
		)
		category = Category.objects.create(
			category_name='Test Category',
			slug='test-category',
		)
		product = Product.objects.create(
			product_name='Cart Item',
			slug='cart-item',
			price=10,
			images='cart-item.jpg',
			stock=5,
			category=category,
		)
		previous_cart = Cart.objects.create(cart_id='previous-session')
		cart_item = CartItem.objects.create(
			user=user,
			product=product,
			cart=previous_cart,
			quantity=2,
		)
		self.client.force_login(user)

		response = self.client.post(reverse('add_to_cart', args=[product.id]))

		self.assertRedirects(response, reverse('cart'))
		self.assertEqual(CartItem.objects.filter(user=user, product=product).count(), 1)
		cart_item.refresh_from_db()
		self.assertEqual(cart_item.quantity, 3)
