"""Construction du contexte schéma pour l'assistant IA AgriBoussole.

Ce module est la première étape du backend IA : il ne interroge pas encore
l'API Groq. Il se contente de lire le schéma de la base via l'API d'introspection
de Django (``Model._meta``) et de le sérialiser sous une forme lisible par un LLM.

Aucune requête SQL n'est écrite en dur : les noms de tables, de colonnes et les
relations sont exclusivement déduits du registre des modèles Django.
"""

from __future__ import annotations

import logging
from typing import Any

import django
from django.apps import apps
from django.db import models
from django.db.models.fields import NOT_PROVIDED

logger = logging.getLogger(__name__)

__all__ = ["ContextBuilderError", "build_context", "get_schema_text"]


class ContextBuilderError(Exception):
    """Erreur levée lorsque le schéma ne peut pas être construit."""


def _ensure_apps_ready() -> None:
    """S'assure que le registre des applications Django est initialisé.

    ``apps.get_models()`` lève ``AppRegistryNotReady`` si le module est importé
    avant ``django.setup()`` (cas d'un script autonome). Appeler ``setup()`` est
    sans effet lorsque Django est déjà démarré par ``manage.py``.
    """
    if not apps.ready:
        django.setup()


def _iter_models() -> list[type[models.Model]]:
    """Retourne tous les modèles enregistrés, tables de jointure exclues.

    Les modèles automatiques (tables de jointure M2M générées) sont exclus de
    cette liste : leurs noms sont ajoutés séparément à ``available_tables``.
    """
    _ensure_apps_ready()
    return list(apps.get_models(include_auto_created=False))


def _format_column(field: models.Field[Any, Any]) -> str:
    """Décrit une colonne (ou un champ M2M) sous forme d'une ligne de texte.

    Args:
        field: Champ Django issu de ``_meta.local_fields`` ou ``local_many_to_many``.

    Returns:
        Une ligne indentée décrivant le champ : nom, type SQL interne,
        nullabilité, unicité, choix, valeur par défaut et libellé.
    """
    column = getattr(field, "column", None)
    if column is None and hasattr(field, "m2m_db_table"):
        column = field.m2m_db_table()
    column = column or field.name

    field_type = field.get_internal_type()
    attributes: list[str] = [field_type]

    if getattr(field, "primary_key", False):
        attributes.append("PK")
    if getattr(field, "unique", False):
        attributes.append("UNIQUE")
    if getattr(field, "null", False):
        attributes.append("NULL")
    else:
        attributes.append("NOT NULL")
    if getattr(field, "blank", False):
        attributes.append("blank")

    max_length = getattr(field, "max_length", None)
    if max_length:
        attributes.append(f"max_length={max_length}")

    default = getattr(field, "default", NOT_PROVIDED)
    if default is not NOT_PROVIDED:
        attributes.append(f"default={default!r}")

    verbose_name = str(getattr(field, "verbose_name", "") or "")
    if verbose_name and verbose_name.lower() != field.name.lower():
        attributes.append(f'libellé="{verbose_name}"')

    line = f"    - {column} ({', '.join(attributes)})"

    choices = getattr(field, "choices", None)
    if choices:
        values = [str(value) for value, _label in choices]
        line += f" — choix: {', '.join(values)}"

    return line


def _format_forward_relation(field: models.Field[Any, Any]) -> str | None:
    """Décrit une relation sortante (FK / OneToOne / ManyToMany)."""
    related_model = getattr(field, "related_model", None)
    if related_model is None:
        return None

    relation_type = "ManyToMany" if field.many_to_many else (
        "OneToOne" if field.one_to_one else "ForeignKey"
    )
    remote_field = getattr(field, "remote_field", None)
    on_delete = getattr(remote_field, "on_delete", None)
    on_delete_name = getattr(on_delete, "__name__", str(on_delete) if on_delete else "—")
    related_name = getattr(remote_field, "related_name", None) or "—"

    column = getattr(field, "column", None)
    if column is None and hasattr(field, "m2m_db_table"):
        column = field.m2m_db_table()

    return (
        f"    - {column or field.name} -> {related_model._meta.db_table} "
        f"({relation_type}, on_delete={on_delete_name}, related_name={related_name})"
    )


def _format_reverse_relation(relation: Any) -> str:
    """Décrit une relation entrante (ForeignObjectRel) vers le modèle courant."""
    source_model = relation.related_model
    relation_type = type(relation).__name__
    try:
        accessor = relation.get_accessor_name()
    except Exception:  # pragma: no cover - dépend de l'état du registre Django
        accessor = "—"

    return (
        f"    - {source_model._meta.db_table}.{relation.field.name} "
        f"-> {relation.model._meta.db_table} ({relation_type}, accessor={accessor})"
    )


def _describe_model(model: type[models.Model]) -> str:
    """Produit la description textuelle complète d'un modèle.

    Args:
        model: Classe de modèle Django.

    Returns:
        Bloc de texte avec le nom de table, les colonnes, les relations
        sortantes et les relations entrantes.
    """
    meta = model._meta
    lines = [
        f"TABLE: {meta.db_table}",
        f"  Modèle: {meta.label} — {meta.verbose_name}",
        "  COLONNES:",
    ]

    fields = list(meta.local_fields) + list(meta.local_many_to_many)
    for field in fields:
        try:
            lines.append(_format_column(field))
        except Exception as exc:  # un champ exotique ne doit pas casser le schéma
            logger.warning("Impossible de décrire %s.%s : %s", meta.label, field.name, exc)
            lines.append(f"    - {field.name} (type indisponible)")

    forward = [
        description
        for field in fields
        if (description := _format_forward_relation(field)) is not None
    ]
    if forward:
        lines.append("  RELATIONS SORTANTES (clés étrangères):")
        lines.extend(forward)

    reverse = []
    for relation in meta.related_objects:
        try:
            reverse.append(_format_reverse_relation(relation))
        except Exception as exc:  # relation non résolue : on continue
            logger.warning("Impossible de décrire la relation inverse de %s : %s", meta.label, exc)
    if reverse:
        lines.append("  RELATIONS ENTRANTES:")
        lines.extend(reverse)

    return "\n".join(lines)


def _collect_available_tables(models_list: list[type[models.Model]]) -> list[str]:
    """Collecte les noms de tables réelles, y compris les tables de jointure M2M."""
    tables: set[str] = set()
    for model in models_list:
        tables.add(model._meta.db_table)
        for field in model._meta.local_many_to_many:
            m2m_table = getattr(field, "m2m_db_table", None)
            if callable(m2m_table):
                tables.add(m2m_table())
    return sorted(tables)


def get_schema_text(models_list: list[type[models.Model]] | None = None) -> tuple[str, list[str]]:
    """Génère la description du schéma et la liste des tables disponibles.

    Args:
        models_list: Modèles à décrire. Par défaut, tous les modèles enregistrés.

    Returns:
        Un tuple ``(schema_text, available_tables)``.

    Raises:
        ContextBuilderError: Si le registre des modèles est inexploitable.
    """
    try:
        selected_models = models_list if models_list is not None else _iter_models()
        available_tables = _collect_available_tables(selected_models)

        blocks = [
            "SCHÉMA DE LA BASE DE DONNÉES AGRIBOUSSOLE",
            "Source : introspection Django (_meta), aucune requête SQL en dur.",
            f"Tables disponibles : {len(available_tables)}",
            "",
        ]
        for model in selected_models:
            try:
                blocks.append(_describe_model(model))
                blocks.append("")
            except Exception as exc:
                logger.exception("Échec de la description du modèle %s", model._meta.label)
                blocks.append(f"TABLE: {model._meta.db_table} — description indisponible ({exc})")
                blocks.append("")

        return "\n".join(blocks).strip(), available_tables
    except ContextBuilderError:
        raise
    except Exception as exc:
        logger.exception("Impossible de construire le schéma de la base")
        raise ContextBuilderError(f"Échec de l'introspection du schéma : {exc}") from exc


def build_context(user_query: str) -> dict[str, Any]:
    """Construit le dictionnaire de contexte transmis au LLM.

    Aucune analyse d'intention n'est effectuée à cette étape : le schéma complet
    est fourni et le modèle décide lui-même des tables pertinentes.

    Args:
        user_query: Question posée par l'utilisateur.

    Returns:
        Un dictionnaire avec les clés ``user_query``, ``schema_text`` et
        ``available_tables``.

    Raises:
        TypeError: Si ``user_query`` n'est pas une chaîne de caractères.
        ValueError: Si la question est vide.
        ContextBuilderError: Si le schéma ne peut pas être lu.
    """
    if not isinstance(user_query, str):
        raise TypeError("user_query doit être une chaîne de caractères.")

    query = user_query.strip()
    if not query:
        raise ValueError("user_query ne peut pas être vide.")

    schema_text, available_tables = get_schema_text()

    return {
        "user_query": query,
        "schema_text": schema_text,
        "available_tables": available_tables,
    }
