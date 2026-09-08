"""Middlewares próprios de proteção das páginas do SGTCC."""

from django.conf import settings
from django.shortcuts import render
from django.utils.deprecation import MiddlewareMixin

from .security import (
    consumir_limite,
    limpar_limite,
    limpar_registros_antigos,
    obter_ip_cliente,
)


class CabecalhosSegurancaMiddleware:
    """Aplica headers adicionais e evita cache de páginas sensíveis."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        response.setdefault(
            'Permissions-Policy',
            'camera=(), geolocation=(), microphone=(), payment=(), usb=()',
        )
        response.setdefault(
            'Cross-Origin-Resource-Policy',
            'same-origin',
        )
        response.setdefault(
            'X-Permitted-Cross-Domain-Policies',
            'none',
        )

        usuario = getattr(request, 'user', None)
        rota_sensivel = request.path.startswith(
            (
                '/senha/',
                '/cadastro/',
                '/admin/',
            )
        ) or request.path == '/'

        if (
            getattr(usuario, 'is_authenticated', False)
            or rota_sensivel
        ):
            response['Cache-Control'] = (
                'no-store, no-cache, max-age=0, must-revalidate, private'
            )
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'

        return response


class LimiteRequisicoesAutenticacaoMiddleware(MiddlewareMixin):
    """Limita tentativas em login, cadastro e disparos de e-mail."""

    ROTAS_EMAIL = {
        'cadastrar_docente',
        'reenviar_confirmacao_docente',
        'recuperar_senha',
    }

    def process_view(
        self,
        request,
        view_func,
        view_args,
        view_kwargs,
    ):
        if (
            not settings.SGTCC_RATE_LIMIT_ENABLED
            or request.method != 'POST'
        ):
            return None

        rota = request.resolver_match.view_name
        eh_login = rota in {'login', 'admin:login'}
        eh_rota_email = rota in self.ROTAS_EMAIL

        if not eh_login and not eh_rota_email:
            return None

        limpar_registros_antigos()

        ip_cliente = obter_ip_cliente(request)
        campo_identificador = 'username' if rota == 'admin:login' else 'email'
        identificador = request.POST.get(campo_identificador, '')

        if eh_login:
            escopo_identificador = 'login-identificador'
            limite_identificador = settings.SGTCC_RATE_LIMIT_LOGIN_ATTEMPTS
            janela = settings.SGTCC_RATE_LIMIT_LOGIN_WINDOW
        else:
            escopo_identificador = f'{rota}-identificador'
            limite_identificador = settings.SGTCC_RATE_LIMIT_EMAIL_ATTEMPTS
            janela = settings.SGTCC_RATE_LIMIT_EMAIL_WINDOW

        # Para login, o identificador é limitado junto ao IP para impedir que
        # terceiros bloqueiem uma conta legítima. Para rotas que enviam e-mail,
        # o limite por destinatário é global e impede bombardeio por vários IPs.
        ip_limite_identificador = (
            ip_cliente
            if eh_login
            else 'global'
        )

        verificacoes = [
            consumir_limite(
                escopo=escopo_identificador,
                ip_cliente=ip_limite_identificador,
                identificador=identificador,
                limite=limite_identificador,
                janela_segundos=janela,
            ),
            consumir_limite(
                escopo='autenticacao-ip',
                ip_cliente=ip_cliente,
                limite=settings.SGTCC_RATE_LIMIT_IP_ATTEMPTS,
                janela_segundos=settings.SGTCC_RATE_LIMIT_IP_WINDOW,
            ),
        ]

        bloqueio = next(
            (
                resultado
                for resultado in verificacoes
                if not resultado.permitido
            ),
            None,
        )

        request._sgtcc_limite_login = (
            escopo_identificador,
            ip_limite_identificador,
            identificador,
        ) if eh_login else None

        if bloqueio is None:
            return None

        resposta = render(
            request,
            'erro_sistema.html',
            {
                'codigo_erro': '429',
                'titulo_erro': 'Muitas tentativas',
                'mensagem_erro': (
                    'Por segurança, aguarde alguns minutos antes de '
                    'tentar novamente.'
                ),
            },
            status=429,
        )
        resposta['Retry-After'] = str(
            bloqueio.tentar_novamente_em
        )

        return resposta

    def process_response(self, request, response):
        dados_login = getattr(
            request,
            '_sgtcc_limite_login',
            None,
        )

        if (
            dados_login
            and getattr(request.user, 'is_authenticated', False)
            and 300 <= response.status_code < 400
        ):
            escopo, ip_cliente, identificador = dados_login

            limpar_limite(
                escopo=escopo,
                ip_cliente=ip_cliente,
                identificador=identificador,
            )

        return response
