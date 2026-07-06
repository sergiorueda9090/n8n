from django.urls import path
from . import views

app_name = 'landing'

urlpatterns = [
    path('', views.home, name='home'),
    path('agente/', views.agent_dashboard, name='agent_dashboard'),
    path('pago/', views.pago, name='pago'),
    path('api/pago/registrar/', views.pago_registrar, name='pago_registrar'),
    path('kpis/', views.kpi_dashboard, name='kpi_dashboard'),
    path('metricas/', views.metricas_disenador, name='metricas_disenador'),
    path('testing/', views.testing_report, name='testing_report'),
    path('testing/run/', views.run_autotests_now, name='run_autotests'),
    path('testing/run/stream/', views.run_autotests_stream, name='run_autotests_stream'),
    path('api/chat/', views.chat_api, name='chat_api'),
    path('api/chat/reset/', views.chat_reset, name='chat_reset'),
]
