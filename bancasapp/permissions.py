from functools import wraps

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .models import pUsuario


def usuario_e_coordenacao(user):

    if not user.is_authenticated or not user.is_active:
        return False

    if user.is_superuser:
        return True

    return pUsuario.objects.filter(
        usuario=user,
        perfil='COORDENACAO'
    ).exists()


def usuario_e_docente(user):

    if not user.is_authenticated or not user.is_active:
        return False

    return pUsuario.objects.filter(
        usuario=user,
        perfil='DOCENTE'
    ).exists()


def usuario_interno_required(view_func):

    @login_required(login_url='login')
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):

        usuario_permitido = (
            usuario_e_coordenacao(request.user)
            or usuario_e_docente(request.user)
        )

        if usuario_permitido:
            return view_func(
                request,
                *args,
                **kwargs
            )

        messages.error(
            request,
            'Seu usuário não possui um perfil ativo no SGTCC.'
        )

        logout(request)

        return redirect('login')

    return wrapper


def coordenacao_required(view_func):

    @login_required(login_url='login')
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):

        if usuario_e_coordenacao(request.user):
            return view_func(
                request,
                *args,
                **kwargs
            )

        messages.error(
            request,
            'Apenas a Coordenação pode realizar esta operação.'
        )

        return redirect('dashboard')

    return wrapper


def docente_required(view_func):

    @login_required(login_url='login')
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):

        if usuario_e_docente(request.user):
            return view_func(
                request,
                *args,
                **kwargs
            )

        messages.error(
            request,
            'Apenas docentes cadastrados podem realizar esta operação.'
        )

        return redirect('dashboard')

    return wrapper