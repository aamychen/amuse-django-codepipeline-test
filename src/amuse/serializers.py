from rest_framework.serializers import CharField, Field, ValidationError


class BitFieldField(Field):
    def __init__(self, flags, **kwargs):
        self.flags = flags
        return super(BitFieldField, self).__init__(**kwargs)

    def to_internal_value(self, obj):
        if not isinstance(obj, dict):
            raise ValidationError(
                'Incorrect type. Expected a dict, but got %s' % type(obj).__name__
            )
        retval = 0
        for bit in [i[1] for i in self.flags if obj.get(i[0]) == True]:
            retval |= bit
        return retval

    def to_representation(self, obj):
        return dict((item[0], bool(item[1] & obj)) for item in self.flags)


class StringMapField(Field):
    def __init__(self, mapping, **kwargs):
        self._mapping = dict(mapping)
        super().__init__(**kwargs)

    def to_internal_value(self, obj):
        if obj not in self._mapping.values():
            raise ValidationError(
                '\'%s\' is not a valid value. Choices are: %s.'
                % (obj, list(self._mapping.keys()))
            )
        return list(self._mapping.keys())[list(self._mapping.values()).index(obj)]

    def to_representation(self, obj):
        if obj not in self._mapping.keys():
            raise ValidationError(
                '\'%s\' is not a valid value. Choices are: %s.'
                % (obj, list(self._mapping.keys()))
            )
        return self._mapping[obj]


class PlaceholderCharField(CharField):
    def __init__(self, placeholder, **kwargs):
        self._placeholder = placeholder
        return super(PlaceholderCharField, self).__init__(**kwargs)

    def to_representation(self, obj):
        return obj or self._placeholder
