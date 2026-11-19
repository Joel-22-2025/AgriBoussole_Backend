"""Appel au LLM Groq pour l'assistant IA AgriBoussole.

Troisième et dernière étape du pipeline IA :
``build_context`` -> ``build_prompt`` -> ``call_llm``.

La clé API est lue en priorité dans ``GROQ_API_KEY``, puis dans le réglage
Django ``settings.GROQ_API_KEY`` (alimenté par ``cley_grok`` dans le .env local).
Aucune valeur sensible n'est journalisée.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import requests
from django.conf import settings

from context_builder import ContextBuilderError, build_context
from prompt_builder import ChatMessage, PromptBuilderError, build_prompt

logger = logging.getLogger(__name__)

__all__ = [
    "GroqAPIError",
    "MissingGroqAPIKeyError",
    "ask_database",
    "call_llm",
]

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
# `llama-3.3-70b-versatile` n'est plus disponible sur la clé gratuite actuelle
# (404 model_not_found). Les modèles ci-dessous sont essayés dans cet ordre.
GROQ_MODEL = "openai/gpt-oss-120b"
GROQ_FALLBACK_MODELS: tuple[str, ...] = (
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
)
GROQ_TEMPERATURE = 0.1
GROQ_TIMEOUT_SECONDS = 30.0


class GroqAPIError(RuntimeError):
    """Erreur lors de l'appel à l'API Groq ou de la lecture de sa réponse."""


class MissingGroqAPIKeyError(GroqAPIError):
    """Erreur levée lorsque la variable GROQ_API_KEY est absente ou vide."""


def _validate_messages(messages: list[ChatMessage]) -> None:
    """Vérifie la forme des messages avant de les envoyer à Groq.

    Args:
        messages: Liste de messages au format Chat Completion.

    Raises:
        TypeError: Si ``messages`` n'est pas une liste.
        ValueError: Si un message est mal formé.
    """
    if not isinstance(messages, list):
        raise TypeError("messages doit être une liste de dictionnaires.")

    if not messages:
        raise ValueError("messages ne peut pas être vide.")

    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            raise ValueError(f"Le message {index} doit être un dictionnaire.")
        role = message.get("role")
        content = message.get("content")
        if not isinstance(role, str) or not role:
            raise ValueError(f"Le message {index} n'a pas de 'role' valide.")
        if not isinstance(content, str) or not content:
            raise ValueError(f"Le message {index} n'a pas de 'content' valide.")


def _extract_content(response_data: dict[str, Any]) -> str:
    """Extrait le texte de ``choices[0].message.content``.

    Args:
        response_data: Corps JSON décodé de la réponse Groq.

    Returns:
        Le contenu textuel du premier choix.

    Raises:
        GroqAPIError: Si la structure de réponse est inattendue.
    """
    choices = response_data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise GroqAPIError("La réponse Groq ne contient aucun choix ('choices').")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise GroqAPIError("Le premier choix Groq est mal formé.")

    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise GroqAPIError("Le premier choix Groq ne contient pas de message.")

    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise GroqAPIError("Le message Groq ne contient aucun texte exploitable.")

    return content.strip()


def call_llm(messages: list[ChatMessage]) -> str:
    """Envoie les messages à l'API Groq et retourne la réponse texte.

    Args:
        messages: Messages au format OpenAI Chat Completion, typiquement
            produits par ``prompt_builder.build_prompt``.

    Returns:
        Le contenu de ``choices[0].message.content``.

    Raises:
        TypeError: Si ``messages`` n'est pas une liste de dictionnaires.
        ValueError: Si la liste est vide ou mal formée.
        MissingGroqAPIKeyError: Si aucune clé n'est disponible (``GROQ_API_KEY``
            ou ``settings.GROQ_API_KEY``).
        GroqAPIError: En cas de timeout, d'erreur HTTP, de JSON invalide ou de
            réponse inexploitable.
    """
    _validate_messages(messages)

    api_key = os.environ.get("GROQ_API_KEY") or getattr(settings, "GROQ_API_KEY", "")
    if not api_key or not api_key.strip():
        raise MissingGroqAPIKeyError(
            "La variable d'environnement GROQ_API_KEY est absente ou vide."
        )

    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
    }
    models = (GROQ_MODEL, *GROQ_FALLBACK_MODELS)
    last_error = "aucun modèle essayé"

    for model in models:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": GROQ_TEMPERATURE,
        }

        try:
            response = requests.post(
                GROQ_API_URL,
                json=payload,
                headers=headers,
                timeout=GROQ_TIMEOUT_SECONDS,
            )
        except requests.Timeout as exc:
            raise GroqAPIError(
                f"Délai dépassé lors de l'appel à Groq ({GROQ_TIMEOUT_SECONDS} s)."
            ) from exc
        except requests.RequestException as exc:
            logger.exception("Erreur réseau lors de l'appel à Groq")
            raise GroqAPIError(f"Erreur réseau lors de l'appel à Groq : {exc}") from exc

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            detail = response.text[:500] if response.text else "aucun détail fourni"
            if response.status_code == 404 and "model_not_found" in detail:
                logger.warning("Modèle Groq %s indisponible, essai du suivant", model)
                last_error = detail
                continue
            logger.error("Groq a répondu avec le statut %s : %s", response.status_code, detail)
            raise GroqAPIError(
                f"Groq a refusé la requête (HTTP {response.status_code}) : {detail}"
            ) from exc

        try:
            response_data = response.json()
        except ValueError as exc:
            raise GroqAPIError("La réponse Groq n'est pas un JSON valide.") from exc

        if not isinstance(response_data, dict):
            raise GroqAPIError("La réponse Groq n'est pas un objet JSON.")

        usage = response_data.get("usage")
        if isinstance(usage, dict):
            logger.info("Groq usage: %s", usage)

        return _extract_content(response_data)

    raise GroqAPIError(f"Aucun modèle Groq disponible : {last_error}")


def ask_database(
    user_query: str,
    role: str | None = None,
    locale: str | None = None,
) -> str:
    """Chaîne complète Context Builder -> Prompt Builder -> appel Groq.

    Args:
        user_query: Question posée par l'utilisateur.
        role: Rôle de l'utilisateur, utilisé pour adapter les conseils
            (formations et accompagnement pour les SAEI).
        locale: Langue de réponse choisie (``fr``, ``wo``, ``dyo``).

    Returns:
        La réponse finale de Boussole, sans SQL ni jargon technique.

    Raises:
        TypeError: Si ``user_query`` n'est pas une chaîne.
        ValueError: Si la question est vide.
        ContextBuilderError: Si le schéma ne peut pas être construit.
        PromptBuilderError: Si le prompt ne peut pas être construit.
        GroqAPIError: Si l'appel à Groq échoue.
    """
    try:
        context = build_context(user_query)
        messages = build_prompt(context, role=role, locale=locale)
        return call_llm(messages)
    except (
        TypeError,
        ValueError,
        ContextBuilderError,
        PromptBuilderError,
        GroqAPIError,
    ):
        raise
    except Exception as exc:
        logger.exception("Échec inattendu du pipeline IA")
        raise GroqAPIError(f"Échec du pipeline IA : {exc}") from exc
