from django import forms
from .models import ReviewRating

class OrderForm(forms.Form):
    class Meta:
        model = ReviewRating
        fields = ['username','rating', 'comment']