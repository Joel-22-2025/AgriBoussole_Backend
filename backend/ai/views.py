"""Vues de l'API de l'assistant IA."""

import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from llm_service import GroqAPIError, ask_database

from .serializers import AskQuestionSerializer

logger = logging.getLogger(__name__)


class AskAIView(APIView):
    """Reçoit une question et retourne la réponse du LLM Groq."""

    permission_classes = [IsAuthenticated]
    throttle_scope = 'ai'

    def post(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Valide la question, appelle le pipeline IA et renvoie la réponse.

        Args:
            request: Requête DRF authentifiée contenant ``question``.

        Returns:
            200 avec ``{"answer": "..."}``, 503 si Groq échoue, 500 pour une
            erreur inattendue.
        """
        serializer = AskQuestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            answer = ask_database(
                serializer.validated_data['question'],
                role=getattr(request.user, 'role', None),
                locale=serializer.validated_data.get('locale', 'fr'),
            )
        except GroqAPIError as exc:
            logger.warning("Échec Groq (utilisateur %s) : %s", request.user.pk, exc)
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception:
            logger.exception("Erreur inattendue de l'assistant IA")
            return Response(
                {'detail': "L'assistant IA a échoué."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({'answer': answer})
