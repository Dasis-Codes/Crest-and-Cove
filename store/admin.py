from django.contrib import admin
from .models import Product, Variation, ReviewRating

# Register your models here.
class VariationInline(admin.TabularInline):
    model = Variation
    extra = 1

class ProductAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('product_name',)}
    list_display = ('product_name', 'price', 'stock', 'category', 'date_only', 'is_available')
    list_editable = ('is_available',)
    list_per_page = 20
    inlines = [VariationInline]

    @admin.display(description='MODIFIED AT', ordering='modified_date')
    def date_only(self, obj):
        return obj.modified_date.date()

admin.site.register(Product, ProductAdmin)


class VariationAdmin(admin.ModelAdmin):
    list_display = ('product','variation_category', 'variation_value', 'is_active', 'date_added')
    list_editable = ('is_active',)
    list_filter = ('product','variation_category','variation_value',)

admin.site.register(Variation, VariationAdmin)
admin.site.register(ReviewRating)