from django.urls import path
from . import views

app_name = 'landing'

urlpatterns = [
    path('', views.home, name='home'),
    path('agente/', views.agent_dashboard, name='agent_dashboard'),
    path('api/chat/', views.chat_api, name='chat_api'),
]
