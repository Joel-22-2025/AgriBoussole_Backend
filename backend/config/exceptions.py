from rest_framework.views import exception_handler
from rest_framework.response import Response


def custom_exception_handler(exc, context):
    """
    Gestionnaire d'exceptions DRF pour homogénéiser les réponses d'erreur JSON.

    Format :
    {
        "error": true,
        "message": "...",
        "status": "...",  # uniquement quand pertinent (ex: refus de connexion SAEI)
        "errors": { ... }  # uniquement en cas d'erreurs de validation
    }
    """
    response = exception_handler(exc, context)
    if response is None:
        return None

    data = response.data
    if not isinstance(data, dict):
        data = {'detail': data}

    status_field = data.pop('status', None)
    detail = data.pop('detail', None)

    if detail is not None:
        message = str(detail) if not isinstance(detail, str) else detail
    else:
        message = 'Une erreur est survenue.'

    normalized = {'error': True, 'message': message}

    if status_field is not None:
        normalized['status'] = status_field

    # Reste des données (erreurs de champ par ex.)
    remaining = {k: v for k, v in data.items() if k != 'detail'}
    if remaining:
        normalized['errors'] = remaining

    response.data = normalized
    return response
