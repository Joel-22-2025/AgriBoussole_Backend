import re
import unicodedata

from django.db.models import Q
from rest_framework import generics
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Role
from accounts.permissions import IsAdmin, IsApprovedSaei
from .models import Pays, Structure, Ville
from .serializers import StructureSerializer, StructurePublicSerializer, VilleSerializer


def _is_admin(user):
    return bool(
        user and user.is_authenticated
        and user.role == Role.ADMIN
    )


def _clean(value):
    """Minuscules, sans accents ni ponctuation (comparaison des libellés de pays)."""
    if value is None:
        return ''
    ascii_text = (
        unicodedata.normalize('NFKD', str(value))
        .encode('ascii', 'ignore')
        .decode('ascii')
    )
    return ' '.join(ascii_text.lower().split())


def _param(query_params, *names):
    """Lit le premier paramètre GET non vide parmi plusieurs alias."""
    for name in names:
        value = query_params.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


_PAYS_ALIASES = {
    'bj': Pays.BENIN,
    'benin': Pays.BENIN,
    'sn': Pays.SENEGAL,
    'senegal': Pays.SENEGAL,
    'ci': Pays.COTE_DIVOIRE,
    'cote d ivoire': Pays.COTE_DIVOIRE,
    'cote divoire': Pays.COTE_DIVOIRE,
}


def _pays_value(value):
    """Accepte le code ('BJ') ou le libellé ('Bénin') dans le filtre pays."""
    return _PAYS_ALIASES.get(_clean(value), value)


def _filter_structures(queryset, query_params):
    """Filtre dynamique de l'annuaire : recherche plein texte + selects."""
    search = _param(query_params, 'search', 'q')
    if search:
        queryset = queryset.filter(
            Q(nom__icontains=search)
            | Q(acronyme__icontains=search)
            | Q(service__icontains=search)
            | Q(public_cible__icontains=search)
            | Q(stade__icontains=search)
            | Q(besoin_couvert__icontains=search)
            | Q(typologie__icontains=search)
            | Q(zone_intervention__icontains=search)
            | Q(region_departement__icontains=search)
            | Q(ville_siege__nom__icontains=search)
        )

    pays = _param(query_params, 'pays', 'Pays')
    if pays:
        queryset = queryset.filter(pays__icontains=_pays_value(pays))

    ville = _param(query_params, 'ville', 'Ville', 'ville_siege')
    if ville:
        queryset = queryset.filter(ville_siege__nom__icontains=ville)

    typologie = _param(query_params, 'typologie', 'Typologie')
    if typologie:
        queryset = queryset.filter(typologie__icontains=typologie)

    cible = _param(query_params, 'cible', 'public_cible', 'PublicCible')
    if cible:
        queryset = queryset.filter(public_cible__icontains=cible)

    stade = _param(query_params, 'stade', 'Stade')
    if stade:
        queryset = queryset.filter(stade__icontains=stade)

    return queryset


class StructureListView(generics.ListCreateAPIView):
    """GET public (structures publiées, filtrables) / POST réservé aux administrateurs."""

    def get_queryset(self):
        queryset = Structure.objects.select_related('ville_siege').all()
        if not _is_admin(self.request.user):
            queryset = queryset.filter(est_publiee=True)
        return _filter_structures(queryset, self.request.query_params)

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdmin()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return StructureSerializer
        return StructurePublicSerializer


class StructureDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET public / PATCH, PUT, DELETE réservés aux administrateurs."""

    def get_queryset(self):
        queryset = Structure.objects.select_related('ville_siege').all()
        if not _is_admin(self.request.user):
            queryset = queryset.filter(est_publiee=True)
        return queryset

    def get_permissions(self):
        if self.request.method in ('PUT', 'PATCH', 'DELETE'):
            return [IsAdmin()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return StructureSerializer
        return StructurePublicSerializer


class VilleListView(generics.ListAPIView):
    """Villes de référence, filtrables par pays puis par région/département."""

    serializer_class = VilleSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = Ville.objects.all().order_by('region', 'nom')
        pays = self.request.query_params.get('pays', '').strip()
        region = self.request.query_params.get('region', '').strip()
        if pays:
            queryset = queryset.filter(headquarters__pays=pays)
        if region:
            queryset = queryset.filter(region__iexact=region)
        return queryset.distinct()


class PublicCibleListView(APIView):
    """Publics cibles distincts relevés dans la base des structures."""

    permission_classes = [AllowAny]

    def get(self, request):
        values = set()
        raw_values = Structure.objects.exclude(public_cible='').values_list(
            'public_cible', flat=True
        )
        for raw in raw_values:
            for item in re.split(r'[;,/\n]+', raw):
                label = item.strip()
                if label:
                    values.add(label)
        ordered = sorted(
            values,
            key=lambda value: unicodedata.normalize('NFD', value).casefold(),
        )
        return Response(ordered)


class SaeiMaStructureView(generics.RetrieveUpdateAPIView):
    """Un SAEI approuvé peut consulter et modifier sa propre structure."""

    serializer_class = StructureSerializer
    permission_classes = [IsApprovedSaei]

    def get_object(self):
        profile = getattr(self.request.user, 'saei_profile', None)
        if profile is None or profile.structure is None:
            raise NotFound("Aucune structure rattachée à ce compte SAEI.")
        return profile.structure
