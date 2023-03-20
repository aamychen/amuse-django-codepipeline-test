from django.forms import MultiWidget, ValidationError, Form
from django.forms.fields import MultiValueField, BooleanField, FileField


class BulkEditWidget(MultiWidget):
    def __init__(self, *args, **kwargs):
        super(BulkEditWidget, self).__init__(*args, **kwargs)
        self.template_name = 'admin/users/bulk_edit/bulk_edit_widget.html'

    def decompress(self, value):
        if value is None:
            return [None, None]
        return [False, value]


class BulkEditField(MultiValueField):
    def __init__(self, field, **kwargs):
        fields = (BooleanField(required=False), field)
        field.widget.attrs['disabled'] = True

        widgets = []
        for field in fields:
            widgets.append(field.widget)
        self.widget = BulkEditWidget(widgets=widgets)

        super().__init__(fields=fields, require_all_fields=False, **kwargs)

    def prepare_value(self, value):
        if type(value) == list and len(value) > 1:
            return value[1]
        return value

    def compress(self, data_list):
        """
        data_list is the array of two elements.
        data_list[0] is Boolean, always.
        If data_list[0] is False, data_list[1] is ignored (the field is not edited).
        Otherwise, data_list[1] represents actual value of the edited field.
        """
        if type(data_list) == list and len(data_list) > 1 and data_list[0] is True:
            return data_list[1]

        return None


class BulkEditForm(Form):
    def bulk_update(self, request, qs):
        if self.is_valid():
            items = qs.all()

            field_names = list(self.cleaned_data.keys())
            if len(field_names) == 0:
                # nothing to update
                return

            for field_name, value in self.cleaned_data.items():
                for instance in items:
                    if hasattr(instance, field_name):
                        setattr(instance, field_name, value)

            qs.model.objects.bulk_update(items, fields=field_names)

    def _should_perform_field_clean(self, field, value):
        """
        BulkEditWidget is cleaned only if the first widget (checkbox) is checked.
        Checked checkbox means that field is edited.
        Otherwise, it is ignored.
        """
        if not isinstance(field.widget, BulkEditWidget):
            return True

        if isinstance(field.widget, BulkEditWidget) and field.disabled is True:
            return False

        if type(value) != list:
            return True

        if len(value) > 0:
            # we are 100% sure that we are dealing with a valid BulkEditWidget value
            return value[0] is True

        return True

    def _clean_fields(self):
        for name, field in self.fields.items():
            # value_from_datadict() gets the data from the data dictionaries.
            # Each widget type knows how to retrieve its own data, because some
            # widgets split data over several HTML fields.
            if field.disabled:
                value = self.get_initial_for_field(field, name)
            else:
                prefix = self.add_prefix(name)
                value = field.widget.value_from_datadict(self.data, self.files, prefix)

            if not self._should_perform_field_clean(field, value):
                # this part is the only difference between
                # _clean_fields() method and super()._clean_fields()
                continue

            try:
                if isinstance(field, FileField):
                    initial = self.get_initial_for_field(field, name)
                    value = field.clean(value, initial)
                else:
                    value = field.clean(value)
                self.cleaned_data[name] = value
                if hasattr(self, 'clean_%s' % name):
                    value = getattr(self, 'clean_%s' % name)()
                    self.cleaned_data[name] = value
            except ValidationError as e:
                self.add_error(name, e)
