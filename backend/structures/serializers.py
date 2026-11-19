from rest_framework import serializers

from .models import Structure, Ville


class VilleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ville
        fields = ['id', 'nom', 'region', 'latitude', 'longitude']


class StructureSerializer(serializers.ModelSerializer):
    """Sérialiseur complet (administration / SAEI) : accepte un nom de ville."""

    ville_siege = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Structure
        fields = '__all__'
        read_only_fields = ['id']

    def _resolve_ville(self, name):
        name = (name or '').strip()
        if not name:
            return None
        ville = Ville.objects.filter(nom__iexact=name).first()
        if ville is None:
            ville = Ville.objects.create(nom=name)
        return ville

    def create(self, validated_data):
        ville_name = validated_data.pop('ville_siege', None)
        structure = Structure(**validated_data)
        structure.ville_siege = self._resolve_ville(ville_name)
        structure.save()
        return structure

    def update(self, instance, validated_data):
        ville_name = validated_data.pop('ville_siege', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if ville_name is not None:
            instance.ville_siege = self._resolve_ville(ville_name)
        instance.save()
        return instance


class StructurePublicSerializer(serializers.ModelSerializer):
    """Sérialiseur public : jamais de champs de contact de personnes."""

    ville_siege = serializers.SerializerMethodField()

    class Meta:
        model = Structure
        fields = [
            'id', 'nom', 'logo', 'pays', 'ville_siege', 'region_departement', 'acronyme',
            'statut_juridique', 'latitude', 'longitude', 'service', 'public_cible',
            'stade', 'besoin_couvert', 'typologie', 'specialisation',
            'zone_intervention', 'site_web', 'email_structure',
            'telephone_structure', 'est_incubateur', 'est_accelerateur',
            'est_recherche_innovation', 'est_appui_technique',
            'est_structure_financement', 'est_plateforme_reseau',
            'score_pertinence', 'source', 'est_publiee', 'date_maj',
        ]

    def get_ville_siege(self, obj) -> str | None:
        return obj.ville_siege.nom if obj.ville_siege_id else None


class StructureAdminReadSerializer(serializers.ModelSerializer):
    """Vue complète (contacts inclus) réservée aux administrateurs."""

    ville_siege = serializers.SerializerMethodField()

    class Meta:
        model = Structure
        fields = '__all__'

    def get_ville_siege(self, obj) -> str | None:
        return obj.ville_siege.nom if obj.ville_siege_id else None
