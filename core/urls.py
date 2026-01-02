from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('trocar_senha/', views.trocar_senha, name='trocar_senha'),

    path('api/dashboard', views.api_dashboard, name='api_dashboard'),

    path('pacientes/', views.gestao_pacientes, name='gestao_pacientes'),
    path('paciente/salvar', views.salvar_paciente, name='salvar_paciente'),
    path('api/paciente/<int:id>/', views.api_paciente, name='api_paciente'),

    path('atendimento/', views.atendimento, name='atendimento'),
    path('atendimento/registrar/', views.registrar_afericao, name='registrar_afericao'),

    path('usuarios/', views.gestao_usuarios, name='gestao_usuarios'),
    path('usuario/salvar', views.salvar_usuario, name='salvar_usuario'),
    path('api/usuario/<int:id>/', views.api_usuario, name='api_usuario'),

    path('medicamentos/', views.gestao_medicamentos, name='gestao_medicamentos'),
    path('medicamento/salvar', views.salvar_medicamento, name='salvar_medicamento'),
]