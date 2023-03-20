from datetime import datetime
from time import time


class ReportingUtils(object):
    @staticmethod
    def get_date_form_string(date_string):
        if date_string is None or date_string == "":
            return datetime.now().date()
        date_object = datetime.strptime(date_string, '%Y-%m-%d')
        return date_object.date()

    @staticmethod
    def get_report_prefix():
        return int(time())

    @staticmethod
    def data_formatter(object, name):
        value = getattr(object, name)
        if isinstance(value, datetime):
            return value.date()
        if name == 'category':
            return object.get_category_display()
        if name == 'platform':
            return object.get_platform_display()
        if name == 'subscription':
            return object.subscription.get_provider_display()
        return value
