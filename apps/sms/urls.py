from django.urls import path
from . import views

app_name = 'sms'

urlpatterns = [
    path('accounts/<str:owner_type>/<str:owner_id>/', views.SmsAccountDetail.as_view(), name='sms_account_detail'),
    path('accounts/<str:owner_type>/<str:owner_id>/topup/', views.SmsAccountTopup.as_view(), name='sms_account_topup'),
    path('deliveries/', views.SmsDeliveryList.as_view(), name='sms_delivery_list'),
]
