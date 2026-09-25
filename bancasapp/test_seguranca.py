from django.contrib.auth.models import User
from django.contrib.auth.hashers import identify_hasher
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import TentativaAcesso, pUsuario
from .security import obter_ip_cliente


class ArmazenamentoSenhasTests(TestCase):

    def test_senha_e_armazenada_com_hash_e_validada_pelo_django(self):
        senha_original = 'SenhaForte#2026'
        usuario = User.objects.create_user(
            username='hash@ufac.br',
            password=senha_original,
        )

        self.assertNotEqual(usuario.password, senha_original)
        self.assertNotIn(senha_original, usuario.password)
        self.assertTrue(usuario.check_password(senha_original))
        self.assertEqual(
            identify_hasher(usuario.password).algorithm,
            'pbkdf2_sha256',
        )


class CabecalhosSegurancaTests(TestCase):

    def test_login_recebe_csp_e_cabecalhos_adicionais(self):
        resposta = self.client.get(reverse('login'))

        self.assertEqual(resposta.status_code, 200)
        self.assertIn(
            "default-src 'self'",
            resposta['Content-Security-Policy'],
        )
        self.assertIn(
            "script-src 'self'",
            resposta['Content-Security-Policy'],
        )
        self.assertNotIn(
            "script-src 'self' 'unsafe-inline'",
            resposta['Content-Security-Policy'],
        )
        self.assertEqual(
            resposta['X-Frame-Options'],
            'DENY',
        )
        self.assertEqual(
            resposta['Cross-Origin-Resource-Policy'],
            'same-origin',
        )
        self.assertIn(
            'camera=()',
            resposta['Permissions-Policy'],
        )

    def test_login_nao_pode_ser_armazenado_em_cache(self):
        resposta = self.client.get(reverse('login'))

        self.assertIn('no-store', resposta['Cache-Control'])
        self.assertEqual(resposta['Pragma'], 'no-cache')

    def test_post_sem_token_csrf_e_rejeitado(self):
        cliente = Client(enforce_csrf_checks=True)

        resposta = cliente.post(
            reverse('login'),
            {
                'email': 'docente@ufac.br',
                'senha': 'SenhaIncorreta#2026',
            },
        )

        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(TentativaAcesso.objects.count(), 0)


@override_settings(
    SGTCC_RATE_LIMIT_ENABLED=True,
    SGTCC_RATE_LIMIT_LOGIN_ATTEMPTS=2,
    SGTCC_RATE_LIMIT_LOGIN_WINDOW=900,
    SGTCC_RATE_LIMIT_EMAIL_ATTEMPTS=2,
    SGTCC_RATE_LIMIT_EMAIL_WINDOW=3600,
    SGTCC_RATE_LIMIT_IP_ATTEMPTS=100,
    SGTCC_RATE_LIMIT_IP_WINDOW=900,
)
class LimiteRequisicoesTests(TestCase):

    def setUp(self):
        self.email = 'seguranca.docente@ufac.br'
        self.senha = 'SenhaForte#2026'
        self.usuario = User.objects.create_user(
            username=self.email,
            email=self.email,
            password=self.senha,
            is_active=True,
        )
        pUsuario.objects.create(
            usuario=self.usuario,
            perfil='DOCENTE',
        )

    def _login(self, senha):
        return self.client.post(
            reverse('login'),
            {
                'email': self.email,
                'senha': senha,
            },
            REMOTE_ADDR='192.0.2.10',
        )

    def test_login_bloqueia_apos_limite_de_falhas(self):
        primeira = self._login('incorreta-1')
        segunda = self._login('incorreta-2')
        bloqueada = self._login('incorreta-3')

        self.assertEqual(primeira.status_code, 200)
        self.assertEqual(segunda.status_code, 200)
        self.assertEqual(bloqueada.status_code, 429)
        self.assertContains(
            bloqueada,
            'Muitas tentativas',
            status_code=429,
        )
        self.assertGreater(int(bloqueada['Retry-After']), 0)

    def test_sucesso_limpa_contador_do_identificador(self):
        self._login('incorreta-1')

        sucesso = self._login(self.senha)

        self.assertRedirects(sucesso, reverse('dashboard'))
        self.assertFalse(
            TentativaAcesso.objects.filter(
                escopo='login-identificador'
            ).exists()
        )

    def test_contador_nao_armazena_ip_ou_email_legivel(self):
        self._login('incorreta-1')

        registros = list(
            TentativaAcesso.objects.values_list(
                'chave',
                flat=True,
            )
        )
        conteudo = ' '.join(registros)

        self.assertNotIn(self.email, conteudo)
        self.assertNotIn('192.0.2.10', conteudo)
        self.assertTrue(
            all(len(chave) == 64 for chave in registros)
        )

    def test_recuperacao_de_senha_possui_limite(self):
        url = reverse('recuperar_senha')
        dados = {'email': self.email}

        primeira = self.client.post(
            url,
            dados,
            REMOTE_ADDR='192.0.2.20',
        )
        segunda = self.client.post(
            url,
            dados,
            REMOTE_ADDR='192.0.2.20',
        )
        bloqueada = self.client.post(
            url,
            dados,
            REMOTE_ADDR='192.0.2.20',
        )

        self.assertEqual(primeira.status_code, 302)
        self.assertEqual(segunda.status_code, 302)
        self.assertEqual(bloqueada.status_code, 429)

    def test_limite_de_email_nao_e_contornado_trocando_ip(self):
        url = reverse('recuperar_senha')
        dados = {'email': self.email}

        self.client.post(
            url,
            dados,
            REMOTE_ADDR='192.0.2.31',
        )
        self.client.post(
            url,
            dados,
            REMOTE_ADDR='192.0.2.32',
        )
        bloqueada = self.client.post(
            url,
            dados,
            REMOTE_ADDR='192.0.2.33',
        )

        self.assertEqual(bloqueada.status_code, 429)

    def test_x_forwarded_for_nao_e_aceito_sem_confianca(self):
        self._login('incorreta-1')

        segunda = self.client.post(
            reverse('login'),
            {
                'email': self.email,
                'senha': 'incorreta-2',
            },
            REMOTE_ADDR='192.0.2.10',
            HTTP_X_FORWARDED_FOR='198.51.100.99',
        )
        bloqueada = self.client.post(
            reverse('login'),
            {
                'email': self.email,
                'senha': 'incorreta-3',
            },
            REMOTE_ADDR='192.0.2.10',
            HTTP_X_FORWARDED_FOR='203.0.113.50',
        )

        self.assertEqual(segunda.status_code, 200)
        self.assertEqual(bloqueada.status_code, 429)

    @override_settings(SGTCC_TRUST_PROXY_CLIENT_IP=True)
    def test_x_forwarded_for_e_aceito_atras_de_proxy_confiavel(self):
        for indice, ip_cliente in enumerate(
            [
                '198.51.100.10',
                '198.51.100.11',
                '198.51.100.12',
            ],
            start=1,
        ):
            resposta = self.client.post(
                reverse('login'),
                {
                    'email': self.email,
                    'senha': f'incorreta-{indice}',
                },
                REMOTE_ADDR='192.0.2.10',
                HTTP_X_FORWARDED_FOR=ip_cliente,
            )

            self.assertEqual(resposta.status_code, 200)

    @override_settings(
        VERCEL_RUNTIME=True,
        SGTCC_TRUST_PROXY_CLIENT_IP=True,
    )
    def test_vercel_forwarded_for_tem_prioridade_na_vercel(self):
        self.assertEqual(
            obter_ip_cliente(
                type(
                    'Requisicao',
                    (),
                    {
                        'META': {
                            'REMOTE_ADDR': '192.0.2.10',
                            'HTTP_X_FORWARDED_FOR': '198.51.100.99',
                            'HTTP_X_VERCEL_FORWARDED_FOR': '203.0.113.50',
                        },
                    },
                )()
            ),
            '203.0.113.50',
        )
