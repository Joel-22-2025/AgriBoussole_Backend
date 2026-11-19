"""Sérialiseurs de l'API de l'assistant IA."""

from rest_framework import serializers


class AskQuestionSerializer(serializers.Serializer):
    """Valide la question envoyée à l'assistant."""

    question = serializers.CharField(max_length=2000, trim_whitespace=True)
    locale = serializers.ChoiceField(
        choices=['fr', 'wo', 'dyo'],
        required=False,
        default='fr',
    )

    def validate_question(self, value: str) -> str:
        """Refuse une question vide après suppression des espaces."""
        question = value.strip()
        if not question:
            raise serializers.ValidationError("La question ne peut pas être vide.")
        return question
