from datetime import date
from decimal import Decimal
from django.db import models
from django.core.validators import EmailValidator
from django.utils.translation import gettext_lazy as _


class Pays(models.TextChoices):
    BENIN = 'BJ', _('Bénin')
    SENEGAL = 'SN', _('Sénégal')
    COTE_DIVOIRE = 'CI', _('Côte d’Ivoire')


class Ville(models.Model):
    """Ville : siège ou antenne de la structure."""
    nom = models.CharField(max_length=200, verbose_name='Nom de la ville')
    region = models.CharField(max_length=100, blank=True, verbose_name='Région')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    class Meta:
        unique_together = [('nom',)]
        verbose_name = 'Ville'
        verbose_name_plural = 'Villes'

    def __str__(self):
        return self.nom


class Structure(models.Model):
    """Structure d'accompagnement (SAEI) au Bénin, Sénégal ou Côte d'Ivoire."""

    nom = models.CharField(max_length=200, verbose_name='Nom de la structure')
    logo = models.FileField(
        upload_to='saei/logos/',
        null=True,
        blank=True,
        verbose_name='Logo de la structure',
    )
    pays = models.CharField(max_length=2, choices=Pays.choices, verbose_name='Pays')
    ville_siege = models.ForeignKey(
        Ville,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='headquarters',
        verbose_name='Ville du siège',
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    service = models.CharField(max_length=200, blank=True, verbose_name='Service')
    public_cible = models.CharField(max_length=200, blank=True, verbose_name='Public cible')
    stade = models.CharField(max_length=200, blank=True, verbose_name='Stade')
    besoin_couvert = models.CharField(max_length=200, blank=True, verbose_name='Besoin couvert')
    typologie = models.CharField(
        max_length=120,
        default='incubateur',
        help_text='Incubateur | Accélérateur | Recherche innovation | Appui technique | Financement | Plateforme réseau',
    )
    specialisation = models.CharField(
        max_length=50,
        default='generaliste',
        choices=[('specialiste', 'Specialiste'), ('generaliste', 'Generaliste')],
    )
    zone_intervention = models.CharField(max_length=100, blank=True, verbose_name="Zone d'intervention")
    site_web = models.URLField(blank=True, null=True, verbose_name='Site web')
    email_structure = models.EmailField(blank=True, null=True, verbose_name='Email structure')
    telephone_structure = models.CharField(max_length=30, blank=True, verbose_name='Téléphone structure')
    contact_nom = models.CharField(max_length=150, blank=True, verbose_name='Contact nom')
    contact_fonction = models.CharField(max_length=150, blank=True, verbose_name='Contact fonction')
    contact_email = models.EmailField(blank=True, null=True, verbose_name='Contact email')
    contact_telephone = models.CharField(max_length=30, blank=True, verbose_name='Contact téléphone')
    est_incubateur = models.BooleanField(default=False, verbose_name='Est incubateur')
    est_accelerateur = models.BooleanField(default=False, verbose_name='Est accélérateur')
    est_recherche_innovation = models.BooleanField(default=False, verbose_name='Est recherche innovation')
    est_appui_technique = models.BooleanField(default=False, verbose_name='Est appui technique')
    est_structure_financement = models.BooleanField(default=False, verbose_name='Est structure de financement')
    est_plateforme_reseau = models.BooleanField(default=False, verbose_name='Est plateforme réseau')
    region_departement = models.CharField(max_length=100, blank=True, verbose_name='Region département')
    acronyme = models.CharField(max_length=200, blank=True, verbose_name='Acronyme')
    statut_juridique = models.CharField(max_length=100, blank=True, verbose_name='Statut juridique')
    score_pertinence = models.PositiveIntegerField(default=0, verbose_name='Score pertinence')
    source = models.CharField(
        max_length=20,
        choices=[
            ('enquetee', 'Enquetee'),
            ('revue_documentaire', 'Revue documentaire'),
        ],
        default='enquetee',
        verbose_name='Source',
    )
    est_publiee = models.BooleanField(default=True, verbose_name='Publiée')
    date_maj = models.DateField(null=True, blank=True, verbose_name='Date maje')

    class Meta:
        ordering = ['pays', 'nom']
        unique_together = [('pays', 'nom')]

    def __str__(self):
        return self.nom
