# core/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario, Paciente, Medicamento, Afericao, AtendimentoMultidisciplinar


# Configuração personalizada para o Usuário
class CustomUserAdmin(UserAdmin):
    model = Usuario
    # Garante que os campos apareçam no formulário do Admin
    fieldsets = UserAdmin.fieldsets + (
        ('Dados Profissionais', {'fields': ('tipo_profissional', 'drt', 'tipo_registro', 'registro_profissional')}),
    )
    # Garante que apareçam na lista (tabela)
    list_display = ['username', 'first_name', 'tipo_profissional', 'registro_profissional', 'is_staff']

admin.site.register(Usuario, CustomUserAdmin)