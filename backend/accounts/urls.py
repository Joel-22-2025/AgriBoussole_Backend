from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

urlpatterns = [
    # Inscriptions
    path(
        'register/entrepreneur/',
        views.RegisterEntrepreneurView.as_view(),
        name='register-entrepreneur',
    ),
    path(
        'register/saei/',
        views.RegisterSaeiView.as_view(),
        name='register-saei',
    ),
    # Connexion / tokens
    path('login/', views.LoginView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    # Mot de passe
    path('password/change/', views.PasswordChangeView.as_view(), name='password-change'),
    path('password/reset/', views.PasswordResetView.as_view(), name='password-reset'),
    path(
        'password/reset/confirm/',
        views.PasswordResetConfirmView.as_view(),
        name='password-reset-confirm',
    ),
    # Profil connecté
    path('me/', views.MeView.as_view(), name='me'),
    # Entrepreneur : quiz d’identification de phase
    path(
        'entrepreneurs/phase/recommandations/',
        views.PhaseRecommendationsView.as_view(),
        name='entrepreneur-phase-recommandations',
    ),
    path(
        'entrepreneurs/phase/',
        views.PhaseEvaluationView.as_view(),
        name='entrepreneur-phase',
    ),
]
