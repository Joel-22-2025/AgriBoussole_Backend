from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class SaeiTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Sérialiseur de connexion : ajoute les claims role et status,
    et refuse la connexion d’un SAEI non approuvé (403 + champ status)."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['status'] = user.status
        return token

    def validate(self, attrs):
        data = super().validate(attrs)

        user = self.user
        if user.role == 'SAEI' and user.status != 'APPROVED':
            raise PermissionDenied({
                'status': user.status,
                'detail': (
                    'Votre demande SAEI est en attente de validation '
                    'par un administrateur. Vous ne pouvez pas vous connecter.'
                ),
            })

        return data
