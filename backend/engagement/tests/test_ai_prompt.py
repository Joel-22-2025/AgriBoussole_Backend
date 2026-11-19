from prompt_builder import build_prompt


def test_prompt_promotes_boussole_without_sql() -> None:
    """Le prompt positionne Boussole comme conseillère, sans sortie SQL."""
    messages = build_prompt(
        {
            "user_query": "Comment structurer mon projet ?",
            "schema_text": "TABLE: accounts_user\n  COLONNES: id, email",
            "available_tables": ["accounts_user"],
        }
    )

    system = messages[0]["content"]
    assert messages[0]["role"] == "system"
    assert messages[1] == {
        "role": "user",
        "content": "Question de l'utilisateur : Comment structurer mon projet ?",
    }
    assert "Boussole" in system
    assert "Ne montre jamais de requête SQL" in system
    assert "Génère d'abord une requête SQL" not in system
    assert "```sql" not in system
    assert "simple salut" in system


def test_prompt_adapts_to_saei_role() -> None:
    """Le prompt aide les SAEI à concevoir formations et accompagnements."""
    messages = build_prompt(
        {
            "user_query": "Aide-moi à élaborer une formation.",
            "schema_text": "TABLE: structures_structure\n  COLONNES: id, nom",
            "available_tables": ["structures_structure"],
        },
        role="SAEI",
    )

    system = messages[0]["content"]
    assert "structure d'accompagnement (SAEI)" in system
    assert "formation ou un module pédagogique" in system
    assert "suivi des entrepreneurs" in system


def test_prompt_uses_selected_language() -> None:
    """Le prompt demande une réponse dans la langue choisie par l'utilisateur."""
    messages = build_prompt(
        {
            "user_query": "Salut",
            "schema_text": "TABLE: accounts_user\n  COLONNES: id, email",
            "available_tables": ["accounts_user"],
        },
        locale="wo",
    )

    assert "Réponds toujours en wolof" in messages[0]["content"]
