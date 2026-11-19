from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from django.db.models import Q

from rest_framework import status, generics
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView, TokenBlacklistView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import User, Role, Status, EntrepreneurProfile, SaeiProfile
from .serializers import (
    EntrepreneurRegisterSerializer,
    EntrepreneurProfileSerializer,
    SaeiRegisterSerializer,
    SaeiProfileSerializer,
    PasswordChangeSerializer,
    PasswordResetSerializer,
    PasswordResetConfirmSerializer,
    MeSerializer,
    UserProfileUpdateSerializer,
    UserSerializer,
    StructureSerializer,
    SaeiRequestSerializer,
    SaeiRequestApproveSerializer,
    SaeiRequestRejectSerializer,
    UserAdminSerializer,
    UserActivateSerializer,
    AdminCreateSerializer,
    PhaseEvaluationSerializer,
)
from .phase import PHASES_BY_KEY, evaluate_answers, phase_response
from .permissions import IsAdmin
from structures.models import Structure
from structures.serializers import StructurePublicSerializer


# ============================================================================
# Authentification publique
# ============================================================================
class RegisterEntrepreneurView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'register'
    serializer_class = EntrepreneurRegisterSerializer

    def post(self, request):
        serializer = EntrepreneurRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                'message': 'Compte entrepreneur créé avec succès.',
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class RegisterSaeiView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'register'
    serializer_class = SaeiRegisterSerializer

    def post(self, request):
        serializer = SaeiRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                'message': (
                    'Demande d’accréditation SAEI enregistrée. Elle est en attente '
                    'de validation par un administrateur.'
                ),
                'status': Status.PENDING,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    throttle_scope = 'login'


class LogoutView(TokenBlacklistView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]


# ============================================================================
# Mot de passe
# ============================================================================
class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PasswordChangeSerializer

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'message': 'Mot de passe modifié avec succès.'})


class PasswordResetView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'password_reset'
    serializer_class = PasswordResetSerializer

    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                'message': (
                    "Si ce compte existe, un email de réinitialisation a été envoyé "
                    "(consultable dans les logs du serveur en développement)."
                )
            },
        )


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'password_reset'
    serializer_class = PasswordResetConfirmSerializer

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'message': 'Mot de passe réinitialisé avec succès.'})


# ============================================================================
# Profil connecté
# ============================================================================
class MeView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MeSerializer

    def get(self, request):
        serializer = MeSerializer(request.user, context={'request': request})
        return Response(serializer.data)

    def patch(self, request):
        user = request.user
        user_serializer = UserProfileUpdateSerializer(user, data=request.data, partial=True)
        user_serializer.is_valid(raise_exception=True)
        user_serializer.save()

        profile_serializer = None
        if user.role == Role.ENTREPRENEUR:
            profile = getattr(user, 'entrepreneur_profile', None)
            if profile is None:
                return Response(
                    {'error': True, 'message': 'Profil entrepreneur introuvable.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            profile_serializer = EntrepreneurProfileSerializer(
                profile, data=request.data, partial=True
            )
        elif user.role == Role.SAEI:
            profile = getattr(user, 'saei_profile', None)
            if profile is None:
                return Response(
                    {'error': True, 'message': 'Profil SAEI introuvable.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            profile_serializer = SaeiProfileSerializer(
                profile, data=request.data, partial=True
            )

        if profile_serializer is not None:
            profile_serializer.is_valid(raise_exception=True)
            profile_serializer.save()

        # Le logo est stocké sur la Structure rattachée au profil SAEI.
        logo = request.FILES.get('logo')
        if (
            user.role == Role.SAEI
            and logo is not None
            and getattr(user, 'saei_profile', None)
            and user.saei_profile.structure
        ):
            structure = user.saei_profile.structure
            structure.logo = logo
            structure.save(update_fields=['logo'])

        return Response(MeSerializer(user, context={'request': request}).data)


# ============================================================================
# Entrepreneur : identification de phase
# ============================================================================
class PhaseEvaluationView(APIView):
    """Quiz d’identification de phase : lecture et enregistrement du résultat."""

    permission_classes = [IsAuthenticated]
    serializer_class = PhaseEvaluationSerializer

    def get(self, request):
        profile = self._get_profile(request.user)
        if profile is None:
            return self._forbidden()
        return Response(phase_response(profile))

    def post(self, request):
        profile = self._get_profile(request.user)
        if profile is None:
            return self._forbidden()

        serializer = PhaseEvaluationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        score, phase = evaluate_answers(serializer.validated_data['answers'])
        with transaction.atomic():
            profile.phase = phase['phase']
            profile.score_phase = score
            profile.phase_answers = serializer.validated_data['answers']
            profile.phase_completed_at = timezone.now()
            profile.save(
                update_fields=[
                    'phase', 'score_phase', 'phase_answers', 'phase_completed_at'
                ]
            )

        payload = phase_response(profile)
        payload['profile'] = EntrepreneurProfileSerializer(profile).data
        return Response(payload)

    @staticmethod
    def _get_profile(user):
        if getattr(user, 'role', None) != Role.ENTREPRENEUR:
            return None
        return getattr(user, 'entrepreneur_profile', None)

    @staticmethod
    def _forbidden():
        return Response(
            {
                'error': True,
                'message': 'Ce quiz est réservé aux comptes entrepreneur.',
            },
            status=status.HTTP_403_FORBIDDEN,
        )


class PhaseRecommendationsView(APIView):
    """Structures publiées proposées automatiquement après le quiz."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if getattr(user, 'role', None) != Role.ENTREPRENEUR:
            return PhaseEvaluationView._forbidden()

        profile = getattr(user, 'entrepreneur_profile', None)
        if profile is None:
            return self._bad_request('Profil entrepreneur introuvable.')
        if not profile.phase:
            return self._bad_request('Réalisez d’abord le quiz d’identification de phase.')

        phase = PHASES_BY_KEY.get(profile.phase)
        stade = phase['stade'] if phase else None
        ville = (profile.ville or '').strip().casefold()

        publications = Structure.objects.filter(
            est_publiee=True
        ).select_related('ville_siege')

        locate = list(publications.filter(pays=profile.pays))
        fallback_all_pays = not locate
        if fallback_all_pays:
            locate = list(publications)

        ranked = []
        for structure in locate:
            score = 0.0
            reasons = []

            if structure.pays == profile.pays:
                score += 4
                reasons.append('Même pays')

            structure_ville = (
                structure.ville_siege.nom if structure.ville_siege_id else ''
            ).strip().casefold()
            if ville and structure_ville == ville:
                score += 5
                reasons.append('Même ville')
            elif ville and ville in structure_ville:
                score += 3
                reasons.append('Ville proche')

            if stade and stade.casefold() in (structure.stade or '').casefold():
                score += 4
                reasons.append('Phase compatible')

            score += min(float(structure.score_pertinence or 0), 5) / 10
            ranked.append((score, structure, reasons))

        ranked.sort(key=lambda item: (-item[0], item[1].nom))

        results = []
        for score, structure, reasons in ranked:
            data = StructurePublicSerializer(structure).data
            data['match_score'] = round(score, 1)
            data['match_reasons'] = reasons
            results.append(data)

        return Response(
            {
                'pays': profile.pays,
                'ville': profile.ville,
                'phase': profile.phase,
                'stade': stade,
                'fallback_all_pays': fallback_all_pays,
                'count': len(results),
                'results': results,
            }
        )

    @staticmethod
    def _bad_request(message):
        return Response(
            {'error': True, 'message': message},
            status=status.HTTP_400_BAD_REQUEST,
        )


# ============================================================================
# Admin : requêtes SAEI
# ============================================================================
class SaeiRequestListView(generics.ListAPIView):
    permission_classes = [IsAdmin]
    serializer_class = SaeiRequestSerializer
    pagination_class = PageNumberPagination

    def get_queryset(self):
        queryset = SaeiProfile.objects.select_related('user', 'structure').all()
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(user__status=status_param)
        pays = self.request.query_params.get('pays')
        if pays:
            queryset = queryset.filter(
                Q(user__entrepreneur_profile__pays=pays)
                | Q(user__saei_profile__pays=pays)
            ).distinct()
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(user__email__icontains=search)
                | Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
                | Q(nom_structure_demandee__icontains=search)
            ).distinct()
        return queryset.order_by('-user__date_joined')


def _notify_saei(user, subject, message):
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )


class SaeiRequestApproveView(APIView):
    permission_classes = [IsAdmin]
    serializer_class = SaeiRequestApproveSerializer

    def post(self, request, pk):
        try:
            profile = SaeiProfile.objects.select_related('user').get(pk=pk)
        except SaeiProfile.DoesNotExist:
            return Response(
                {'error': True, 'message': 'Demande SAEI introuvable.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        user = profile.user
        if user.status != Status.PENDING:
            return Response(
                {'error': True, 'message': 'Cette demande a déjà été traitée.', 'status': user.status},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SaeiRequestApproveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        structure = serializer.validated_data.get('structure_id')

        user.status = Status.APPROVED
        user.approved_by = request.user
        user.approved_at = timezone.now()
        user.rejection_reason = ''
        user.save()

        if structure is not None:
            profile.structure = structure
        if profile.structure is not None:
            profile.structure.est_publiee = True
            profile.structure.save(update_fields=['est_publiee'])
        profile.save()

        _notify_saei(
            user,
            'Votre demande SAEI a été approuvée',
            (
                f"Bonjour {user.first_name or user.email},\n\n"
                f"Votre demande d’accréditation SAEI a été approuvée par un administrateur. "
                f"Vous pouvez désormais vous connecter.\n"
            ),
        )

        return Response(
            {'message': 'Demande SAEI approuvée.', 'status': Status.APPROVED}
        )


class SaeiRequestRejectView(APIView):
    permission_classes = [IsAdmin]
    serializer_class = SaeiRequestRejectSerializer

    def post(self, request, pk):
        try:
            profile = SaeiProfile.objects.select_related('user').get(pk=pk)
        except SaeiProfile.DoesNotExist:
            return Response(
                {'error': True, 'message': 'Demande SAEI introuvable.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        user = profile.user
        if user.status != Status.PENDING:
            return Response(
                {'error': True, 'message': 'Cette demande a déjà été traitée.', 'status': user.status},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SaeiRequestRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        motif = serializer.validated_data['motif']

        user.status = Status.REJECTED
        user.rejection_reason = motif
        user.save()

        if profile.structure is not None:
            profile.structure.est_publiee = False
            profile.structure.save(update_fields=['est_publiee'])

        _notify_saei(
            user,
            'Votre demande SAEI a été rejetée',
            (
                f"Bonjour {user.first_name or user.email},\n\n"
                f"Votre demande d’accréditation SAEI a été rejetée.\n"
                f"Motif : {motif}\n"
            ),
        )

        return Response(
            {'message': 'Demande SAEI rejetée.', 'status': Status.REJECTED, 'motif': motif}
        )


# ============================================================================
# Admin : utilisateurs
# ============================================================================
class UserListView(generics.ListAPIView):
    permission_classes = [IsAdmin]
    serializer_class = UserAdminSerializer
    pagination_class = PageNumberPagination

    def get_queryset(self):
        queryset = User.objects.all().order_by('-date_joined')
        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)
        st = self.request.query_params.get('status')
        if st:
            queryset = queryset.filter(status=st)
        pays = self.request.query_params.get('pays')
        if pays:
            queryset = queryset.filter(
                Q(entrepreneur_profile__pays=pays) | Q(saei_profile__pays=pays)
            ).distinct()
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            ).distinct()
        return queryset


class UserActivateDeactivateView(APIView):
    permission_classes = [IsAdmin]
    serializer_class = UserActivateSerializer

    def patch(self, request, pk):
        try:
            target = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(
                {'error': True, 'message': 'Utilisateur introuvable.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Un admin ne peut pas se désactiver lui-même
        if target.pk == request.user.pk:
            return Response(
                {'error': True, 'message': 'Vous ne pouvez pas modifier votre propre compte.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        is_active = request.data.get('is_active')
        if isinstance(is_active, str):
            is_active = is_active.lower() == 'true'
        if not isinstance(is_active, bool):
            return Response(
                {'error': True, 'message': 'Le champ is_active (booléen) est requis.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target.is_active = is_active
        target.save()
        return Response(
            {
                'message': f"Utilisateur {'activé' if is_active else 'désactivé'} avec succès.",
                'is_active': target.is_active,
            }
        )


# ============================================================================
# Admin : création/suppression d'ADMIN
# ============================================================================
class AdminCreateView(APIView):
    permission_classes = [IsAdmin]
    serializer_class = AdminCreateSerializer

    def post(self, request):
        serializer = AdminCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        admin = serializer.save()
        return Response(
            {
                'message': 'ADMIN créé avec succès.',
                'user': UserSerializer(admin).data,
            },
            status=status.HTTP_201_CREATED,
        )


class AdminDeleteView(APIView):
    permission_classes = [IsAdmin]
    serializer_class = UserSerializer

    def delete(self, request, pk):
        try:
            target = User.objects.get(pk=pk, role=Role.ADMIN)
        except User.DoesNotExist:
            return Response(
                {'error': True, 'message': 'ADMIN introuvable.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Un admin ne peut pas se supprimer lui-même
        if target.pk == request.user.pk:
            return Response(
                {'error': True, 'message': 'Vous ne pouvez pas supprimer votre propre compte.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target.delete()
        return Response({'message': 'ADMIN supprimé avec succès.'}, status=status.HTTP_204_NO_CONTENT)
