from django.urls import path
from . import views

urlpatterns = [
    path('place_order/',views.place_order,name='place_order'),
    path('payments/webhook/', views.safepay_webhook, name='safepay_webhook'),
    path('payments/cod/<int:order_id>/', views.place_cod_order, name='place_cod_order'),
    path('payments/<int:order_id>/', views.payments, name='payments'),
    path('payments/<int:order_id>/result/', views.payment_result, name='payment_result'),
    path('payments/<int:order_id>/result/status/', views.payment_result_status, name='payment_result_status'),
    path('payments/<int:order_id>/start/', views.start_safepay_payment, name='start_safepay_payment'),
    path('payments/<int:order_id>/success/', views.safepay_success, name='safepay_success'),
    path('payments/<int:order_id>/cancel/', views.safepay_cancel, name='safepay_cancel'),
]

