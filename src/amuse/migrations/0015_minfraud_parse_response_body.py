from django.db import migrations, transaction
import json


# Format:
# {... '[opening sign]': ('[closing sign]', is_recursive), ...}
paired_signs = {
    '(': (')', True),
    '[': (']', True),
    '{': ('}', True),
    '\'': ('\'', False),
    '"': ('"', False),
}
spaces = {' ', '\n', '\r', '\t'}
special_chars = set(
    list(paired_signs.keys())
    + [item[0] for item in paired_signs.values()]
    + list(spaces)
    + [',', '=', ':']
)


def _cast_str(s):
    if s == 'None':
        return None
    if s.isdigit():
        return int(s)
    try:
        val = float(s)
        return val
    except ValueError:
        pass
    return s


def _minfraud_str_to_json(s, start_i, typ):
    start_char = s[start_i]
    start_pair = paired_signs.get(start_char)
    result = None
    if typ == 0:
        result = []
    elif typ == 1:
        result = {}
    curr_i = start_i + 1

    curr_token = ''
    curr_token_str = False
    label = ''

    while curr_i < len(s):
        curr_char = s[curr_i]
        curr_i += 1

        if curr_char in spaces:
            continue

        if curr_char == '=' or curr_char == ':':
            label = curr_token
            curr_token = ''
            curr_token_str = False
            continue

        if curr_char == '(' and s[curr_i - 2] not in special_chars:
            temp_res, curr_i = _minfraud_str_to_json(s, curr_i - 1, 1)
            if typ == 0:
                result.append(temp_res)
            else:
                exist_res = result.get(label)
                result[label] = [exist_res, temp_res] if exist_res else temp_res
            curr_token = ''
            curr_token_str = False
            continue

        if start_pair and curr_char == start_pair[0]:
            if curr_token:
                val = curr_token
                if not curr_token_str:
                    val = _cast_str(curr_token)
                if typ == 0:
                    result.append(val)
                else:
                    exist_res = result.get(label)
                    result[label] = [exist_res, val] if exist_res else val
            break

        if curr_char == ',':
            if curr_token:
                val = curr_token
                if not curr_token_str:
                    val = _cast_str(curr_token)
                if typ == 0:
                    result.append(val)
                else:
                    exist_res = result.get(label)
                    result[label] = [exist_res, val] if exist_res else val
                curr_token = ''
                curr_token_str = False
            continue

        pair = paired_signs.get(curr_char)
        if pair:
            if pair[1]:
                next_typ = 0
                if curr_char == '{':
                    next_typ = 1
                temp_res, curr_i = _minfraud_str_to_json(s, curr_i - 1, next_typ)
                if typ == 0:
                    result.append(temp_res)
                else:
                    exist_res = result.get(label)
                    result[label] = [exist_res, temp_res] if exist_res else temp_res
                curr_token = ''
                curr_token_str = False
            else:
                curr_str = ""
                while curr_i < len(s):
                    curr_char = s[curr_i]
                    if curr_char == pair[0]:
                        curr_i += 1
                        break
                    curr_str += curr_char
                    curr_i += 1
                curr_token = curr_str
                curr_token_str = True
            continue

        curr_token += curr_char

    return result, curr_i


@transaction.atomic
def parse_response_body_to_json(apps, schema_editor):
    MinfraudResult = apps.get_model("amuse", "MinfraudResult")
    for item in MinfraudResult.objects.all():
        if not item.response_body:
            continue

        # Skip service types ('Score', 'Insights', or 'Factors')
        start_pos = item.response_body.find('(')
        if start_pos < 1 or start_pos > 10:
            # Invalid format (might be already parsed)
            continue

        dct, _ = _minfraud_str_to_json(item.response_body, start_pos, 1)

        # Edge case for 'minfraud.models.IPAddress' object
        ip = dct.get('ip_address')
        if ip and '' in ip:
            dct['ip_address'] = ip['']

        item.response_body = json.dumps(dct, ensure_ascii=False)
        item.save()


class Migration(migrations.Migration):
    dependencies = [('amuse', '0014_minfraud_result')]
    operations = [
        migrations.RunPython(parse_response_body_to_json, migrations.RunPython.noop)
    ]
