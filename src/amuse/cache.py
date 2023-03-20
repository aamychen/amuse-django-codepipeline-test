from django.core.cache.backends.db import DatabaseCache


class AmuseDatabaseCache(DatabaseCache):
    pickle_protocol = 4
