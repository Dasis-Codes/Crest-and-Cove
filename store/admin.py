from django.contrib import admin
from .models import Product

# Register your models here.
class ProductAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('product_name',)}
    list_display = ('product_name', 'price', 'stock', 'category', 'date_only', 'is_available')
    list_editable = ('is_available',)
    list_per_page = 20

    @admin.display(description='MODIFIED AT', ordering='modified_date')
    def date_only(self, obj):
        return obj.modified_date.date()

admin.site.register(Product, ProductAdmin)