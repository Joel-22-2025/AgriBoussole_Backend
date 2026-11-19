from unittest.mock import patch

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from accounts.models import User


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1'])
def test_ask_ai_authenticated() -> None:
    client = APIClient()
    client.force_authenticate(user=User(email='test@example.com'))
    with patch('ai.views.ask_database', return_value='SELECT 1;') as mocked:
        response = client.post('/api/ai/ask/', {'question': 'Combien ?'}, format='json')
    assert response.status_code == 200
    assert response.json() == {'answer': 'SELECT 1;'}
    assert mocked.call_args.args == ('Combien ?',)
    assert mocked.call_args.kwargs == {'role': 'ENTREPRENEUR', 'locale': 'fr'}


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1'])
def test_ask_ai_requires_authentication() -> None:
    client = APIClient()
    response = client.post('/api/ai/ask/', {'question': 'test'}, format='json')
    assert response.status_code in (401, 403)


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1'])
def test_ask_ai_rejects_empty_question() -> None:
    client = APIClient()
    client.force_authenticate(user=User(email='test@example.com'))
    with patch('ai.views.ask_database') as mocked:
        response = client.post('/api/ai/ask/', {'question': '   '}, format='json')
    assert response.status_code == 400
    mocked.assert_not_called()
