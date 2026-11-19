from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone

from structures.models import Pays


class Role(models.TextChoices):
    ADMIN = 'ADMIN', 'Administrateur'
    SAEI = 'SAEI', 'SAEI'
    ENTREPRENEUR = 'ENTREPRENEUR', 'Entrepreneur'


class Status(models.TextChoices):
    PENDING = 'PENDING', 'En attente'
    APPROVED = 'APPROVED', 'Approuvé'
    REJECTED = 'REJECTED', 'Rejeté'


class TypeProfil(models.TextChoices):
    INDIVIDUEL = 'individuel', 'Individuel'
    STARTUP = 'startup', 'Startup'
    COOPERATIVE = 'cooperative', 'Coopérative'
    ORGANISATION_PAYSANNE = 'organisation_paysanne', 'Organisation paysanne'
    PME = 'pme', 'PME'
    ETUDIANT = 'etudiant', 'Étudiant'


class Phase(models.TextChoices):
    """Phases de maturité issues du quiz d’identification (score 0 à 21)."""

    IDEATION = 'IDEATION', 'Idéation'
    CREATION = 'CREATION', 'Création'
    INCUBATION = 'INCUBATION', 'Incubation'
    ACCELERATION = 'ACCELERATION', 'Accélération'
    DEVELOPPEMENT = 'DEVELOPPEMENT', 'Développement / Croissance'
    CROISSANCE = 'CROISSANCE', 'Croissance'
    PASSAGE_ECHELLE = 'PASSAGE_ECHELLE', 'Passage à l’échelle'


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('L’adresse email est obligatoire.')
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', Role.ADMIN)
        extra_fields.setdefault('status', Status.APPROVED)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('L\'administrateur doit avoir is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('L\'administrateur doit avoir is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, db_index=True, verbose_name='Email')
    first_name = models.CharField(max_length=150, blank=True, verbose_name='Prénom')
    last_name = models.CharField(max_length=150, blank=True, verbose_name='Nom')
    phone = models.CharField(max_length=30, blank=True, verbose_name='Téléphone')
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.ENTREPRENEUR,
        verbose_name='Rôle',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='Statut',
    )
    is_active = models.BooleanField(default=True, verbose_name='Actif')
    is_staff = models.BooleanField(default=False, verbose_name='Staff')
    date_joined = models.DateTimeField(default=timezone.now, verbose_name='Date d’inscription')
    approved_by = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_users',
        verbose_name='Approuvé par',
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='Approuvé le')
    rejection_reason = models.TextField(blank=True, verbose_name='Motif du rejet')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    class Meta:
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.lower()
        super().save(*args, **kwargs)

    # Propriétés pratiques
    @property
    def is_admin(self):
        return self.role == Role.ADMIN

    @property
    def is_saei(self):
        return self.role == Role.SAEI

    @property
    def is_entrepreneur(self):
        return self.role == Role.ENTREPRENEUR

    def can_approve(self):
        """Seul un ADMIN peut approuver/rejeter une demande SAEI."""
        return self.is_authenticated and self.is_admin

    def can_manage_admins(self):
        """Un ADMIN peut créer/supprimer un autre ADMIN."""
        return self.is_authenticated and self.is_admin


class EntrepreneurProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='entrepreneur_profile',
        verbose_name='Utilisateur',
    )
    pays = models.CharField(max_length=100, choices=Pays.choices, verbose_name='Pays')
    ville = models.CharField(max_length=100, verbose_name='Ville')
    type_profil = models.CharField(
        max_length=30,
        choices=TypeProfil.choices,
        verbose_name='Type de profil',
    )
    est_femme = models.BooleanField(default=False, verbose_name='Est une femme')
    est_jeune = models.BooleanField(default=False, verbose_name='Est un jeune')
    filiere = models.CharField(max_length=100, blank=True, verbose_name='Filière')
    photo_profil = models.FileField(
        upload_to='entrepreneurs/photos/',
        null=True,
        blank=True,
        verbose_name='Photo de profil',
    )

    phase = models.CharField(
        max_length=30,
        choices=Phase.choices,
        blank=True,
        verbose_name='Phase du projet',
    )
    score_phase = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Score du quiz (0-21)'
    )
    phase_answers = models.JSONField(default=dict, blank=True, verbose_name='Réponses au quiz')
    phase_completed_at = models.DateTimeField(
        null=True, blank=True, verbose_name='Quiz réalisé le'
    )

    class Meta:
        verbose_name = 'Profil Entrepreneur'
        verbose_name_plural = 'Profils Entrepreneurs'

    def __str__(self):
        return f"{self.user.email} ({self.pays})"


class SaeiProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='saei_profile',
        verbose_name='Utilisateur',
    )
    structure = models.ForeignKey(
        'structures.Structure',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='saei_profiles',
        verbose_name='Structure rattachée',
    )
    nom_structure_demandee = models.CharField(
        max_length=200, verbose_name='Nom de la structure demandée'
    )
    pays = models.CharField(max_length=100, choices=Pays.choices, verbose_name='Pays')
    ville = models.CharField(max_length=100, verbose_name='Ville')
    telephone_structure = models.CharField(max_length=30, verbose_name='Téléphone structure')
    justificatif = models.FileField(
        upload_to='saei_justificatifs/',
        null=True,
        blank=True,
        verbose_name='Justificatif',
    )
    message = models.TextField(blank=True, verbose_name='Message')

    class Meta:
        verbose_name = 'Profil SAEI'
        verbose_name_plural = 'Profils SAEI'

    def __str__(self):
        return self.nom_structure_demandee
