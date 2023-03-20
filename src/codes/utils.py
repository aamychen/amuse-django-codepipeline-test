from random import shuffle
from codes.models import ISRC


def generate_isrc():
    n = list(range(0, 99999))
    shuffle(n)
    for i in n:
        ISRC.objects.create(code='SE5BU17%05d' % i)
