# core/decorators.py

from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps


# Decorador para garantir que apenas o Admin acesse
def admin_only(view_func):
    def wrapper_func(request, *args, **kwargs):
        # Verifica se é superusuário
        if request.user.is_authenticated and request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        else:
            messages.error(request, "Você não tem permissão para acessar esta página.")
            return redirect('index')  # <--- CORREÇÃO: Mudado de 'home' para 'index'
    return wrapper_func

# Decorador para Médicos (e Admin)
def medico_only(view_func):
    def wrapper_func(request, *args, **kwargs):
        if request.user.is_authenticated and (request.user.tipo_profissional == 'MED' or request.user.is_superuser):
            return view_func(request, *args, **kwargs)
        else:
            messages.error(request, "Acesso restrito a Médicos.")
            return redirect('index')
    return wrapper_func

# Decorador para Equipe Multi + Admin
def multi_only(view_func):
    def wrapper_func(request, *args, **kwargs):
        # Lista de profissionais permitidos
        allowed_roles = ['ENF', 'NUT', 'FAR']
        if request.user.is_authenticated and (request.user.tipo_profissional in allowed_roles or request.user.is_superuser):
            return view_func(request, *args, **kwargs)
        else:
            messages.error(request, "Acesso restrito à Equipe Multidisciplinar.")
            return redirect('index')  # <--- CORREÇÃO AQUI TAMBÉM
    return wrapper_func

def health_team(view_func):
    def wrapper_func(request, *args, **kwargs):
        allowed_roles = ['MED', 'ENF', 'NUT', 'FAR']
        if request.user.is_authenticated and (
                request.user.tipo_profissional in allowed_roles or request.user.is_superuser):
            return view_func(request, *args, **kwargs)
        else:
            messages.error(request, "Acesso restrito à Equipe de Profissionais de Saúde.")
            return redirect('index')

    return wrapper_func