from django import forms
from .models import ReviewRating


class ReviewForm(forms.ModelForm):

    class Meta:
        model = ReviewRating
        fields = ['rating', 'comment']

    def clean_rating(self):
        rating = self.cleaned_data['rating']

        if rating < 0.5 or rating > 5:
            raise forms.ValidationError(
                'Rating must be between 0.5 and 5.'
            )

        if rating * 2 != int(rating * 2):
            raise forms.ValidationError(
                'Rating must be in increments of 0.5.'
            )

        return rating