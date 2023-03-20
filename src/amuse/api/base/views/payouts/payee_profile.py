from rest_framework import status
from rest_framework.decorators import permission_classes
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from payouts.models import Payee, TransferMethod
from amuse.vendor.hyperwallet.client_factory import HyperWalletEmbeddedClientFactory
from amuse.mixins import LogMixin


@permission_classes([IsAuthenticated])
class PayeeSummaryView(LogMixin, GenericAPIView):
    def _filter_deactivated(self, payee, hw_data):
        deactivated_trms = TransferMethod.objects.filter(payee=payee, active=False)
        trms_count_hw = hw_data.get('count')
        trms_list = hw_data.get('data')
        if not deactivated_trms:
            return hw_data
        if trms_count_hw == 1:
            return hw_data
        for trm in deactivated_trms:
            for hw_trm in trms_list:
                if hw_trm['token'] == trm.external_id:
                    trms_list.remove(hw_trm)
        return {'count': 1, 'limit': hw_data.get('limit'), 'data': trms_list}

    def _get_summary_from_hw(self, payee):
        data = {}
        user_country = payee.user.country
        hw_client = HyperWalletEmbeddedClientFactory().create(country_code=user_country)
        user_data = hw_client.getUser(userToken=payee.external_id)
        trms = hw_client.listTransferMethods(userToken=payee.external_id)
        data['user_profile'] = user_data.asDict()
        data['trms'] = self._filter_deactivated(payee, trms.asDict())
        return data

    def get(self, request):
        user = self.request.user
        try:
            payee = Payee.objects.get(user=user)
            data = self._get_summary_from_hw(payee=payee)
            return Response(
                {
                    'is_success': True,
                    "data": data,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {'is_success': False, "data": None, "reason": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )
