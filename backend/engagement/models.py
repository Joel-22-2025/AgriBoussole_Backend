from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from accounts.models import EntrepreneurProfile, SaeiProfile


class Offre(models.Model):
    """Offre d'insertion, de formation ou d'accompagnement publiée par une SAEI."""

    class Statut(models.TextChoices):
        BROUILLON = 'BROUILLON', 'Brouillon'
        PUBLIEE = 'PUBLIEE', 'Publiée'
        CLOTUREE = 'CLOTUREE', 'Clôturée'

    saei = models.ForeignKey(SaeiProfile, on_delete=models.CASCADE, related_name='offres')
    titre = models.CharField(max_length=200, verbose_name='Titre')
    programme = models.CharField(max_length=200, blank=True, verbose_name='Programme / filière')
    description = models.TextField(verbose_name='Description')
    conditions_eligibilite = models.TextField(verbose_name="Conditions d'éligibilité")
    type_offre = models.CharField(max_length=60, default='Accompagnement', verbose_name="Type d'offre")
    date_limite = models.DateField(null=True, blank=True, verbose_name='Date limite')
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.PUBLIEE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Offre'
        verbose_name_plural = 'Offres'

    def __str__(self):
        return self.titre


class Candidature(models.Model):
    """Candidature d'un entrepreneur à une offre."""

    class Statut(models.TextChoices):
        ENVOYEE = 'ENVOYEE', 'Envoyée'
        EN_COURS = 'EN_COURS', 'En cours'
        ACCEPTEE = 'ACCEPTEE', 'Acceptée'
        REFUSEE = 'REFUSEE', 'Refusée'

    offre = models.ForeignKey(Offre, on_delete=models.CASCADE, related_name='candidatures')
    entrepreneur = models.ForeignKey(
        EntrepreneurProfile, on_delete=models.CASCADE, related_name='candidatures'
    )
    message = models.TextField(blank=True, verbose_name='Motivation')
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.ENVOYEE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = [('offre', 'entrepreneur')]
        verbose_name = 'Candidature'
        verbose_name_plural = 'Candidatures'

    def __str__(self):
        return f'{self.entrepreneur} → {self.offre}'


class IndicateurPerformance(models.Model):
    """Indicateur de performance publié par une SAEI (texte, image ou vidéo)."""

    class TypeMedia(models.TextChoices):
        TEXTE = 'TEXTE', 'Texte'
        IMAGE = 'IMAGE', 'Image'
        VIDEO = 'VIDEO', 'Vidéo'

    saei = models.ForeignKey(SaeiProfile, on_delete=models.CASCADE, related_name='indicateurs')
    titre = models.CharField(max_length=200)
    contenu = models.TextField(blank=True, verbose_name='Contenu / légende')
    type_media = models.CharField(max_length=10, choices=TypeMedia.choices, default=TypeMedia.TEXTE)
    media = models.FileField(upload_to='indicateurs/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Indicateur de performance'
        verbose_name_plural = 'Indicateurs de performance'

    def __str__(self):
        return self.titre


class Reaction(models.Model):
    """Like d'un utilisateur sur un indicateur."""

    indicateur = models.ForeignKey(
        IndicateurPerformance, on_delete=models.CASCADE, related_name='reactions'
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('indicateur', 'user')]
        verbose_name = 'Like'
        verbose_name_plural = 'Likes'

    def __str__(self):
        return f'{self.user.email} aime {self.indicateur_id}'


class Commentaire(models.Model):
    """Commentaire d'un utilisateur sur un indicateur."""

    indicateur = models.ForeignKey(
        IndicateurPerformance, on_delete=models.CASCADE, related_name='commentaires'
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    contenu = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Commentaire'
        verbose_name_plural = 'Commentaires'

    def __str__(self):
        return f'{self.user.email} sur {self.indicateur_id}'


class Conversation(models.Model):
    """Fil de discussion entre un entrepreneur et une SAEI."""

    entrepreneur = models.ForeignKey(
        EntrepreneurProfile, on_delete=models.CASCADE, related_name='conversations'
    )
    saei = models.ForeignKey(SaeiProfile, on_delete=models.CASCADE, related_name='conversations')
    sujet = models.CharField(max_length=200, blank=True, default='Discussion')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        unique_together = [('entrepreneur', 'saei', 'sujet')]
        verbose_name = 'Conversation'
        verbose_name_plural = 'Conversations'

    def __str__(self):
        return f'{self.entrepreneur} ↔ {self.saei} — {self.sujet}'


class Message(models.Model):
    """Message unique du chat, des notifications et des demandes d'insertion."""

    class TypeMessage(models.TextChoices):
        CHAT = 'CHAT', 'Discussion'
        NOTIFICATION = 'NOTIFICATION', 'Notification'
        DEMANDE_INSERTION = 'DEMANDE_INSERTION', "Demande d'insertion"

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    type_message = models.CharField(max_length=20, choices=TypeMessage.choices, default=TypeMessage.CHAT)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'

    def __str__(self):
        return f'{self.get_type_message_display()} — {self.sender.email}'


class MembreEquipe(models.Model):
    """Entrepreneur ajouté à l'équipe d'une SAEI."""

    saei = models.ForeignKey(SaeiProfile, on_delete=models.CASCADE, related_name='membres')
    entrepreneur = models.ForeignKey(
        EntrepreneurProfile, on_delete=models.CASCADE, related_name='equipes'
    )
    role = models.CharField(max_length=120, blank=True, verbose_name='Rôle dans l’équipe')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = [('saei', 'entrepreneur')]
        verbose_name = 'Membre de l’équipe'
        verbose_name_plural = 'Membres de l’équipe'

    def __str__(self):
        return f'{self.entrepreneur} chez {self.saei}'


class Tache(models.Model):
    """Tâche ou formation assignée à un membre de l'équipe."""

    class TypeTache(models.TextChoices):
        TACHE = 'TACHE', 'Tâche'
        FORMATION = 'FORMATION', 'Formation'

    class Statut(models.TextChoices):
        A_FAIRE = 'A_FAIRE', 'À faire'
        EN_COURS = 'EN_COURS', 'En cours'
        TERMINEE = 'TERMINEE', 'Terminée'

    membre = models.ForeignKey(MembreEquipe, on_delete=models.CASCADE, related_name='taches')
    titre = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    type_tache = models.CharField(max_length=20, choices=TypeTache.choices, default=TypeTache.TACHE)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.A_FAIRE)
    date_echeance = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Tâche / formation'
        verbose_name_plural = 'Tâches / formations'

    def __str__(self):
        return self.titre


class EvaluationEquipe(models.Model):
    """Note de 1 à 5 attribuée par un entrepreneur à l'équipe SAEI."""

    saei = models.ForeignKey(SaeiProfile, on_delete=models.CASCADE, related_name='evaluations')
    entrepreneur = models.ForeignKey(
        EntrepreneurProfile, on_delete=models.CASCADE, related_name='evaluations'
    )
    note = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name='Note sur 5'
    )
    commentaire = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        unique_together = [('saei', 'entrepreneur')]
        verbose_name = 'Évaluation de l’équipe'
        verbose_name_plural = 'Évaluations de l’équipe'

    def __str__(self):
        return f'{self.note}/5 — {self.entrepreneur}'
