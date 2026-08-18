from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from datetime import timedelta
from django.utils import timezone

from .models import (
    pUsuario,
    EspacoFisico,
    Discente,
    ProjetoTCC,
    SolicitacaoAgendamento,
    ComposicaoBanca,
)


# Testes da tela de login
class LoginTests(TestCase):

    def setUp(self):
        self.usuario = User.objects.create_user(
            username='docente@ufac.br',
            password='Senha123!'
        )

        self.perfil = pUsuario.objects.create(
            usuario=self.usuario,
            perfil='DOCENTE'
        )

    def test_tela_login_abre(self):
        response = self.client.get(
            reverse('login')
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertTemplateUsed(
            response,
            'login.html'
        )

    def test_login_valido(self):
        response = self.client.post(
            reverse('login'),
            {
                'email': 'docente@ufac.br',
                'senha': 'Senha123!'
            }
        )

        self.assertRedirects(
            response,
            reverse('dashboard')
        )

    def test_login_invalido(self):
        response = self.client.post(
            reverse('login'),
            {
                'email': 'docente@ufac.br',
                'senha': 'senha_errada'
            }
        )

        self.assertEqual(
            response.status_code,
            200
        )

        # Confirma que o usuário não entrou no sistema
        self.assertNotIn(
            '_auth_user_id',
            self.client.session
        )


# Testes da solicitação de banca
class AgendamentoTests(TestCase):

    def setUp(self):

        # Docente que fará a solicitação
        self.usuario_docente = User.objects.create_user(
            username='docente@ufac.br',
            password='Senha123!'
        )

        self.docente = pUsuario.objects.create(
            usuario=self.usuario_docente,
            perfil='DOCENTE'
        )

        # Segundo docente para ser avaliador
        self.usuario_avaliador = User.objects.create_user(
            username='avaliador@ufac.br',
            password='Senha123!'
        )

        self.avaliador = pUsuario.objects.create(
            usuario=self.usuario_avaliador,
            perfil='DOCENTE'
        )

        # Discente usado no teste
        self.discente = Discente.objects.create(
            nome='Aluno Teste',
            matricula='20260000001'
        )

        # Projeto usado no teste
        self.projeto = ProjetoTCC.objects.create(
            titulo='Projeto de Teste Automatizado',
            resumo='Projeto criado somente durante os testes.',
            semestre_letivo='2026.1',
            discente=self.discente
        )

        # Sala usada no teste
        self.espaco = EspacoFisico.objects.create(
            nome='LAB TESTE'
        )

    def test_solicitar_banca_exige_login(self):
        response = self.client.get(
            reverse('solicitar_banca')
        )

        self.assertEqual(
            response.status_code,
            302
        )

    def test_docente_consegue_abrir_solicitacao(self):

        self.client.force_login(
            self.usuario_docente
        )

        response = self.client.get(
            reverse('solicitar_banca')
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertTemplateUsed(
            response,
            'solicitar_banca.html'
        )

    def test_docente_consegue_solicitar_banca(self):

        self.client.force_login(
            self.usuario_docente
        )

        response = self.client.post(
            reverse('solicitar_banca'),
            {
                'projeto_tcc': self.projeto.id,
                'espaco': self.espaco.id,

                'opcao_data_inicio':
                    '2026-08-20T14:00',

                'opcao_data_fim':
                    '2026-08-20T16:00',

                'orientador':
                    self.docente.id,

                'avaliador_interno':
                    self.avaliador.id,

                'nome_avaliador_externo':
                    '',

                'instituicao_avaliador_externo':
                    '',
            }
        )

        # Após salvar, deve voltar ao Dashboard
        self.assertRedirects(
            response,
            reverse('dashboard')
        )

        # Deve existir exatamente uma solicitação
        self.assertEqual(
            SolicitacaoAgendamento.objects.count(),
            1
        )

        solicitacao = (
            SolicitacaoAgendamento.objects.first()
        )

        # A solicitação deve começar Em Análise
        self.assertEqual(
            solicitacao.status,
            'EM_ANÁLISE'
        )

        # Deve pertencer ao docente logado
        self.assertEqual(
            solicitacao.usuario_solicitante,
            self.docente
        )

        # Deve estar ligada ao projeto correto
        self.assertEqual(
            solicitacao.projeto_tcc,
            self.projeto
        )

        # A composição da banca também deve ter sido criada
        composicao = ComposicaoBanca.objects.get(
            projeto_tcc=self.projeto
        )

        self.assertEqual(
            composicao.orientador,
            self.docente
        )

        self.assertEqual(
            composicao.avaliador_interno,
            self.avaliador
        )