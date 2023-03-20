import json
import logging
from uuid import uuid4
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.timezone import now
from amuse.view_log_base import ViewLogBase

logger = logging.getLogger('api')


def generate_request_id():
    return str(uuid4())


class LogMixin(ViewLogBase):
    def initial(self, request, *args, **kwargs):
        self.request.request_id = generate_request_id()
        self.request.time_initialized = now()
        super(LogMixin, self).initial(request, *args, **kwargs)

    def finalize_response(self, request, response, *args, **kwargs):
        unit_test = kwargs.get("test")
        if unit_test:
            pass
        else:
            response = super(LogMixin, self).finalize_response(
                request, response, *args, **kwargs
            )

        try:
            request_data = {
                'user_id': None if not request.user else request.user.id,
                'version': getattr(request, 'version', '1'),
                'uri': request.path,
                'method': request.method,
                'http_status': response.status_code,
                'user_agent': request.META.get('HTTP_USER_AGENT'),
                'query_params': json.dumps(
                    self.clean_data(request.query_params.dict()), cls=DjangoJSONEncoder
                ),
                'request': json.dumps(
                    self.clean_data(request.data), cls=DjangoJSONEncoder
                ),
                'response': json.dumps(
                    self.clean_data(getattr(response, 'data', None)),
                    cls=DjangoJSONEncoder,
                ),
                'time_initialized': None
                if not hasattr(request, 'time_initialized')
                else self.format_datetime(request.time_initialized),
                'time_finalized': self.format_datetime(now()),
                'headers': json.dumps(
                    self.clean_data(self.collect_headers(request.META)),
                    cls=DjangoJSONEncoder,
                ),
                'request_id': self.request.request_id,
            }
            logger.info(msg="", extra=request_data)
        except Exception as e:
            logging.error('Unable to log current request')
            logging.error(e, exc_info=True)
        finally:
            if unit_test:
                return response, request_data
            return response
