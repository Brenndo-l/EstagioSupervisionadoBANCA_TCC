from functools import wraps

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .models import pUsuario


def usuario_e_coordenacao(user):
    """
    Verifica se o usuário pertence à Coordenação.

    Durante o desenvolvimento, um superusuário também é
    considerado parte da Coordenação.
    """

    if not user.is_authenticated:
        return False

    return (
        user.is_superuser
        or pUsuario.objects.filter(
            usuario=user,
            perfil='COORDENACAO'
        ).exists()
    )


def usuario_e_docente(user):
    """
    Verifica se o usuário possui o perfil DOCENTE.
    """

    if not user.is_authenticated:
        return False

    return pUsuario.objects.filter(
        usuario=user,
        perfil='DOCENTE'
    ).exists()


def usuario_interno_required(view_func):
    """
    Permite acesso apenas a usuários internos do SGTCC:
    Coordenação ou Docente.
    """

    @login_required(login_url='login')
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):

        usuario_permitido = (
            usuario_e_coordenacao(request.user)
            or usuario_e_docente(request.user)
        )

        if usuario_permitido:
            return view_func(request, *args, **kwargs)

        messages.error(
            request,
            'Seu usuário não possui um perfil ativo no SGTCC.'
        )

        # Encerra a sessão para evitar que o usuário fique preso
        # em um ciclo de redirecionamentos.
        logout(request)

        return redirect('login')

    return wrapper


def coordenacao_required(view_func):
    """
    Permite acesso somente à Coordenação.
    """

    @login_required(login_url='login')
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):

        if usuario_e_coordenacao(request.user):
            return view_func(request, *args, **kwargs)

        messages.error(
            request,
            'Apenas a Coordenação pode realizar esta operação.'
        )

        return redirect('dashboard')

    return wrapper


def docente_required(view_func):
    """
    Permite acesso somente aos docentes cadastrados.
    """

    @login_required(login_url='login')
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):

        if usuario_e_docente(request.user):
            return view_func(request, *args, **kwargs)

        messages.error(
            request,
            'Apenas docentes cadastrados podem solicitar uma banca.'
        )

        return redirect('dashboard')

    return wrapper