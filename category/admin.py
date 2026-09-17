from django.contrib import admin
from category.models import Category


# Register your models here.
class CategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('category_name',)}
    list_display = ('category_name', 'slug', 'date_only')

    @admin.display(description='Date added', ordering='date_added')
    def date_only(self, obj):
        return obj.date_added.date()

admin.site.register(Category, CategoryAdmin)