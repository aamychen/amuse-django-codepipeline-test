from uuid import uuid4


def are_all_equal_to_none(items):
    return items.count(None) == len(items)


def generate_event_id():
    return str(uuid4()).replace('-', '')
