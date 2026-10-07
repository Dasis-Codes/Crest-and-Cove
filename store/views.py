from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse

from .models import Product
from category.models import Category
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from carts.views import _cart_id, CartItem
from .forms import ReviewForm
from .models import Product, ReviewRating
from django.contrib import messages
from django.shortcuts import redirect
# Create your views here.
def store(request, category_slug=None):

    categories = None
    products = None

    if category_slug != None:
        categories = get_object_or_404(Category, slug=category_slug)
        products = Product.objects.all().filter(category=categories, is_available=True).order_by( '-added_at')
        paginator = Paginator(products, 6)
        page = request.GET.get('page')
        paged_products = paginator.get_page(page)
        product_count = products.count()
    else:
        products = Product.objects.all().filter(is_available=True).order_by('-added_at')
        paginator = Paginator(products, 6)
        page = request.GET.get('page')
        paged_products = paginator.get_page(page)
        product_count = products.count()

    context = {
        'products': paged_products,
        'product_count': product_count,
        'categories': Category.objects.all(),  # Include all categories in the context
    }
    return render(request, 'store/stores.html', context)

def product_detail(request, category_slug, product_slug):

    single_product = get_object_or_404(
        Product,
        category__slug=category_slug,
        slug=product_slug
    )

    in_cart = CartItem.objects.filter(
        cart__cart_id=_cart_id(request),
        product=single_product
    ).exists()

    

    form = ReviewForm(request.POST)

    if request.method == 'POST':

        if not request.user.is_authenticated:
            messages.error(request, 'You must be logged in to submit a review.')
            return redirect(
                'product_detail',
                category_slug=category_slug,
                product_slug=product_slug
            )

        form = ReviewForm(request.POST)

        if form.is_valid():

            review = form.save(commit=False)

            review.product = single_product
            review.user = request.user

            review.save()

            messages.success(request, 'Thank you! Your review has been submitted.')

            return redirect(
                'product_detail',
                category_slug=category_slug,
                product_slug=product_slug
            )

    else:
        form = ReviewForm()

    reviews = ReviewRating.objects.filter(
        product=single_product,
        status=True
    ).order_by('-date_added')

    context = {
        'single_product': single_product,
        'in_cart': in_cart,
        'form': form,
        'reviews': reviews,
    }

    return render(request, 'store/product_detail.html', context)

def search(request):
    keyword = request.GET.get('keyword', '').strip()
    products = Product.objects.none()

    if keyword:
        products = Product.objects.order_by('-added_at').filter(
            product_name__icontains=keyword,
            is_available=True,
        )

    paginator = Paginator(products, 6)
    paged_products = paginator.get_page(request.GET.get('page'))

    context = {
        'products': paged_products,
        'product_count': products.count(),
        'categories': Category.objects.all(),
        'keyword': keyword,
    }
    return render(request, 'store/stores.html', context)