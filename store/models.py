from django.db import models
from category.models import Category
from django.urls import reverse
from accounts.models import Account
from django.db.models import Avg


# Create your models here.
# class Product(models.Model):
#     product_name = models.CharField(max_length=200, unique=True)
#     slug = models.SlugField(max_length=200, unique=True)
#     description = models.TextField(max_length=500, blank=True)
#     price = models.IntegerField()
#     images = models.ImageField(upload_to='photos/products')
#     stock = models.IntegerField()
#     is_available = models.BooleanField(default=True)
#     category = models.ForeignKey('category.Category', on_delete=models.CASCADE)
#     added_at = models.DateTimeField(auto_now_add=True)
#     modified_date = models.DateTimeField(auto_now=True)

#     def get_url(self):
#         return reverse('product_detail', args=[self.category.slug, self.slug])


#     def __str__(self):
#         return self.product_name

class Product(models.Model):
    product_name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(max_length=500, blank=True)
    price = models.IntegerField()
    images = models.ImageField(upload_to='photos/products')
    stock = models.IntegerField()
    is_available = models.BooleanField(default=True)
    category = models.ForeignKey('category.Category', on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    def get_url(self):
        return reverse('product_detail', args=[self.category.slug, self.slug])

    @property
    def average_rating(self):
        result = self.reviewrating_set.filter(status=True).aggregate(average=Avg('rating'))
        return result['average'] or 0

    @property
    def average_star_display(self):
        rating = self.average_rating
        full_stars = int(rating)
        half_star = rating - full_stars >= 0.5
        empty_stars = 5 - full_stars - (1 if half_star else 0)

        return {
            'full': range(full_stars),
            'half': range(1 if half_star else 0),
            'empty': range(empty_stars),
        }

    @property
    def review_count(self):
        return self.reviewrating_set.filter(status=True).count()

    def __str__(self):
        return self.product_name

class VariationManager(models.Manager):
    def colors(self):
        return super(VariationManager, self).filter(variation_category='color', is_active=True)
    def sizes(self):
        return super(VariationManager, self).filter(variation_category='size', is_active=True)


variation_category_choices = (
    ('color', 'Color'),
    ('size', 'Size'),
)

class Variation(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variation_category = models.CharField(max_length=100, choices= variation_category_choices)
    variation_value = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    date_added = models.DateTimeField(auto_now_add=True)

    objects = VariationManager()

    def __str__(self):
        return self.variation_value

# class ReviewRating(models.Model):
#     product = models.ForeignKey(Product, on_delete=models.CASCADE)
#     user = models.ForeignKey(Account, on_delete=models.CASCADE)
#     rating = models.FloatField()
#     comment = models.TextField(blank=True)
#     ip = models.CharField(max_length=20, blank=True)
#     status = models.BooleanField(default=True)
#     date_added = models.DateTimeField(auto_now_add=True)

#     @property
#     def star_display(self):
#         full_stars = int(self.rating)
#         half_star = self.rating % 1 == 0.5
#         empty_stars = 5 - full_stars - (1 if half_star else 0)

#         return {
#             'full': range(full_stars),
#             'half': range(1 if half_star else 0),
#             'empty': range(empty_stars),
#         }

#     @property
#     def average_rating(self):
#         result = self.reviewrating_set.filter(
#             status=True
#         ).aggregate(
#             average=Avg('rating')
#         )

#         return result['average'] or 0


#     @property
#     def average_star_display(self):
#         rating = self.average_rating

#         full_stars = int(rating)
#         half_star = rating - full_stars >= 0.5
#         empty_stars = 5 - full_stars - (1 if half_star else 0)

#         return {
#             'full': range(full_stars),
#             'half': range(1 if half_star else 0),
#             'empty': range(empty_stars),
#         }


#     @property
#     def review_count(self):
#         return self.reviewrating_set.filter(status=True).count()

#     def __str__(self):
#         return self.user.username

class ReviewRating(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    user = models.ForeignKey(Account, on_delete=models.CASCADE)
    rating = models.FloatField()
    comment = models.TextField(blank=True)
    ip = models.CharField(max_length=20, blank=True)
    status = models.BooleanField(default=True)
    date_added = models.DateTimeField(auto_now_add=True)

    @property
    def star_display(self):
        full_stars = int(self.rating)
        half_star = self.rating % 1 == 0.5
        empty_stars = 5 - full_stars - (1 if half_star else 0)

        return {
            'full': range(full_stars),
            'half': range(1 if half_star else 0),
            'empty': range(empty_stars),
        }

    def __str__(self):
        return self.user.username