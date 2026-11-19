from django.urls import path
from . import views

urlpatterns = [
    path('structures/', views.StructureListView.as_view(), name='structure-list'),
    path('structures/<int:pk>/', views.StructureDetailView.as_view(), name='structure-detail'),
    path('villes/', views.VilleListView.as_view(), name='ville-list'),
    path(
        'publics-cibles/',
        views.PublicCibleListView.as_view(),
        name='public-cible-list',
    ),
    path('saei/ma-structure/', views.SaeiMaStructureView.as_view(), name='saei-ma-structure'),
]
