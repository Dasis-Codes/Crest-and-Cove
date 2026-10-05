from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.contrib import messages

from store.models import Product, Variation
from .models import Cart, CartItem

from django.contrib.auth.decorators import login_required


# Create your views here.
def _cart_id(request):
    cart = request.session.session_key
    if not cart:
        request.session.create()
        cart = request.session.session_key
    return cart

def add_to_cart(request, product_id):
    current_user = request.user
    product = get_object_or_404(Product, id=product_id)
    product_variation = []

    if request.method == 'POST':
        for key, value in request.POST.items():
            try:
                variation = Variation.objects.get(
                    product=product,
                    variation_category__iexact=key,
                    variation_value__iexact=value,
                )
                product_variation.append(variation)
            except Variation.DoesNotExist:
                continue

    cart, _ = Cart.objects.get_or_create(cart_id=_cart_id(request))
    if current_user.is_authenticated:
        cart_items = CartItem.objects.filter(product=product).filter(
            Q(user=current_user) | Q(cart=cart, user__isnull=True)
        )
    else:
        cart_items = CartItem.objects.filter(
            product=product,
            cart=cart,
            user__isnull=True,
        )
    selected_variation_ids = {variation.id for variation in product_variation}
    cart_item = None

    for item in cart_items:
        existing_variation_ids = set(item.variations.values_list('id', flat=True))
        if existing_variation_ids == selected_variation_ids:
            cart_item = item
            break

    if product.stock <= 0:
        messages.error(request, f'Sorry, {product.product_name} is out of stock.')
        return redirect('cart')

    product.stock -= 1
    product.save(update_fields=['stock'])

    if cart_item is not None:
        cart_item.quantity += 1
        update_fields = ['quantity']
        if current_user.is_authenticated and cart_item.user_id is None:
            cart_item.user = current_user
            update_fields.append('user')
        cart_item.save(update_fields=update_fields)
    else:
        cart_item = CartItem.objects.create(
            product=product,
            quantity=1,
            cart=cart,
            user=current_user if current_user.is_authenticated else None,
        )
        cart_item.variations.set(product_variation)

    return redirect('cart')


def remove_from_cart(request, product_id, item_id):
    cart = Cart.objects.filter(cart_id=_cart_id(request)).first()
    product = get_object_or_404(Product, id=product_id)
    if cart is None and not request.user.is_authenticated:
        return redirect('cart')

    if request.user.is_authenticated:
        item_filter = Q(user=request.user)
        if cart is not None:
            item_filter |= Q(cart=cart)
    else:
        item_filter = Q(cart=cart)
    cart_item = CartItem.objects.filter(item_filter, product=product, pk=item_id).first()

    if cart_item is None:
        return redirect('cart')

    if cart_item.quantity > 1:
        cart_item.quantity -= 1
        cart_item.save()
    else:
        cart_item.delete()

    # Restore 1 item back to stock
    product.stock += 1
    product.save(update_fields=['stock'])

    return redirect('cart')

def remove_cart_item(request, product_id, item_id):
    cart = Cart.objects.filter(cart_id=_cart_id(request)).first()
    product = get_object_or_404(Product, id=product_id)
    if cart is None and not request.user.is_authenticated:
        return redirect('cart')

    if request.user.is_authenticated:
        item_filter = Q(user=request.user)
        if cart is not None:
            item_filter |= Q(cart=cart)
    else:
        item_filter = Q(cart=cart)
    
    cart_item = CartItem.objects.filter(item_filter, product=product, pk=item_id).first()
    if cart_item:
        qty_to_restore = cart_item.quantity
        cart_item.delete()
        # Restore quantity back to stock
        product.stock += qty_to_restore
        product.save(update_fields=['stock'])

    return redirect('cart')


def cart(request, total=0, quantity=0, cart_items=None, tax=0, grand_total=0):
    try:
        cart = Cart.objects.get(cart_id=_cart_id(request))
        if request.user.is_authenticated:
            cart_items = CartItem.objects.filter(user = request.user, is_active=True).order_by('-quantity')
        else:
            cart_items = CartItem.objects.filter(cart = cart, is_active=True).order_by('-quantity')
        for cart_item in cart_items:
            total += cart_item.product.price * cart_item.quantity
            quantity += cart_item.quantity

        tax = (1.4 * total)/100
        grand_total = total + tax

    except Cart.DoesNotExist:
        pass 

    context = {
        'total': total, 
        'quantity': quantity,
        'cart_items': cart_items,
        'tax': tax,
        'grand_total': grand_total
    }

    return render(request, 'store/cart.html', context)

@login_required(login_url='login')
def checkout(request, total=0, quantity=0, cart_items=None):
    cart_items = CartItem.objects.filter(
        user=request.user,
        is_active=True,
    ).order_by('-quantity')

    for cart_item in cart_items:
        total += cart_item.product.price * cart_item.quantity
        quantity += cart_item.quantity

    tax = (1.4 * total) / 100
    grand_total = total + tax
    
    context = {
            'total': total, 
            'quantity': quantity,
            'cart_items': cart_items,
            'tax': tax,
            'grand_total': grand_total
        }
    return render(request, 'store/checkout.html', context)