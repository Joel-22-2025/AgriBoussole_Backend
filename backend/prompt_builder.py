"""Construction du prompt Chat Completion pour Boussole (IA AgriBoussole).

Deuxième étape du backend IA : ce module reçoit le dictionnaire produit par
``context_builder.build_context`` et assemble la liste de messages à envoyer à
l'API Groq (format compatible OpenAI Chat Completion).

Boussole est une conseillère en entrepreneuriat agricole. Le schéma de base est
un contexte interne : il ne doit jamais apparaître dans la réponse utilisateur
(sans SQL, sans noms de tables techniques).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["PromptBuilderError", "build_prompt"]

ChatMessage = dict[str, str]

REQUIRED_CONTEXT_KEYS = ("user_query", "schema_text", "available_tables")

# Le quota gratuit Groq est limité en tokens/minute : on ne transmet qu'un
# résumé compact des tables métier, jamais le schéma technique complet.
BUSINESS_TABLE_PREFIXES = ("accounts_", "structures_", "engagement_")
MAX_SCHEMA_CHARS = 5_000
MAX_COLUMNS_PER_TABLE = 12

# Orientation complémentaire selon le rôle de l'utilisateur authentifié.
ROLE_GUIDANCE: dict[str, str] = {
    "ENTREPRENEUR": (
        "L'utilisateur est un entrepreneur agricole. Aide-le à structurer son idée, "
        "à choisir une activité, à préparer son plan d'action et à estimer ses besoins."
    ),
    "SAEI": (
        "L'utilisateur travaille au sein d'une structure d'accompagnement (SAEI). "
        "Aide-le à élaborer une formation ou un module pédagogique (objectifs, public cible, "
        "contenu, méthode, durée, évaluation), à concevoir une offre d'accompagnement, "
        "à préparer le suivi des entrepreneurs, à animer son équipe et à communiquer "
        "sur ses activités. Propose des plans concrets et des exemples adaptés au Bénin, "
        "au Sénégal ou en Côte d'Ivoire."
    ),
    "ADMIN": (
        "L'utilisateur est un administrateur de la plateforme. Aide-le à piloter "
        "l'accompagnement et à comprendre les indicateurs généraux, sans donner "
        "d'informations techniques internes."
    ),
}
DEFAULT_ROLE_GUIDANCE = ROLE_GUIDANCE["ENTREPRENEUR"]

# Langue de réponse demandée par l'interface (français, wolof, diola).
LANGUAGE_NAMES: dict[str, str] = {
    "fr": "français",
    "wo": "wolof",
    "dyo": "diola",
}

SYSTEM_PROMPT_TEMPLATE = """Tu es Boussole, l'intelligence artificielle d'AgriBoussole, une plateforme qui accompagne les entrepreneurs agricoles et les met en relation avec des structures d'accompagnement (SAEI) au Bénin, au Sénégal et en Côte d'Ivoire.

RÔLE
Tu es une conseillère en entrepreneuriat agricole. Tu aides l'utilisateur à structurer une idée, à trouver des pistes d'activité, à préparer un plan d'action, à estimer des besoins et à formuler des prévisions. Tu connais également les informations que la plateforme AgriBoussole gère.

RÈGLES DE RÉPONSE
1. Réponds toujours en {language_name}, de façon claire, encourageante et concrète, avec des phrases courtes et des listes si utile.
2. Ne refuse JAMAIS une question au motif qu'elle n'est pas traduisible en SQL. Réponds à toute question liée à l'entrepreneuriat, à l'agriculture, à l'orientation ou à la plateforme.
3. Ne montre jamais de requête SQL, de code, de nom de table technique ni de jargon de base de données. Les informations ci-dessous sont fournies uniquement pour te guider en interne.
4. Quand la question porte sur des données de la plateforme, explique quels éléments regarder et comment les interpréter, sans inventer de chiffres ni prétendre connaître les valeurs réelles.
5. Pour une prévision, précise toujours les hypothèses et présente une fourchette prudente plutôt qu'un chiffre présenté comme certain.
6. Si la question est très large, donne d'abord une réponse utile, puis propose une ou deux questions de clarification.
7. Reste dans le contexte de l'agriculture, de l'agroalimentaire et de l'accompagnement des entrepreneurs en Afrique de l'Ouest.
8. Si l'utilisateur écrit un simple salut (« salut », « bonjour », « hello »), réponds en une ou deux phrases maximum, sans répéter ton message d'accueil, et pose une question courte pour lancer l'échange.

PROFIL DE L'UTILISATEUR
{role_text}

LANGUE DE RÉPONSE (OBLIGATOIRE)
Réponds intégralement en {language_name}, même si la question est écrite en français ou si le contexte ci-dessous est en français. Ne joins pas de traduction française.

CONTEXTE INTERNE — INFORMATIONS GÉRÉES PAR LA PLATEFORME
{schema_text}

TABLES DISPONIBLES (usage interne uniquement)
{tables_text}
"""


class PromptBuilderError(Exception):
    """Erreur levée lorsque le prompt ne peut pas être construit."""


def _format_tables(available_tables: list[str]) -> str:
    """Formate la liste des tables pour le message système.

    Args:
        available_tables: Noms de tables issus du Context Builder.

    Returns:
        Une liste à puces, ou une mention explicite si la liste est vide.
    """
    if not available_tables:
        return "(aucune table disponible)"
    return "\n".join(f"- {table}" for table in available_tables)


def _role_guidance(role: str | None) -> str:
    """Retourne l'orientation pédagogique associée au rôle de l'utilisateur.

    Args:
        role: Rôle Django de l'utilisateur (``SAEI``, ``ENTREPRENEUR``, ``ADMIN``)
            ou ``None`` si le rôle est inconnu.

    Returns:
        Un paragraphe court à insérer dans le message système.
    """
    if not role:
        return DEFAULT_ROLE_GUIDANCE
    return ROLE_GUIDANCE.get(role.strip().upper(), DEFAULT_ROLE_GUIDANCE)


def _language_name(locale: str | None) -> str:
    """Retourne le nom de la langue de réponse attendue.

    Args:
        locale: Code langue envoyé par l'interface (``fr``, ``wo``, ``dyo``).

    Returns:
        Le nom lisible de la langue, avec le français par défaut.
    """
    if not locale:
        return LANGUAGE_NAMES["fr"]
    return LANGUAGE_NAMES.get(locale.strip().lower(), LANGUAGE_NAMES["fr"])


def _compact_schema(schema_text: str) -> str:
    """Réduit le schéma complet à un résumé des tables métier.

    Seules les tables métier sont conservées, avec leurs douze premières
    colonnes. Cette compression garde le prompt sous la limite de tokens par
    minute de l'offre Groq gratuite, sans changer le rôle de Boussole.

    Args:
        schema_text: Schéma verbeux produit par ``build_context``.

    Returns:
        Un résumé lisible du schéma métier.
    """
    blocks: list[str] = []
    table: str | None = None
    model = ""
    columns: list[str] = []

    def flush() -> None:
        nonlocal table, model, columns
        if not table:
            return
        if table.startswith(BUSINESS_TABLE_PREFIXES):
            col_text = ", ".join(columns) if columns else "(colonnes non détaillées)"
            blocks.append(f"TABLE: {table}\n  {model}\n  COLONNES: {col_text}")
        table, model, columns = None, "", []

    for line in schema_text.splitlines():
        if line.startswith("TABLE: "):
            flush()
            table = line.removeprefix("TABLE: ").strip()
        elif table and line.startswith("  Modèle: "):
            model = line.strip()
        elif table and line.startswith("    - ") and "(" in line:
            if len(columns) < MAX_COLUMNS_PER_TABLE:
                columns.append(line.strip()[2:].split(" ", 1)[0])

    flush()

    compact = "\n".join(blocks) or "(schéma métier indisponible)"
    if len(compact) > MAX_SCHEMA_CHARS:
        compact = compact[:MAX_SCHEMA_CHARS] + "\n… (schéma réduit)"
    return compact


def _validate_context(context: Mapping[str, Any]) -> tuple[str, str, list[str]]:
    """Vérifie la structure du dictionnaire de contexte reçu.

    Args:
        context: Dictionnaire retourné par ``build_context``.

    Returns:
        Un tuple ``(user_query, schema_text, available_tables)`` normalisé.

    Raises:
        TypeError: Si ``context`` n'est pas un mapping.
        PromptBuilderError: Si une clé est absente ou d'un type invalide.
    """
    if not isinstance(context, Mapping):
        raise TypeError("context doit être un dictionnaire (ou un mapping).")

    missing = [key for key in REQUIRED_CONTEXT_KEYS if key not in context]
    if missing:
        raise PromptBuilderError(
            f"Clés de contexte manquantes : {', '.join(missing)}."
        )

    user_query = context["user_query"]
    schema_text = context["schema_text"]
    available_tables = context["available_tables"]

    if not isinstance(user_query, str) or not user_query.strip():
        raise PromptBuilderError("La clé 'user_query' doit être une chaîne non vide.")
    if not isinstance(schema_text, str) or not schema_text.strip():
        raise PromptBuilderError("La clé 'schema_text' doit être une chaîne non vide.")
    if not isinstance(available_tables, (list, tuple)) or not all(
        isinstance(table, str) for table in available_tables
    ):
        raise PromptBuilderError(
            "La clé 'available_tables' doit être une liste de noms de tables (chaînes)."
        )

    return user_query.strip(), schema_text.strip(), list(available_tables)


def build_prompt(
    context: Mapping[str, Any],
    role: str | None = None,
    locale: str | None = None,
) -> list[ChatMessage]:
    """Assemble les messages Chat Completion à envoyer à l'API Groq.

    Args:
        context: Dictionnaire retourné par ``build_context``, contenant
            ``user_query``, ``schema_text`` et ``available_tables``.
        role: Rôle de l'utilisateur authentifié, utilisé pour adapter les
            conseils (formation pour les SAEI, structuration pour les entrepreneurs).
        locale: Langue de réponse choisie dans l'interface (``fr``, ``wo``, ``dyo``).

    Returns:
        Une liste de deux messages : le message ``system`` (rôle, contexte
        interne et règles de réponse) puis le message ``user`` contenant la
        question.

    Raises:
        TypeError: Si ``context`` n'est pas un mapping.
        PromptBuilderError: Si le contexte est invalide ou incomplet.
    """
    try:
        user_query, schema_text, available_tables = _validate_context(context)

        system_content = SYSTEM_PROMPT_TEMPLATE.format(
            language_name=_language_name(locale),
            role_text=_role_guidance(role),
            schema_text=_compact_schema(schema_text),
            tables_text=_format_tables(available_tables),
        )

        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": f"Question de l'utilisateur : {user_query}"},
        ]
    except (TypeError, PromptBuilderError):
        raise
    except Exception as exc:
        logger.exception("Impossible de construire le prompt pour Groq")
        raise PromptBuilderError(f"Échec de la construction du prompt : {exc}") from exc
