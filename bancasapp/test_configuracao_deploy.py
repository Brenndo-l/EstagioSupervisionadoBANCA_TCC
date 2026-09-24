"""Testes isolados das proteções de configuração do deploy."""

import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase


class ConfiguracaoDeployTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):

        super().setUpClass()
        cls.raiz_projeto = Path(__file__).resolve().parent.parent

    def ambiente_vercel_valido(self):

        nomes_controlados = {
            'VERCEL',
            'VERCEL_ENV',
            'VERCEL_URL',
            'DJANGO_DEBUG',
            'DJANGO_SECRET_KEY',
            'DJANGO_ALLOWED_HOSTS',
            'DJANGO_CSRF_TRUSTED_ORIGINS',
            'DATABASE_URL',
            'BLOB_READ_WRITE_TOKEN',
            'VERCEL_BLOB_READ_WRITE_TOKEN',
            'BLOB_STORE_ID',
            'DJANGO_EMAIL_BACKEND',
            'DJANGO_EMAIL_HOST',
            'DJANGO_EMAIL_PORT',
            'DJANGO_EMAIL_HOST_USER',
            'DJANGO_EMAIL_HOST_PASSWORD',
            'DJANGO_EMAIL_USE_TLS',
            'DJANGO_EMAIL_USE_SSL',
            'DJANGO_DEFAULT_FROM_EMAIL',
        }

        ambiente = {
            nome: valor
            for nome, valor in os.environ.items()
            if nome not in nomes_controlados
        }

        ambiente.update(
            {
                'VERCEL': '1',
                'VERCEL_ENV': 'production',
                'VERCEL_URL': 'sgtcc-teste.vercel.app',
                'DJANGO_DEBUG': 'False',
                'DJANGO_SECRET_KEY': (
                    'chave-aleatoria-de-teste-com-mais-de-cinquenta-'
                    'caracteres-123456789'
                ),
                'DATABASE_URL': (
                    'postgresql://usuario:senha@db.example:5432/sgtcc'
                    '?sslmode=require'
                ),
                'BLOB_READ_WRITE_TOKEN': (
                    'vercel_blob_rw_store_teste_segredo'
                ),
                'DJANGO_EMAIL_BACKEND': (
                    'django.core.mail.backends.smtp.EmailBackend'
                ),
                'DJANGO_EMAIL_HOST': 'smtp.example.com',
                'DJANGO_EMAIL_PORT': '587',
                'DJANGO_EMAIL_HOST_USER': 'usuario-smtp',
                'DJANGO_EMAIL_HOST_PASSWORD': 'senha-smtp',
                'DJANGO_EMAIL_USE_TLS': 'True',
                'DJANGO_EMAIL_USE_SSL': 'False',
                'DJANGO_DEFAULT_FROM_EMAIL': (
                    'SGTCC <sgtcc@example.com>'
                ),
            }
        )

        return ambiente

    def importar_configuracao(self, ambiente):

        return subprocess.run(
            [
                sys.executable,
                '-c',
                (
                    'import core.settings as s; '
                    'print(s.DEBUG); '
                    'print(s.EMAIL_BACKEND); '
                    'print(s.STORAGES["default"]["BACKEND"])'
                ),
            ],
            cwd=self.raiz_projeto,
            env=ambiente,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )

    def test_configuracao_completa_da_vercel_e_aceita(self):

        resultado = self.importar_configuracao(
            self.ambiente_vercel_valido()
        )

        self.assertEqual(
            resultado.returncode,
            0,
            resultado.stderr,
        )
        self.assertIn('False', resultado.stdout)
        self.assertIn('smtp.EmailBackend', resultado.stdout)
        self.assertIn('VercelBlobStorage', resultado.stdout)

    def test_debug_ativo_e_rejeitado_na_vercel(self):

        ambiente = self.ambiente_vercel_valido()
        ambiente['DJANGO_DEBUG'] = 'True'

        resultado = self.importar_configuracao(ambiente)

        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn(
            'DJANGO_DEBUG deve ser False na Vercel',
            resultado.stderr,
        )

    def test_vercel_sem_database_url_e_rejeitada(self):

        ambiente = self.ambiente_vercel_valido()
        ambiente.pop('DATABASE_URL')

        resultado = self.importar_configuracao(ambiente)

        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn('DATABASE_URL', resultado.stderr)

    def test_vercel_sem_token_blob_e_rejeitada(self):

        ambiente = self.ambiente_vercel_valido()
        ambiente.pop('BLOB_READ_WRITE_TOKEN')
        ambiente['BLOB_STORE_ID'] = 'store_sem_credencial'

        resultado = self.importar_configuracao(ambiente)

        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn('BLOB_READ_WRITE_TOKEN', resultado.stderr)

    def test_vercel_com_backend_de_console_e_rejeitada(self):

        ambiente = self.ambiente_vercel_valido()
        ambiente['DJANGO_EMAIL_BACKEND'] = (
            'django.core.mail.backends.console.EmailBackend'
        )

        resultado = self.importar_configuracao(ambiente)

        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn(
            'backend de console apenas escreve o e-mail nos logs',
            resultado.stderr,
        )

    def test_vercel_sem_credenciais_smtp_e_rejeitada(self):

        ambiente = self.ambiente_vercel_valido()
        ambiente.pop('DJANGO_EMAIL_HOST_PASSWORD')

        resultado = self.importar_configuracao(ambiente)

        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn(
            'DJANGO_EMAIL_HOST_PASSWORD',
            resultado.stderr,
        )
