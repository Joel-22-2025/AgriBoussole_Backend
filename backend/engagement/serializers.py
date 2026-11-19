from django.db.models import Avg, Count
from rest_framework import serializers

from accounts.models import EntrepreneurProfile, SaeiProfile
from .models import (
    Candidature,
    Commentaire,
    Conversation,
    EvaluationEquipe,
    IndicateurPerformance,
    MembreEquipe,
    Message,
    Offre,
    Tache,
)


class UserBriefSerializer(serializers.ModelSerializer):
    class Meta:
        from django.contrib.auth import get_user_model

        model = get_user_model()
        fields = ['id', 'email', 'first_name', 'last_name', 'phone', 'last_login']


class SaeiBriefSerializer(serializers.ModelSerializer):
    nom_structure = serializers.CharField(source='structure.nom', read_only=True)
    structure_id = serializers.IntegerField(read_only=True)
    logo = serializers.FileField(source='structure.logo', read_only=True, allow_null=True)

    class Meta:
        model = SaeiProfile
        fields = [
            'id', 'nom_structure', 'structure_id', 'logo', 'nom_structure_demandee',
            'pays', 'ville', 'telephone_structure',
        ]


class EntrepreneurBriefSerializer(serializers.ModelSerializer):
    user = UserBriefSerializer(read_only=True)
    nom = serializers.SerializerMethodField()
    photo_profil = serializers.FileField(read_only=True, allow_null=True)

    class Meta:
        model = EntrepreneurProfile
        fields = [
            'id', 'user', 'nom', 'pays', 'ville', 'type_profil', 'filiere',
            'phase', 'score_phase', 'photo_profil',
        ]

    def get_nom(self, obj):
        user = obj.user
        return ' '.join([user.first_name, user.last_name]).strip() or user.email


class OffreSerializer(serializers.ModelSerializer):
    saei = SaeiBriefSerializer(read_only=True)
    candidatures_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Offre
        fields = [
            'id', 'saei', 'titre', 'programme', 'description',
            'conditions_eligibilite', 'type_offre', 'date_limite', 'statut',
            'created_at', 'updated_at', 'candidatures_count',
        ]
        read_only_fields = ['statut', 'created_at', 'updated_at', 'candidatures_count']


class CandidatureSerializer(serializers.ModelSerializer):
    offre = OffreSerializer(read_only=True)
    entrepreneur = EntrepreneurBriefSerializer(read_only=True)
    offre_id = serializers.PrimaryKeyRelatedField(
        queryset=Offre.objects.all(), source='offre', write_only=True
    )

    class Meta:
        model = Candidature
        fields = [
            'id', 'offre', 'offre_id', 'entrepreneur', 'message', 'statut', 'created_at'
        ]
        read_only_fields = ['entrepreneur', 'statut', 'created_at']


class CommentaireSerializer(serializers.ModelSerializer):
    auteur = serializers.SerializerMethodField()

    class Meta:
        model = Commentaire
        fields = ['id', 'auteur', 'contenu', 'created_at']
        read_only_fields = ['created_at']

    def get_auteur(self, obj):
        return ' '.join([obj.user.first_name, obj.user.last_name]).strip() or obj.user.email


class IndicateurSerializer(serializers.ModelSerializer):
    saei = SaeiBriefSerializer(read_only=True)
    commentaires = CommentaireSerializer(many=True, read_only=True)
    likes_count = serializers.IntegerField(read_only=True)
    liked_by_me = serializers.SerializerMethodField()

    class Meta:
        model = IndicateurPerformance
        fields = [
            'id', 'saei', 'titre', 'contenu', 'type_media', 'media',
            'created_at', 'likes_count', 'liked_by_me', 'commentaires',
        ]
        read_only_fields = ['created_at', 'likes_count', 'liked_by_me', 'commentaires']

    def get_liked_by_me(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.reactions.filter(user=request.user).exists()


class ConversationSerializer(serializers.ModelSerializer):
    entrepreneur = EntrepreneurBriefSerializer(read_only=True)
    saei = SaeiBriefSerializer(read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            'id', 'entrepreneur', 'saei', 'sujet', 'created_at', 'updated_at',
            'last_message', 'unread_count',
        ]

    def get_last_message(self, obj):
        message = obj.messages.order_by('-created_at').first()
        return MessageSerializer(message, context=self.context).data if message else None

    def get_unread_count(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return 0
        return obj.messages.filter(is_read=False).exclude(sender=request.user).count()


class MessageSerializer(serializers.ModelSerializer):
    sender_email = serializers.EmailField(source='sender.email', read_only=True)
    sender_name = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            'id', 'conversation', 'sender', 'sender_email', 'sender_name',
            'content', 'type_message', 'is_read', 'created_at', 'is_mine',
        ]
        read_only_fields = [
            'conversation', 'sender', 'sender_email', 'sender_name', 'type_message',
            'is_read', 'created_at', 'is_mine',
        ]

    def get_sender_name(self, obj):
        return ' '.join([obj.sender.first_name, obj.sender.last_name]).strip() or obj.sender.email

    def get_is_mine(self, obj):
        request = self.context.get('request')
        return bool(request and request.user.is_authenticated and obj.sender_id == request.user.id)


class MembreEquipeSerializer(serializers.ModelSerializer):
    entrepreneur = EntrepreneurBriefSerializer(read_only=True)
    entrepreneur_id = serializers.PrimaryKeyRelatedField(
        queryset=EntrepreneurProfile.objects.all(), source='entrepreneur', write_only=True
    )
    note_moyenne = serializers.SerializerMethodField()
    taches_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = MembreEquipe
        fields = [
            'id', 'entrepreneur', 'entrepreneur_id', 'role', 'created_at',
            'note_moyenne', 'taches_count',
        ]
        read_only_fields = ['created_at', 'note_moyenne', 'taches_count']

    def get_note_moyenne(self, obj):
        moyenne = obj.saei.evaluations.filter(entrepreneur=obj.entrepreneur).aggregate(
            moyenne=Avg('note')
        )['moyenne']
        return round(moyenne, 1) if moyenne is not None else None


class TacheSerializer(serializers.ModelSerializer):
    membre = serializers.PrimaryKeyRelatedField(queryset=MembreEquipe.objects.all())
    membre_detail = serializers.SerializerMethodField()

    class Meta:
        model = Tache
        fields = [
            'id', 'membre', 'membre_detail', 'titre', 'description', 'type_tache',
            'statut', 'date_echeance', 'created_at',
        ]
        read_only_fields = ['created_at']

    def get_membre_detail(self, obj):
        return {
            'id': obj.membre_id,
            'entrepreneur': EntrepreneurBriefSerializer(obj.membre.entrepreneur).data,
        }


class EvaluationEquipeSerializer(serializers.ModelSerializer):
    entrepreneur = EntrepreneurBriefSerializer(read_only=True)
    saei = SaeiBriefSerializer(read_only=True)
    saei_id = serializers.PrimaryKeyRelatedField(
        queryset=SaeiProfile.objects.all(), source='saei', write_only=True
    )

    class Meta:
        model = EvaluationEquipe
        fields = [
            'id', 'saei', 'saei_id', 'entrepreneur', 'note', 'commentaire',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class SaeiDashboardSerializer(serializers.Serializer):
    entrepreneurs = serializers.IntegerField()
    entrepreneurs_connectes = serializers.IntegerField()
    offres = serializers.IntegerField()
    candidatures = serializers.IntegerField()
    indicateurs = serializers.IntegerField()
    messages_non_lus = serializers.IntegerField()
    note_moyenne = serializers.FloatField(allow_null=True)
    structure = SaeiBriefSerializer()
