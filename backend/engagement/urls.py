from django.urls import path

from . import views

urlpatterns = [
    # Tableau de bord et entrepreneurs
    path('saei/dashboard/', views.SaeiDashboardView.as_view(), name='saei-dashboard'),
    path('saei/entrepreneurs/', views.SaeiEntrepreneursView.as_view(), name='saei-entrepreneurs'),
    path('saei/notifier/', views.SaeiMessageView.as_view(), name='saei-notifier'),
    # Offres et candidatures
    path('offres/', views.OffreListCreateView.as_view(), name='offre-list'),
    path('offres/<int:pk>/', views.OffreDetailView.as_view(), name='offre-detail'),
    path('candidatures/', views.CandidatureListCreateView.as_view(), name='candidature-list'),
    path(
        'candidatures/<int:pk>/statut/',
        views.CandidatureStatusView.as_view(),
        name='candidature-statut',
    ),
    # Indicateurs de performance
    path('indicateurs/', views.IndicateurListCreateView.as_view(), name='indicateur-list'),
    path(
        'indicateurs/<int:pk>/like/',
        views.IndicateurLikeView.as_view(),
        name='indicateur-like',
    ),
    path(
        'indicateurs/<int:indicateur_id>/commentaires/',
        views.CommentaireListCreateView.as_view(),
        name='commentaire-list',
    ),
    # Équipe, tâches, évaluations
    path('equipe/', views.TeamListCreateView.as_view(), name='equipe-list'),
    path('equipe/<int:pk>/', views.TeamDetailView.as_view(), name='equipe-detail'),
    path('taches/', views.TacheListCreateView.as_view(), name='tache-list'),
    path('taches/<int:pk>/statut/', views.TacheStatusView.as_view(), name='tache-statut'),
    path('evaluations/', views.EvaluationListCreateView.as_view(), name='evaluation-list'),
    path('evaluations/<int:pk>/', views.EvaluationDetailView.as_view(), name='evaluation-detail'),
    # Messagerie
    path('conversations/', views.ConversationListView.as_view(), name='conversation-list'),
    path(
        'conversations/<int:conversation_id>/messages/',
        views.MessageListCreateView.as_view(),
        name='message-list',
    ),
    path('notifications/', views.NotificationListView.as_view(), name='notification-list'),
    path('notifications/lire/', views.NotificationReadView.as_view(), name='notification-read'),
    path('contact-saei/', views.ContactSaeiView.as_view(), name='contact-saei'),
]
