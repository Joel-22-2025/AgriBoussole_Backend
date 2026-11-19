"""Routes de l'API de l'assistant IA."""

from django.urls import path

from .views import AskAIView

urlpatterns = [
    path('ask/', AskAIView.as_view(), name='ask-ai'),
]
