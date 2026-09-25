"""Utilitários de segurança que não dependem das regras de negócio."""

from dataclasses import dataclass
from datetime import timedelta
from ipaddress import ip_address
from math import ceil

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import TentativaAcesso


@dataclass(frozen=True)
class ResultadoLimite:
    permitido: bool
    tentar_novamente_em: int = 0


def obter_ip_cliente(request):
    """
    Obtém um IP validado.

    X-Forwarded-For somente é aceito quando o administrador declara que o
    aplicativo está atrás de um proxy confiável que sobrescreve esse header.
    """

    valor = request.META.get('REMOTE_ADDR', '')

    if settings.SGTCC_TRUST_PROXY_CLIENT_IP:
        # Na Vercel, prioriza o cabeçalho reservado da própria plataforma.
        # Fora dela, X-Forwarded-For só é usado quando o administrador
        # habilita explicitamente a confiança no proxy.
        encaminhado = ''

        if getattr(settings, 'VERCEL_RUNTIME', False):
            encaminhado = request.META.get(
                'HTTP_X_VERCEL_FORWARDED_FOR',
                '',
            )

        encaminhado = encaminhado or request.META.get(
            'HTTP_X_FORWARDED_FOR',
            '',
        )

        if encaminhado:
            valor = encaminhado.split(',', 1)[0].strip()

    try:
        return str(ip_address(valor))
    except ValueError:
        return 'desconhecido'


def _normalizar_identificador(identificador):
    return ' '.join((identificador or '').strip().casefold().split())


def _gerar_chave(escopo, ip_cliente, identificador=''):
    material = '|'.join(
        [
            escopo,
            ip_cliente,
            _normalizar_identificador(identificador),
        ]
    )

    return salted_hmac(
        'bancasapp.limite_requisicoes',
        material,
        algorithm='sha256',
    ).hexdigest()


def _obter_com_bloqueio(chave, escopo, agora):
    try:
        return (
            TentativaAcesso.objects
            .select_for_update()
            .get(chave=chave)
        )
    except TentativaAcesso.DoesNotExist:
        try:
            with transaction.atomic():
                return TentativaAcesso.objects.create(
                    chave=chave,
                    escopo=escopo,
                    inicio_janela=agora,
                )
        except IntegrityError:
            return (
                TentativaAcesso.objects
                .select_for_update()
                .get(chave=chave)
            )


def consumir_limite(
    *,
    escopo,
    ip_cliente,
    identificador='',
    limite,
    janela_segundos,
):
    """Consome uma tentativa e informa se a requisição ainda é permitida."""

    agora = timezone.now()
    duracao = timedelta(seconds=janela_segundos)
    chave = _gerar_chave(
        escopo,
        ip_cliente,
        identificador,
    )

    with transaction.atomic():
        registro = _obter_com_bloqueio(
            chave,
            escopo,
            agora,
        )

        if registro.bloqueado_ate and registro.bloqueado_ate > agora:
            restante = ceil(
                (registro.bloqueado_ate - agora).total_seconds()
            )

            return ResultadoLimite(
                permitido=False,
                tentar_novamente_em=max(restante, 1),
            )

        if agora - registro.inicio_janela >= duracao:
            registro.quantidade = 0
            registro.inicio_janela = agora
            registro.bloqueado_ate = None

        if registro.quantidade >= limite:
            registro.bloqueado_ate = registro.inicio_janela + duracao

            if registro.bloqueado_ate <= agora:
                registro.bloqueado_ate = agora + duracao

            registro.save(
                update_fields=[
                    'bloqueado_ate',
                    'atualizado_em',
                ]
            )

            restante = ceil(
                (registro.bloqueado_ate - agora).total_seconds()
            )

            return ResultadoLimite(
                permitido=False,
                tentar_novamente_em=max(restante, 1),
            )

        registro.quantidade += 1

        if registro.quantidade >= limite:
            registro.bloqueado_ate = registro.inicio_janela + duracao

        registro.save(
            update_fields=[
                'quantidade',
                'inicio_janela',
                'bloqueado_ate',
                'atualizado_em',
            ]
        )

    return ResultadoLimite(permitido=True)


def limpar_limite(*, escopo, ip_cliente, identificador=''):
    chave = _gerar_chave(
        escopo,
        ip_cliente,
        identificador,
    )

    TentativaAcesso.objects.filter(
        chave=chave
    ).delete()


def limpar_registros_antigos():
    limite_retencao = timezone.now() - timedelta(
        days=settings.SGTCC_RATE_LIMIT_RETENTION_DAYS
    )

    TentativaAcesso.objects.filter(
        atualizado_em__lt=limite_retencao
    ).delete()
