from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import EntrepreneurProfile, SaeiProfile
from accounts.permissions import IsApprovedSaei, IsEntrepreneur
from structures.models import Structure
from .models import (
    Candidature,
    Commentaire,
    Conversation,
    EvaluationEquipe,
    IndicateurPerformance,
    MembreEquipe,
    Message,
    Offre,
    Reaction,
    Tache,
)
from .serializers import (
    CandidatureSerializer,
    CommentaireSerializer,
    ConversationSerializer,
    EntrepreneurBriefSerializer,
    EvaluationEquipeSerializer,
    IndicateurSerializer,
    MembreEquipeSerializer,
    MessageSerializer,
    OffreSerializer,
    SaeiDashboardSerializer,
    TacheSerializer,
)


def _saei(user):
    profile = getattr(user, 'saei_profile', None)
    if profile is None:
        raise PermissionDenied('Ce compte n’est pas une structure SAEI.')
    return profile


def _entrepreneur(user):
    profile = getattr(user, 'entrepreneur_profile', None)
    if profile is None:
        raise PermissionDenied('Ce compte n’est pas un entrepreneur.')
    return profile


def _notify(subject, message, recipients):
    recipients = [email for email in recipients if email]
    if recipients:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=True,
        )


# ---------------------------------------------------------------------------
# Tableau de bord SAEI
# ---------------------------------------------------------------------------
class SaeiDashboardView(APIView):
    permission_classes = [IsApprovedSaei]

    def get(self, request):
        saei = _saei(request.user)
        payload = {
            'entrepreneurs': EntrepreneurProfile.objects.count(),
            'entrepreneurs_connectes': EntrepreneurProfile.objects.filter(
                user__last_login__isnull=False
            ).count(),
            'offres': Offre.objects.filter(saei=saei).count(),
            'candidatures': Candidature.objects.filter(offre__saei=saei).count(),
            'indicateurs': IndicateurPerformance.objects.filter(saei=saei).count(),
            'messages_non_lus': Message.objects.filter(
                conversation__saei=saei, is_read=False
            ).exclude(sender=request.user).count(),
            'note_moyenne': (
                EvaluationEquipe.objects.filter(saei=saei).aggregate(moyenne=Avg('note'))[
                    'moyenne'
                ]
            ),
            'structure': saei,
        }
        return Response(SaeiDashboardSerializer(payload).data)


class SaeiEntrepreneursView(generics.ListAPIView):
    serializer_class = EntrepreneurBriefSerializer
    permission_classes = [IsApprovedSaei]

    def get_queryset(self):
        queryset = EntrepreneurProfile.objects.select_related('user').all()
        if self.request.query_params.get('connectes') == 'true':
            queryset = queryset.filter(user__last_login__isnull=False)
        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
                | Q(user__email__icontains=search)
                | Q(ville__icontains=search)
            )
        return queryset.order_by('-user__last_login', '-user__date_joined')


class SaeiMessageView(APIView):
    """Notification personnelle envoyée par une SAEI à un entrepreneur."""

    permission_classes = [IsApprovedSaei]

    def post(self, request):
        saei = _saei(request.user)
        entrepreneur = get_object_or_404(
            EntrepreneurProfile, pk=request.data.get('entrepreneur_id')
        )
        content = (request.data.get('content') or '').strip()
        if not content:
            raise ValidationError({'content': 'Le message ne peut pas être vide.'})

        conversation, _ = Conversation.objects.get_or_create(
            entrepreneur=entrepreneur, saei=saei, sujet='Notification'
        )
        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            content=content,
            type_message=Message.TypeMessage.NOTIFICATION,
        )
        _notify(
            'AgriBoussole — nouveau message de votre structure accompagnante',
            f'Bonjour {entrepreneur.user.first_name or entrepreneur.user.email},\n\n'
            f'{saei.nom_structure_demandee} vous a envoyé un message :\n\n{content}\n\n'
            'Connectez-vous à AgriBoussole pour y répondre.',
            [entrepreneur.user.email],
        )
        return Response(MessageSerializer(message, context={'request': request}).data, status=201)


# ---------------------------------------------------------------------------
# Offres et candidatures
# ---------------------------------------------------------------------------
class OffreListCreateView(generics.ListCreateAPIView):
    serializer_class = OffreSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsApprovedSaei()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = Offre.objects.select_related('saei', 'saei__structure').annotate(
            candidatures_count=Count('candidatures')
        ).order_by('-created_at')
        user = self.request.user
        if getattr(user, 'role', None) == 'SAEI' and hasattr(user, 'saei_profile'):
            return queryset.filter(saei=user.saei_profile)
        return queryset.filter(statut=Offre.Statut.PUBLIEE)

    def perform_create(self, serializer):
        serializer.save(saei=_saei(self.request.user))


class OffreDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = OffreSerializer

    def get_permissions(self):
        if self.request.method in ('PUT', 'PATCH', 'DELETE'):
            return [IsApprovedSaei()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = Offre.objects.select_related('saei', 'saei__structure').annotate(
            candidatures_count=Count('candidatures')
        )
        user = self.request.user
        if self.request.method in ('PUT', 'PATCH', 'DELETE'):
            return queryset.filter(saei=_saei(user))
        if getattr(user, 'role', None) == 'SAEI' and hasattr(user, 'saei_profile'):
            return queryset.filter(saei=user.saei_profile)
        return queryset.filter(statut=Offre.Statut.PUBLIEE)


class CandidatureListCreateView(generics.ListCreateAPIView):
    serializer_class = CandidatureSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsEntrepreneur()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = Candidature.objects.select_related(
            'offre', 'offre__saei', 'entrepreneur', 'entrepreneur__user'
        )
        user = self.request.user
        if getattr(user, 'role', None) == 'ENTREPRENEUR' and hasattr(user, 'entrepreneur_profile'):
            return queryset.filter(entrepreneur=user.entrepreneur_profile)
        if getattr(user, 'role', None) == 'SAEI' and hasattr(user, 'saei_profile'):
            return queryset.filter(offre__saei=user.saei_profile)
        return queryset.none()

    def perform_create(self, serializer):
        entrepreneur = _entrepreneur(self.request.user)
        offre = serializer.validated_data['offre']
        if offre.statut != Offre.Statut.PUBLIEE:
            raise ValidationError({'offre': 'Cette offre n’est plus ouverte aux candidatures.'})
        candidature = serializer.save(entrepreneur=entrepreneur)
        _notify(
            'AgriBoussole — nouvelle candidature',
            f'{entrepreneur.user.email} a postulé à l’offre « {offre.titre} ».',
            [
                offre.saei.user.email,
                offre.saei.structure.contact_email if offre.saei.structure else None,
            ],
        )
        _notify(
            'AgriBoussole — candidature envoyée',
            f'Votre candidature à l’offre « {offre.titre} » a bien été envoyée.',
            [entrepreneur.user.email],
        )
        return candidature


class CandidatureStatusView(APIView):
    permission_classes = [IsApprovedSaei]

    def patch(self, request, pk):
        candidature = get_object_or_404(
            Candidature, pk=pk, offre__saei=_saei(request.user)
        )
        new_status = request.data.get('statut')
        if new_status not in Candidature.Statut.values:
            raise ValidationError({'statut': 'Statut invalide.'})
        candidature.statut = new_status
        candidature.save(update_fields=['statut'])
        return Response(CandidatureSerializer(candidature, context={'request': request}).data)


# ---------------------------------------------------------------------------
# Indicateurs de performance, likes et commentaires
# ---------------------------------------------------------------------------
class IndicateurListCreateView(generics.ListCreateAPIView):
    serializer_class = IndicateurSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsApprovedSaei()]
        return [IsAuthenticated()]

    def get_queryset(self):
        return (
            IndicateurPerformance.objects.select_related('saei', 'saei__structure')
            .prefetch_related('commentaires__user', 'reactions')
            .annotate(likes_count=Count('reactions', distinct=True))
            .order_by('-created_at')
        )

    def perform_create(self, serializer):
        serializer.save(saei=_saei(self.request.user))


class IndicateurLikeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        indicateur = get_object_or_404(IndicateurPerformance, pk=pk)
        reaction = Reaction.objects.filter(indicateur=indicateur, user=request.user).first()
        if reaction:
            reaction.delete()
            liked = False
        else:
            Reaction.objects.create(indicateur=indicateur, user=request.user)
            liked = True
        likes_count = indicateur.reactions.count()
        return Response({'liked': liked, 'likes_count': likes_count})


class CommentaireListCreateView(generics.ListCreateAPIView):
    serializer_class = CommentaireSerializer

    def get_queryset(self):
        return Commentaire.objects.filter(indicateur_id=self.kwargs['indicateur_id']).select_related(
            'user'
        )

    def perform_create(self, serializer):
        indicateur = get_object_or_404(IndicateurPerformance, pk=self.kwargs['indicateur_id'])
        serializer.save(indicateur=indicateur, user=self.request.user)


# ---------------------------------------------------------------------------
# Équipe, tâches et évaluations
# ---------------------------------------------------------------------------
class TeamListCreateView(generics.ListCreateAPIView):
    serializer_class = MembreEquipeSerializer
    permission_classes = [IsApprovedSaei]

    def get_queryset(self):
        return (
            MembreEquipe.objects.filter(saei=_saei(self.request.user))
            .select_related('entrepreneur', 'entrepreneur__user')
            .annotate(taches_count=Count('taches'))
        )

    def perform_create(self, serializer):
        serializer.save(saei=_saei(self.request.user))


class TeamDetailView(generics.DestroyAPIView):
    permission_classes = [IsApprovedSaei]

    def get_queryset(self):
        return MembreEquipe.objects.filter(saei=_saei(self.request.user))


class TacheListCreateView(generics.ListCreateAPIView):
    serializer_class = TacheSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Tache.objects.select_related(
            'membre', 'membre__entrepreneur', 'membre__entrepreneur__user'
        )
        if getattr(user, 'role', None) == 'SAEI' and hasattr(user, 'saei_profile'):
            return queryset.filter(membre__saei=user.saei_profile)
        if getattr(user, 'role', None) == 'ENTREPRENEUR' and hasattr(user, 'entrepreneur_profile'):
            return queryset.filter(membre__entrepreneur=user.entrepreneur_profile)
        return queryset.none()

    def perform_create(self, serializer):
        membre = serializer.validated_data['membre']
        if membre.saei_id != _saei(self.request.user).id:
            raise PermissionDenied('Ce membre n’appartient pas à votre équipe.')
        serializer.save()


class TacheStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        tache = get_object_or_404(Tache, pk=pk)
        user = request.user
        is_owner = (
            getattr(user, 'role', None) == 'SAEI'
            and hasattr(user, 'saei_profile')
            and tache.membre.saei_id == user.saei_profile.id
        )
        is_assigned = (
            getattr(user, 'role', None) == 'ENTREPRENEUR'
            and hasattr(user, 'entrepreneur_profile')
            and tache.membre.entrepreneur_id == user.entrepreneur_profile.id
        )
        if not (is_owner or is_assigned):
            raise PermissionDenied('Vous ne pouvez pas modifier cette tâche.')
        statut = request.data.get('statut')
        if statut not in Tache.Statut.values:
            raise ValidationError({'statut': 'Statut invalide.'})
        tache.statut = statut
        tache.save(update_fields=['statut'])
        return Response(TacheSerializer(tache, context={'request': request}).data)


class EvaluationListCreateView(generics.ListCreateAPIView):
    serializer_class = EvaluationEquipeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = EvaluationEquipe.objects.select_related(
            'saei', 'saei__structure', 'entrepreneur', 'entrepreneur__user'
        )
        if getattr(user, 'role', None) == 'SAEI' and hasattr(user, 'saei_profile'):
            return queryset.filter(saei=user.saei_profile)
        if getattr(user, 'role', None) == 'ENTREPRENEUR' and hasattr(user, 'entrepreneur_profile'):
            return queryset.filter(entrepreneur=user.entrepreneur_profile)
        return queryset.none()

    def perform_create(self, serializer):
        entrepreneur = _entrepreneur(self.request.user)
        saei = serializer.validated_data['saei']
        if not MembreEquipe.objects.filter(saei=saei, entrepreneur=entrepreneur).exists():
            raise ValidationError(
                {'saei': 'Vous devez être membre de l’équipe pour l’évaluer.'}
            )
        serializer.save(entrepreneur=entrepreneur)


class EvaluationDetailView(generics.UpdateAPIView):
    serializer_class = EvaluationEquipeSerializer
    permission_classes = [IsEntrepreneur]

    def get_queryset(self):
        return EvaluationEquipe.objects.filter(entrepreneur=_entrepreneur(self.request.user))


# ---------------------------------------------------------------------------
# Messagerie, notifications et demandes d'insertion
# ---------------------------------------------------------------------------
def _conversations_for(user):
    queryset = Conversation.objects.select_related(
        'entrepreneur', 'entrepreneur__user', 'saei', 'saei__structure'
    )
    if getattr(user, 'role', None) == 'SAEI' and hasattr(user, 'saei_profile'):
        return queryset.filter(saei=user.saei_profile)
    if getattr(user, 'role', None) == 'ENTREPRENEUR' and hasattr(user, 'entrepreneur_profile'):
        return queryset.filter(entrepreneur=user.entrepreneur_profile)
    return queryset.none()


def _can_access_conversation(conversation, user):
    return (
        (
            getattr(user, 'role', None) == 'SAEI'
            and hasattr(user, 'saei_profile')
            and conversation.saei_id == user.saei_profile.id
        )
        or (
            getattr(user, 'role', None) == 'ENTREPRENEUR'
            and hasattr(user, 'entrepreneur_profile')
            and conversation.entrepreneur_id == user.entrepreneur_profile.id
        )
    )


class ConversationListView(generics.ListAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return _conversations_for(self.request.user)


class MessageListCreateView(generics.ListCreateAPIView):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def _conversation(self):
        conversation = get_object_or_404(Conversation, pk=self.kwargs['conversation_id'])
        if not _can_access_conversation(conversation, self.request.user):
            raise PermissionDenied('Cette conversation ne vous appartient pas.')
        return conversation

    def get_queryset(self):
        conversation = self._conversation()
        queryset = Message.objects.filter(conversation=conversation).select_related('sender')
        after = self.request.query_params.get('after')
        if after and after.isdigit():
            queryset = queryset.filter(id__gt=int(after))
        # Les messages reçus sont marqués comme lus dès l'ouverture du fil.
        queryset.filter(is_read=False).exclude(sender=self.request.user).update(is_read=True)
        return queryset

    def perform_create(self, serializer):
        conversation = self._conversation()
        serializer.save(
            conversation=conversation,
            sender=self.request.user,
            type_message=Message.TypeMessage.CHAT,
        )


class NotificationListView(generics.ListAPIView):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Message.objects.filter(
            type_message__in=[
                Message.TypeMessage.NOTIFICATION,
                Message.TypeMessage.DEMANDE_INSERTION,
            ]
        ).exclude(sender=user)
        if getattr(user, 'role', None) == 'SAEI' and hasattr(user, 'saei_profile'):
            queryset = queryset.filter(conversation__saei=user.saei_profile)
        elif getattr(user, 'role', None) == 'ENTREPRENEUR' and hasattr(user, 'entrepreneur_profile'):
            queryset = queryset.filter(conversation__entrepreneur=user.entrepreneur_profile)
        else:
            return queryset.none()
        if self.request.query_params.get('unread') == 'true':
            queryset = queryset.filter(is_read=False)
        return queryset.select_related('sender', 'conversation')


class NotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        queryset = Message.objects.exclude(sender=user).filter(is_read=False)
        if getattr(user, 'role', None) == 'SAEI' and hasattr(user, 'saei_profile'):
            queryset = queryset.filter(conversation__saei=user.saei_profile)
        elif getattr(user, 'role', None) == 'ENTREPRENEUR' and hasattr(user, 'entrepreneur_profile'):
            queryset = queryset.filter(conversation__entrepreneur=user.entrepreneur_profile)
        else:
            queryset = queryset.none()
        updated = queryset.update(is_read=True)
        return Response({'updated': updated})


class ContactSaeiView(APIView):
    """Demande d'insertion envoyée depuis la fiche publique d'une structure."""

    permission_classes = [IsEntrepreneur]

    def post(self, request):
        entrepreneur = _entrepreneur(request.user)
        structure = get_object_or_404(Structure, pk=request.data.get('structure_id'))
        saei = SaeiProfile.objects.filter(structure=structure).first()
        if saei is None:
            raise ValidationError(
                {'structure': 'Cette structure ne dispose pas encore d’un espace SAEI actif.'}
            )
        programme = (request.data.get('programme') or '').strip()
        contenu = (request.data.get('message') or '').strip()
        if not programme:
            raise ValidationError({'programme': 'Indiquez le programme ou la filière visée.'})
        if not contenu:
            raise ValidationError({'message': 'Décrivez votre demande en quelques lignes.'})

        sujet = (f"Demande d'insertion — {programme}")[:200]
        conversation, _ = Conversation.objects.get_or_create(
            entrepreneur=entrepreneur, saei=saei, sujet=sujet
        )
        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            content=f"Programme : {programme}\n\n{contenu}",
            type_message=Message.TypeMessage.DEMANDE_INSERTION,
        )

        destinataires = [saei.user.email]
        if structure.contact_email:
            destinataires.append(structure.contact_email)
        if structure.email_structure:
            destinataires.append(structure.email_structure)
        _notify(
            f'AgriBoussole — demande d’insertion : {programme}',
            f'Bonjour {structure.nom},\n\n'
            f'{entrepreneur.user.email} souhaite rejoindre le programme « {programme} ».\n\n'
            f'{contenu}\n\nRépondez depuis la plateforme AgriBoussole.',
            destinataires,
        )
        _notify(
            'AgriBoussole — votre demande a bien été envoyée',
            f'Bonjour {entrepreneur.user.first_name or entrepreneur.user.email},\n\n'
            f'Votre demande d’insertion au programme « {programme} » a été envoyée à '
            f'{structure.nom}. Vous recevrez leur réponse directement sur la plateforme.\n\n'
            f'Message envoyé :\n{contenu}',
            [entrepreneur.user.email],
        )
        return Response(
            MessageSerializer(message, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )
