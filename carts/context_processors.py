from .models import Cart, CartItem
from .views import _cart_id

def counter(request):
    cart_count = 0
    if 'admin' in request.path:
        return {}

    try:
        if request.user.is_authenticated:
            # Query CartItem directly for the logged-in user
            cart_items = CartItem.objects.filter(user=request.user)
        else:
            # Find the specific cart using the session cart_id
            # Using .get() will trigger Cart.DoesNotExist if not found
            cart = Cart.objects.get(cart_id=_cart_id(request))
            cart_items = CartItem.objects.filter(cart=cart)

        for cart_item in cart_items:
            cart_count += cart_item.quantity 

    except Cart.DoesNotExist:
        cart_count = 0

    return {'cart_count': cart_count}
