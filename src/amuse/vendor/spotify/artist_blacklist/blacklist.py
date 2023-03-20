import string


TRANSLATIONS = ''.maketrans(
    'èéüçáóøúíãñî$ë', 'eeucaoouianise'  # Replace what  # Replace with
)

ALLOWED_CHARS = string.ascii_lowercase + string.digits


def lowercase(text):
    return text.lower()


def substitute_chars(text):
    return text.translate(TRANSLATIONS)


def remove_disallowed_chars(text):
    return ''.join([char for char in text if char in ALLOWED_CHARS])


def remove_prefix(prefix):
    index = len(prefix)

    def remove_prefix(text):
        if text.startswith(prefix):
            return text[index:]
        return text

    return remove_prefix


def create_fuzzifier(*filters):
    def fuzzify(text):
        for filter in filters:
            text = filter(text)
        return text

    return fuzzify


fuzzify = create_fuzzifier(
    lowercase, remove_prefix('the '), substitute_chars, remove_disallowed_chars
)
