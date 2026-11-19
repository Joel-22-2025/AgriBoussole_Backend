from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from .models import User, Role, Status, EntrepreneurProfile, SaeiProfile, TypeProfil
from .phase import CHOICE_POINTS, QUESTION_IDS
from structures.models import Structure, Pays, Ville
from structures.serializers import StructureAdminReadSerializer


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------
def _normalize_email(value):
    return value.strip().lower()


# ---------------------------------------------------------------------------
# Lecture / profil connecté
# ---------------------------------------------------------------------------
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'phone', 'role',
            'status', 'is_active', 'is_staff', 'date_joined',
        ]
        read_only_fields = fields


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """Mise à jour des seules informations modifiables par l'utilisateur."""

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone']
        extra_kwargs = {
            'first_name': {'required': False, 'allow_blank': True},
            'last_name': {'required': False, 'allow_blank': True},
            'phone': {'required': False, 'allow_blank': True},
        }


class EntrepreneurProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = EntrepreneurProfile
        fields = [
            'pays', 'ville', 'type_profil', 'est_femme', 'est_jeune', 'filiere',
            'photo_profil', 'phase', 'score_phase', 'phase_answers', 'phase_completed_at',
        ]
        read_only_fields = ['phase', 'score_phase', 'phase_answers', 'phase_completed_at']


class PhaseEvaluationSerializer(serializers.Serializer):
    """Valide les 7 réponses du quiz avant calcul côté serveur."""

    answers = serializers.DictField(child=serializers.CharField())

    def validate_answers(self, value):
        expected = set(QUESTION_IDS)
        received = set(value)
        missing = expected - received
        unexpected = received - expected
        if missing or unexpected:
            raise serializers.ValidationError(
                'Répondez exactement aux 7 questions du quiz.'
            )
        for question_id, choice in value.items():
            if choice not in CHOICE_POINTS:
                raise serializers.ValidationError(
                    {question_id: 'Choisissez une réponse A, B, C ou D.'}
                )
        return value


class SaeiProfileSerializer(serializers.ModelSerializer):
    logo = serializers.FileField(source='structure.logo', read_only=True, allow_null=True)
    nom_structure = serializers.CharField(source='structure.nom', read_only=True)
    email_structure = serializers.EmailField(source='structure.email_structure', read_only=True)
    site_web = serializers.URLField(source='structure.site_web', read_only=True)

    class Meta:
        model = SaeiProfile
        fields = [
            'structure', 'nom_structure_demandee', 'nom_structure', 'pays', 'ville',
            'telephone_structure', 'justificatif', 'message', 'logo',
            'email_structure', 'site_web',
        ]
        read_only_fields = ['structure', 'nom_structure_demandee', 'pays']


class MeSerializer(serializers.Serializer):
    user = serializers.SerializerMethodField()
    profile = serializers.SerializerMethodField()

    @extend_schema_field(UserSerializer)
    def get_user(self, obj):
        user = obj if isinstance(obj, User) else getattr(obj, 'user', None)
        return UserSerializer(user).data if user else None

    @extend_schema_field({'type': 'object', 'nullable': True})
    def get_profile(self, obj):
        user = obj if isinstance(obj, User) else getattr(obj, 'user', None)
        if not user:
            return None
        if user.role == Role.ENTREPRENEUR:
            profile = getattr(user, 'entrepreneur_profile', None)
            return EntrepreneurProfileSerializer(profile, context=self.context).data if profile else None
        if user.role == Role.SAEI:
            profile = getattr(user, 'saei_profile', None)
            return SaeiProfileSerializer(profile, context=self.context).data if profile else None
        return None


# ---------------------------------------------------------------------------
# Inscriptions
# ---------------------------------------------------------------------------
class EntrepreneurRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)

    pays = serializers.ChoiceField(choices=Pays.choices)
    ville = serializers.CharField(max_length=100)
    type_profil = serializers.ChoiceField(choices=TypeProfil.choices)
    est_femme = serializers.BooleanField(default=False)
    est_jeune = serializers.BooleanField(default=False)
    filiere = serializers.CharField(max_length=100, required=False, allow_blank=True)
    photo_profil = serializers.FileField(required=False, allow_null=True)

    def validate_email(self, value):
        value = _normalize_email(value)
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Un compte avec cet email existe déjà.')
        return value

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def create(self, validated_data):
        profile_fields = {
            'pays': validated_data.pop('pays'),
            'ville': validated_data.pop('ville'),
            'type_profil': validated_data.pop('type_profil'),
            'est_femme': validated_data.pop('est_femme', False),
            'est_jeune': validated_data.pop('est_jeune', False),
            'filiere': validated_data.pop('filiere', ''),
            'photo_profil': validated_data.pop('photo_profil', None),
        }

        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            phone=validated_data.get('phone', ''),
            role=Role.ENTREPRENEUR,
            status=Status.APPROVED,
        )
        EntrepreneurProfile.objects.create(user=user, **profile_fields)
        return user


class SaeiRegisterSerializer(serializers.Serializer):
    """Inscription d'une structure SAEI.

    Toutes les informations d'identité, de typologie, de services, de publics,
    de stades et de contact sont obligatoires. La structure est créée non
    publiée et sera publiée lors de l'approbation par un administrateur.
    """

    # --- Compte utilisateur ---
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)

    # --- Identité de la structure ---
    nom_structure = serializers.CharField(max_length=200)
    pays = serializers.ChoiceField(choices=Pays.choices)
    ville = serializers.CharField(max_length=100)
    region_departement = serializers.CharField(max_length=100)
    zone_intervention = serializers.CharField(max_length=100)
    acronyme = serializers.CharField(max_length=200)
    statut_juridique = serializers.CharField(max_length=100)

    # --- Typologie ---
    est_incubateur = serializers.BooleanField(default=False)
    est_accelerateur = serializers.BooleanField(default=False)
    est_recherche_innovation = serializers.BooleanField(default=False)
    est_appui_technique = serializers.BooleanField(default=False)
    est_structure_financement = serializers.BooleanField(default=False)
    est_plateforme_reseau = serializers.BooleanField(default=False)

    # --- Services / publics / stades ---
    service = serializers.CharField(max_length=200)
    public_cible = serializers.CharField(max_length=200)
    stade = serializers.CharField(max_length=200)

    # --- Contact ---
    contact_nom = serializers.CharField(max_length=150)
    contact_fonction = serializers.CharField(max_length=150)
    contact_email = serializers.EmailField()
    contact_telephone = serializers.CharField(max_length=30)
    email_structure = serializers.EmailField(required=False, allow_blank=True)
    telephone_structure = serializers.CharField(max_length=30)
    site_web = serializers.URLField(required=False, allow_blank=True)

    # --- Demande ---
    justificatif = serializers.FileField(required=False, allow_null=True)
    logo = serializers.FileField(required=False, allow_null=True)
    message = serializers.CharField(required=False, allow_blank=True)

    TYPOLOGIE_FIELDS = (
        'est_incubateur',
        'est_accelerateur',
        'est_recherche_innovation',
        'est_appui_technique',
        'est_structure_financement',
        'est_plateforme_reseau',
    )

    def validate_email(self, value):
        value = _normalize_email(value)
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Un compte avec cet email existe déjà.')
        return value

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def validate(self, attrs):
        if not any(attrs.get(field) for field in self.TYPOLOGIE_FIELDS):
            raise serializers.ValidationError(
                {'typologie': 'Sélectionnez au moins un type de structure.'}
            )
        return attrs

    def _resolve_ville(self, name):
        name = (name or '').strip()
        ville = Ville.objects.filter(nom__iexact=name).first()
        if ville is None:
            ville = Ville.objects.create(nom=name)
        return ville

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            phone=validated_data.get('phone', ''),
            role=Role.SAEI,
            status=Status.PENDING,
        )

        ville = self._resolve_ville(validated_data['ville'])
        structure = Structure.objects.create(
            nom=validated_data['nom_structure'],
            pays=validated_data['pays'],
            ville_siege=ville,
            region_departement=validated_data['region_departement'],
            zone_intervention=validated_data['zone_intervention'],
            acronyme=validated_data['acronyme'],
            statut_juridique=validated_data['statut_juridique'],
            est_incubateur=validated_data.get('est_incubateur', False),
            est_accelerateur=validated_data.get('est_accelerateur', False),
            est_recherche_innovation=validated_data.get('est_recherche_innovation', False),
            est_appui_technique=validated_data.get('est_appui_technique', False),
            est_structure_financement=validated_data.get('est_structure_financement', False),
            est_plateforme_reseau=validated_data.get('est_plateforme_reseau', False),
            service=validated_data['service'],
            public_cible=validated_data['public_cible'],
            stade=validated_data['stade'],
            contact_nom=validated_data['contact_nom'],
            contact_fonction=validated_data['contact_fonction'],
            contact_email=validated_data['contact_email'],
            contact_telephone=validated_data['contact_telephone'],
            email_structure=validated_data.get('email_structure') or None,
            telephone_structure=validated_data['telephone_structure'],
            site_web=validated_data.get('site_web') or None,
            logo=validated_data.get('logo'),
            est_publiee=False,
        )

        SaeiProfile.objects.create(
            user=user,
            structure=structure,
            nom_structure_demandee=validated_data['nom_structure'],
            pays=validated_data['pays'],
            ville=validated_data['ville'],
            telephone_structure=validated_data['telephone_structure'],
            justificatif=validated_data.get('justificatif'),
            message=validated_data.get('message', ''),
        )

        # Notification à l’administrateur (console backend en dev)
        send_mail(
            subject='Nouvelle demande SAEI en attente de validation',
            message=(
                f"Une nouvelle demande d’accréditation SAEI a été enregistrée.\n"
                f"Utilisateur : {user.email} ({user.first_name} {user.last_name})\n"
                f"Structure : {validated_data['nom_structure']}\n"
                f"Pays : {validated_data['pays']} - Ville : {validated_data['ville']}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.ADMIN_EMAIL],
            fail_silently=True,
        )
        return user


# ---------------------------------------------------------------------------
# Mot de passe
# ---------------------------------------------------------------------------
class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8, write_only=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('L’ancien mot de passe est incorrect.')
        return value

    def validate_new_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()


class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        value = _normalize_email(value)
        if not User.objects.filter(email=value).exists():
            # On ne révèle pas si l’email existe ou pas (sécurité)
            raise serializers.ValidationError("Si ce compte existe, un email de réinitialisation a été envoyé.")
        return value

    def save(self):
        user = User.objects.get(email=self.validated_data['email'])
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        send_mail(
            subject='Réinitialisation de votre mot de passe SAEI Orientation',
            message=(
                f"Bonjour {user.first_name or user.email},\n\n"
                f"Voici votre lien de réinitialisation de mot de passe :\n"
                f"uid={uid}&token={token}\n\n"
                f"Utilisez ces valeurs sur l'endpoint /api/auth/password/reset/confirm/.\n"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
        return user


class PasswordResetConfirmSerializer(serializers.Serializer):
    uidb64 = serializers.CharField(required=True)
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8, write_only=True)

    def validate_new_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def save(self):
        from django.utils.http import urlsafe_base64_decode
        try:
            uid = urlsafe_base64_decode(self.validated_data['uidb64']).decode()
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            raise serializers.ValidationError('Lien de réinitialisation invalide.')

        if not default_token_generator.check_token(user, self.validated_data['token']):
            raise serializers.ValidationError('Token de réinitialisation invalide ou expiré.')

        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


# ---------------------------------------------------------------------------
# Structures
# ---------------------------------------------------------------------------
class StructureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Structure
        fields = ['id', 'nom', 'pays', 'est_publiee']


# ---------------------------------------------------------------------------
# Requêtes SAEI (admin)
# ---------------------------------------------------------------------------
class SaeiRequestSerializer(serializers.ModelSerializer):
    # `id` est l'identifiant de la demande (SaeiProfile) utilisé par
    # /approve/ et /reject/. On expose aussi l'identifiant utilisateur.
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    status = serializers.CharField(source='user.status', read_only=True)
    date_joined = serializers.DateTimeField(source='user.date_joined', read_only=True)
    structure = StructureAdminReadSerializer(read_only=True)

    class Meta:
        model = SaeiProfile
        fields = [
            'id', 'user_id', 'email', 'first_name', 'last_name',
            'nom_structure_demandee', 'pays', 'ville', 'telephone_structure',
            'status', 'date_joined', 'structure', 'justificatif', 'message',
        ]


class SaeiRequestApproveSerializer(serializers.Serializer):
    structure_id = serializers.PrimaryKeyRelatedField(
        queryset=Structure.objects.all(),
        required=False,
        allow_null=True,
    )


class SaeiRequestRejectSerializer(serializers.Serializer):
    motif = serializers.CharField(required=True, allow_blank=False)


# ---------------------------------------------------------------------------
# Utilisateurs (admin)
# ---------------------------------------------------------------------------
class UserAdminSerializer(serializers.ModelSerializer):
    pays = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'phone', 'role',
            'status', 'is_active', 'pays', 'date_joined',
        ]
        read_only_fields = ['id', 'email', 'role', 'date_joined', 'pays']

    def get_pays(self, obj) -> str | None:
        profile = getattr(obj, 'entrepreneur_profile', None) or getattr(obj, 'saei_profile', None)
        return profile.pays if profile else None


class UserActivateSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()


class AdminCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)

    def validate_email(self, value):
        value = _normalize_email(value)
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Un compte avec cet email existe déjà.')
        return value

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def create(self, validated_data):
        return User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role=Role.ADMIN,
            status=Status.APPROVED,
            is_staff=True,
        )
