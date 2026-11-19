from django.contrib import admin
from .models import User, EntrepreneurProfile, SaeiProfile


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = [
        'email', 'first_name', 'last_name', 'role', 'status',
        'is_active', 'is_staff', 'date_joined',
    ]
    list_filter = ['role', 'status', 'is_active', 'is_staff']
    search_fields = ['email', 'first_name', 'last_name']
    ordering = ['-date_joined']
    readonly_fields = ['date_joined', 'approved_at']


@admin.register(EntrepreneurProfile)
class EntrepreneurProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'pays', 'ville', 'type_profil', 'est_femme', 'est_jeune', 'filiere']
    list_filter = ['pays', 'type_profil', 'est_femme', 'est_jeune']
    search_fields = ['user__email', 'ville', 'filiere']


@admin.register(SaeiProfile)
class SaeiProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'nom_structure_demandee', 'pays', 'ville', 'telephone_structure']
    list_filter = ['pays', 'ville']
    search_fields = ['user__email', 'nom_structure_demandee', 'ville']
