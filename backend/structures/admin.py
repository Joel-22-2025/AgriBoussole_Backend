from django.contrib import admin
from .models import Structure


@admin.register(Structure)
class StructureAdmin(admin.ModelAdmin):
    list_display = ['nom', 'pays', 'est_publiee']
    list_filter = ['pays', 'est_publiee']
    search_fields = ['nom']
