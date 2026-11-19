"""Barème et grille de lecture du quiz d’identification de phase.

Le serveur est la source de vérité : le score n’est jamais calculé côté client.
"""

from .models import Phase

QUESTION_IDS = ('q1', 'q2', 'q3', 'q4', 'q5', 'q6', 'q7')
CHOICE_POINTS = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
MAX_SCORE = len(QUESTION_IDS) * 3

PHASES = (
    {
        'min': 0,
        'max': 4,
        'phase': Phase.IDEATION,
        'label': 'Idéation',
        'range': '0 – 4',
        'orientation': "Structures d’idéation, coaching, formation de base",
        'stade': 'Idéation',
    },
    {
        'min': 5,
        'max': 8,
        'phase': Phase.CREATION,
        'label': 'Création',
        'range': '5 – 8',
        'orientation': (
            'Structures de pré-incubation / incubation, appui à la formalisation, '
            'prototypage'
        ),
        'stade': 'Incubation',
    },
    {
        'min': 9,
        'max': 12,
        'phase': Phase.INCUBATION,
        'label': 'Incubation',
        'range': '9 – 12',
        'orientation': (
            'Incubateurs et accélérateurs, coaching individuel, '
            'accès au financement d’amorçage'
        ),
        'stade': 'Incubation',
    },
    {
        'min': 13,
        'max': 15,
        'phase': Phase.ACCELERATION,
        'label': 'Accélération',
        'range': '13 – 15',
        'orientation': (
            'Accélérateurs, programmes d’investissement, mise en relation financeurs'
        ),
        'stade': 'Accélération',
    },
    {
        'min': 16,
        'max': 17,
        'phase': Phase.DEVELOPPEMENT,
        'label': 'Développement / Croissance',
        'range': '16 – 17',
        'orientation': 'Structures de financement, appui à la structuration',
        'stade': 'Développement',
    },
    {
        'min': 18,
        'max': 19,
        'phase': Phase.CROISSANCE,
        'label': 'Croissance',
        'range': '18 – 19',
        'orientation': 'Appui à l’export, financement, conseil stratégique',
        'stade': 'Croissance',
    },
    {
        'min': 20,
        'max': 21,
        'phase': Phase.PASSAGE_ECHELLE,
        'label': 'Passage à l’échelle',
        'range': '20 – 21',
        'orientation': (
            'Programmes d’investissement, partenariats, mise en relation bailleurs, '
            'réseaux internationaux'
        ),
        'stade': 'Passage à l’échelle',
    },
)

PHASES_BY_KEY = {item['phase']: item for item in PHASES}


def evaluate_answers(answers):
    """Retourne (score, grille) pour un dictionnaire de réponses valide."""
    score = sum(CHOICE_POINTS[answers[question_id]] for question_id in QUESTION_IDS)
    phase = next(item for item in PHASES if item['min'] <= score <= item['max'])
    return score, phase


def phase_response(profile):
    """Payload API commun à GET et POST."""
    phase = PHASES_BY_KEY.get(profile.phase) if profile.phase else None
    return {
        'phase': profile.phase or None,
        'label': phase['label'] if phase else None,
        'score': profile.score_phase,
        'max_score': MAX_SCORE,
        'range': phase['range'] if phase else None,
        'orientation': phase['orientation'] if phase else None,
        'stade': phase['stade'] if phase else None,
        'answers': profile.phase_answers or {},
        'completed_at': profile.phase_completed_at,
    }
