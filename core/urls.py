from django.urls import path
from . import views

urlpatterns = [
    # Menu Principal (Hub)
    path('', views.index, name='index'),

    # Nova Tela de Dashboard (Índices)
    path('indices/', views.dashboard_clinico, name='indices'),  # Nova View

    # API de Dados (Atualizada)
    path('api/dashboard', views.api_dashboard, name='api_dashboard'),

    # ... (mantenha as rotas de login, pacientes, atendimento, usuarios, medicamentos) ...
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('trocar_senha/', views.trocar_senha, name='trocar_senha'),
    path('pacientes/', views.gestao_pacientes, name='gestao_pacientes'),
    path('paciente/salvar', views.salvar_paciente, name='salvar_paciente'),
    path('api/paciente/<int:id>/', views.api_paciente, name='api_paciente'),
    path('atendimento/', views.atendimento_hub, name='atendimento_hub'),
    path('atendimento/multi/<int:paciente_id>/', views.atendimento_multidisciplinar, name='atendimento_multidisciplinar'),
    path('atendimento/prevent/<int:paciente_id>/', views.atendimento_prevent, name='atendimento_prevent'),
    path('usuarios/', views.gestao_usuarios, name='gestao_usuarios'),
    path('usuario/salvar', views.salvar_usuario, name='salvar_usuario'),
    path('medicamentos/', views.gestao_medicamentos, name='gestao_medicamentos'),
    path('medicamento/salvar', views.salvar_medicamento, name='salvar_medicamento'),
    path('api/usuario/<int:id>/', views.api_usuario, name='api_usuario'),
    path('paciente/alta/<int:id>/', views.gerar_alta, name='gerar_alta'),
]