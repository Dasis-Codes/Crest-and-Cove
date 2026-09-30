from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from carts.models import CartItem
from .forms import OrderForm
from .models import Order
import datetime

# Create your views here.

@login_required(login_url='login')
def payments(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    cart_items = CartItem.objects.filter(user=request.user, is_active=True)
    total = order.order_total - order.tax
    context = {
        'order': order,
        'cart_items': cart_items,
        'total': total,
        'tax': order.tax,
        'grand_total': order.order_total,
    }
    return render(request, 'orders/payments.html', context)

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

            messages.success(request, f'Order {order.order_number} was placed successfully.')
            return redirect('payments', order_id=order.id)

        else:
            for field, errors in form.errors.items():
                messages.error(request, f'{field}: {", ".join(errors)}')
            return redirect('checkout')

    return redirect('checkout')


