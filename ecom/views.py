from django.shortcuts import render
from store.models import Product
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


def home(request):
    products = Product.objects.all().filter(is_available=True).order_by('added_at')
    paginator = Paginator(products, 8)
    page = request.GET.get('page')
    paged_products = paginator.get_page(page)
    context = {
        'products': paged_products,
    }
    return render(request, 'home.html', context)
