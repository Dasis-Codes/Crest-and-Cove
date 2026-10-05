from django.contrib import admin
from .models import Order, OrderProduct, Payment
# Register your models here.

class OrderProductInline(admin.TabularInline):
    model = OrderProduct
    readonly_fields = ('payment', 'user', 'product', 'variation', 'color', 'size', 'quantity', 'product_price', 'ordered')
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
	list_display = ('order_number', 'first_name', 'last_name', 'user', 'order_total', 'status', 'created_at')
	list_filter = ('status', 'created_at')
	search_fields = ('order_number', 'first_name', 'last_name', 'email', 'user__email')
	inlines = [OrderProductInline]


# admin.site.register(OrderProduct)
# admin.site.register(Payment)
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
	list_display = ('payment_id', 'payment_method', 'status', )
	list_filter = ('status', 'payment_method')


