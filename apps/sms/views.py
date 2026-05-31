from rest_framework import generics, status
from rest_framework.response import Response
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404
from .models import SmsAccount, SmsDelivery
from .serializers import SmsAccountSerializer, SmsDeliverySerializer
from .services import SmsService


class SmsAccountDetail(generics.RetrieveAPIView):
    serializer_class = SmsAccountSerializer

    def get_object(self):
        owner_type = self.kwargs['owner_type']
        owner_id = self.kwargs['owner_id']
        ct = get_object_or_404(ContentType, model=owner_type)
        return get_object_or_404(SmsAccount, owner_content_type=ct, owner_object_id=owner_id)


class SmsAccountTopup(generics.UpdateAPIView):
    serializer_class = SmsAccountSerializer

    def update(self, request, *args, **kwargs):
        account = self.get_object()
        amount = int(request.data.get('amount', 0))
        # In real world we'd create a topup record and integrate payment gateway.
        account.balance_credits += amount
        account.last_topup_at = timezone.now()
        account.save(update_fields=['balance_credits', 'last_topup_at'])
        return Response(self.get_serializer(account).data)


class SmsDeliveryList(generics.ListAPIView):
    serializer_class = SmsDeliverySerializer

    def get_queryset(self):
        return SmsDelivery.objects.all()
