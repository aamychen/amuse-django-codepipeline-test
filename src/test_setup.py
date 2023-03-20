import subprocess

import pytest
import requests
import responses
from celery import current_app
from django.core.cache import cache
from django.core.management import call_command


@current_app.task
def sum_of_values(x, y):
    return x + y


@pytest.mark.django_db
def test_no_missing_migrations():
    """Check no model changes have been made since the last `./manage.py makemigrations`."""
    try:
        call_command(
            'makemigrations', interactive=False, dry_run=True, check_changes=True
        )
    except SystemExit as e:
        exit_code = str(e)
        assert exit_code == '1'

        pytest.fail('Migrations are missing. Run `manage.py makemigrations`')


def test_celery_setup():
    """Test celery executes a task properly"""

    result = sum_of_values.delay(7, 3)

    assert result.wait() == 10


@pytest.mark.django_db
def test_django_cache():
    """Test the Django cache backend & associated server are properly set up."""
    k, v = 'my_key', 'my_value'
    cache.set(k, v, 10)

    assert cache.get(k) == v


def test_block_unmocked_requests():
    """Ensure the `block_unmocked_requests` fixture prevents requests from hitting the network."""
    url = 'https://example.com'
    with pytest.raises(RuntimeError):
        requests.get(url)
        pytest.fail("Tests must mock all HTTP requests!")

    with pytest.raises(RuntimeError):
        requests.post(url)
        pytest.fail("Tests must mock all HTTP requests!")

    with responses.RequestsMock() as rsps:
        expected = 'Mocked GET requests still work'
        rsps.add(responses.GET, url, body=expected)

        r = requests.get(url)

        assert r.text == expected

    with responses.RequestsMock() as rsps:
        expected = 'Mocked POST requests still work'
        rsps.add(responses.POST, url, body=expected)

        r = requests.post(url)

        assert r.text == expected


def test_lock_file_up_to_date():
    result = subprocess.run(['poetry', 'lock', '--check'], capture_output=True)
    output = result.stdout.decode('utf-8')
    print(output)
    try:
        result.check_returncode()
    except subprocess.CalledProcessError as e:
        print(e.stderr.decode('utf-8'))
        pytest.fail(
            'Error: poetry.lock is not consistent with pyproject.toml. Run `poetry lock [--no-update]` to fix it.'
        )
