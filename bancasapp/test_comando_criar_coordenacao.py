from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.test import TestCase

from .models import pUsuario


class CriarCoordenacaoCommandTests(TestCase):

    def executar(self, **opcoes):

        dados = {
            'usuario': 'coordenacao',
            'email': 'coordenacao@ufac.br',
            'nome': 'Pessoa',
            'sobrenome': 'Coordenadora',
            'stdout': StringIO(),
        }
        dados.update(opcoes)

        with patch.dict(
            'os.environ',
            {
                'SGTCC_COORDENACAO_PASSWORD': (
                    'SenhaSegura#2026!Coordenacao'
                )
            },
            clear=False,
        ):
            call_command('criar_coordenacao', **dados)

        return dados['stdout']

    def test_cria_usuario_e_perfil_coordenacao(self):

        saida = self.executar()

        usuario = User.objects.get(username='coordenacao')
        perfil = pUsuario.objects.get(usuario=usuario)

        self.assertTrue(usuario.is_active)
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        self.assertTrue(
            usuario.check_password('SenhaSegura#2026!Coordenacao')
        )
        self.assertNotEqual(
            usuario.password,
            'SenhaSegura#2026!Coordenacao',
        )
        self.assertEqual(perfil.perfil, 'COORDENACAO')
        self.assertIn('criada com sucesso', saida.getvalue())

    def test_pode_criar_superusuario_para_o_primeiro_acesso(self):

        self.executar(superusuario=True)

        usuario = User.objects.get(username='coordenacao')

        self.assertTrue(usuario.is_staff)
        self.assertTrue(usuario.is_superuser)

    def test_nao_altera_conta_existente(self):

        User.objects.create_user(
            username='coordenacao',
            email='existente@ufac.br',
            password='OutraSenha#2026!',
        )

        with self.assertRaisesMessage(
            CommandError,
            'Já existe uma conta com esse usuário',
        ):
            self.executar()

        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(pUsuario.objects.count(), 0)
