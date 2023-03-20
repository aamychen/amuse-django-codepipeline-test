def is_splitable(input_string):
    if ',' in input_string:
        return True, ','
    if ';' in input_string:
        return True, ';'
    return False, None


def remove_non_digits(input_list):
    return [x for x in input_list if x.strip().isdigit()]


def parse_input_string_to_digits(string):
    striped = string.strip()
    status, separator = is_splitable(striped)
    if not status and striped.isdigit():
        return [striped]
    if status and separator == ',':
        list = striped.split(',')
        return remove_non_digits(list)
    if status and separator == ';':
        list = striped.split(';')
        return remove_non_digits(list)
    return []
