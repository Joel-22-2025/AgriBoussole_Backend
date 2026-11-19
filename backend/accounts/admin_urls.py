from django.urls import path
from . import views

urlpatterns = [
    # Requêtes SAEI
    path(
        'saei-requests/',
        views.SaeiRequestListView.as_view(),
        name='saei-request-list',
    ),
    path(
        'saei-requests/<int:pk>/approve/',
        views.SaeiRequestApproveView.as_view(),
        name='saei-request-approve',
    ),
    path(
        'saei-requests/<int:pk>/reject/',
        views.SaeiRequestRejectView.as_view(),
        name='saei-request-reject',
    ),
    # Utilisateurs
    path('users/', views.UserListView.as_view(), name='user-list'),
    path(
        'users/<int:pk>/',
        views.UserActivateDeactivateView.as_view(),
        name='user-activate-deactivate',
    ),
    # ADMIN (création/suppression par un admin)
    path('admins/', views.AdminCreateView.as_view(), name='admin-create'),
    path(
        'admins/<int:pk>/',
        views.AdminDeleteView.as_view(),
        name='admin-delete',
    ),
]
