from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from datetime import timedelta
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import (
    pUsuario,
    EspacoFisico,
    Discente,
    ProjetoTCC,
    SolicitacaoAgendamento,
    ComposicaoBanca,
    BancaTCC,
    DisponibilidadeEspaco,
)

def criar_pdf_teste():

    return SimpleUploadedFile(
        'tcc_teste.pdf',
        b'%PDF-1.4\n% Arquivo utilizado nos testes do SGTCC.',
        content_type='application/pdf'
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

        self.inicio_agendamento = (
            timezone.localtime(
                timezone.now()
            )
            + timedelta(days=30)
        ).replace(
            second=0,
            microsecond=0
        )

        self.fim_agendamento = (
            self.inicio_agendamento
            + timedelta(hours=2)
        )

        self.disponibilidade = (
            DisponibilidadeEspaco.objects.create(
                espaco=self.espaco,
                data_hora_inicio=(
                    self.inicio_agendamento
                    - timedelta(hours=1)
                ),
                data_hora_fim=(
                    self.fim_agendamento
                    + timedelta(hours=1)
                ),
                ativo=True,
                criada_por=self.usuario_docente,
            )
        )
    def test_horario_fora_da_disponibilidade_e_recusado(self):

        self.client.force_login(
            self.usuario_docente
        )

        inicio_fora = (
            self.disponibilidade.data_hora_fim
            + timedelta(hours=1)
        )

        fim_fora = (
            inicio_fora
            + timedelta(hours=2)
        )

        response = self.client.post(
            reverse('solicitar_banca'),
            {
                'projeto_tcc': self.projeto.id,
                'espaco': self.espaco.id,

                'opcao_data_inicio': (
                    inicio_fora.strftime(
                        '%Y-%m-%dT%H:%M'
                    )
                ),

                'opcao_data_fim': (
                    fim_fora.strftime(
                        '%Y-%m-%dT%H:%M'
                    )
                ),

                'orientador': self.docente.id,

                'avaliador_interno': self.avaliador.id,

                'nome_avaliador_externo': '',

                'instituicao_avaliador_externo': '',
            }
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertContains(
            response,
            'não está dentro de um horário disponibilizado'
        )

        self.assertEqual(
            SolicitacaoAgendamento.objects.count(),
            0
        )


    def test_disponibilidade_inativa_nao_pode_ser_usada(self):

        self.disponibilidade.ativo = False

        self.disponibilidade.save(
            update_fields=['ativo']
        )

        self.client.force_login(
            self.usuario_docente
        )

        response = self.client.post(
            reverse('solicitar_banca'),
            {
                'projeto_tcc': self.projeto.id,
                'espaco': self.espaco.id,

                'opcao_data_inicio': (
                    self.inicio_agendamento.strftime(
                        '%Y-%m-%dT%H:%M'
                    )
                ),

                'opcao_data_fim': (
                    self.fim_agendamento.strftime(
                        '%Y-%m-%dT%H:%M'
                    )
                ),

                'orientador': self.docente.id,

                'avaliador_interno': self.avaliador.id,

                'nome_avaliador_externo': '',

                'instituicao_avaliador_externo': '',
            }
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertEqual(
            SolicitacaoAgendamento.objects.count(),
            0
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

    def test_espaco_ativo_sem_disponibilidade_aparece_no_formulario(self):

        espaco_sem_disponibilidade = (
            EspacoFisico.objects.create(
                nome='Sala Ativa Sem Horário',
                ativo=True
            )
        )

        self.client.force_login(
            self.usuario_docente
        )

        response = self.client.get(
            reverse('solicitar_banca')
        )

        queryset_espacos = (
            response.context['form']
            .fields['espaco']
            .queryset
        )

        self.assertIn(
            espaco_sem_disponibilidade,
            queryset_espacos
        )

    def test_arquivo_tcc_precisa_ser_pdf_valido(self):

        self.client.force_login(
            self.usuario_docente
        )

        arquivo_falso = SimpleUploadedFile(
            'tcc_falso.pdf',
            b'Este arquivo nao possui estrutura de PDF.',
            content_type='application/pdf'
        )

        response = self.client.post(
            reverse('solicitar_banca'),
            {
                'projeto_tcc': self.projeto.id,
                'espaco': self.espaco.id,

                'opcao_data_inicio': (
                    self.inicio_agendamento.strftime(
                        '%Y-%m-%dT%H:%M'
                    )
                ),

                'opcao_data_fim': (
                    self.fim_agendamento.strftime(
                        '%Y-%m-%dT%H:%M'
                    )
                ),

                'orientador':
                    self.docente.id,

                'avaliador_interno':
                    self.avaliador.id,

                'nome_avaliador_externo':
                    '',

                'instituicao_avaliador_externo':
                    '',

                'arquivo_tcc':
                    arquivo_falso,
            }
        )

        # Formulário inválido permanece na página.
        self.assertEqual(
            response.status_code,
            200
        )

        self.assertContains(
            response,
            'não parece ser um PDF válido'
        )

        # Nenhuma solicitação deve ter sido criada.
        self.assertEqual(
            SolicitacaoAgendamento.objects.count(),
            0
        )

    def test_docente_nao_pode_ocupar_duas_funcoes(self):

        self.client.force_login(
            self.usuario_docente
        )

        response = self.client.post(
            reverse('solicitar_banca'),
            {
                'projeto_tcc': self.projeto.id,
                'espaco': self.espaco.id,

                'opcao_data_inicio': (
                    self.inicio_agendamento.strftime(
                        '%Y-%m-%dT%H:%M'
                    )
                ),

                'opcao_data_fim': (
                    self.fim_agendamento.strftime(
                        '%Y-%m-%dT%H:%M'
                    )
                ),

                'orientador': self.docente.id,

                # Mesmo docente escolhido novamente.
                'coorientador': self.docente.id,

                'avaliador_interno': self.avaliador.id,

                'segundo_avaliador_interno': '',

                'nome_avaliador_externo': '',

                'instituicao_avaliador_externo': '',

                'arquivo_tcc': criar_pdf_teste(),
            }
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertContains(
            response,
            'já foi selecionado como orientador'
        )

        self.assertEqual(
            SolicitacaoAgendamento.objects.count(),
            0
        )

    def test_participantes_opcionais_sao_salvos(self):

        usuario_coorientador = User.objects.create(
            username='coorientador@ufac.br'
        )

        coorientador = pUsuario.objects.create(
            usuario=usuario_coorientador,
            perfil='DOCENTE'
        )

        usuario_segundo_avaliador = User.objects.create(
            username='segundo.avaliador@ufac.br'
        )

        segundo_avaliador = pUsuario.objects.create(
            usuario=usuario_segundo_avaliador,
            perfil='DOCENTE'
        )

        self.client.force_login(
            self.usuario_docente
        )

        response = self.client.post(
            reverse('solicitar_banca'),
            {
                'projeto_tcc': self.projeto.id,
                'espaco': self.espaco.id,

                'opcao_data_inicio': (
                    self.inicio_agendamento.strftime(
                        '%Y-%m-%dT%H:%M'
                    )
                ),

                'opcao_data_fim': (
                    self.fim_agendamento.strftime(
                        '%Y-%m-%dT%H:%M'
                    )
                ),

                'orientador': self.docente.id,

                'coorientador': coorientador.id,

                'avaliador_interno': self.avaliador.id,

                'segundo_avaliador_interno':
                    segundo_avaliador.id,

                'nome_avaliador_externo': '',

                'instituicao_avaliador_externo': '',

                'arquivo_tcc': criar_pdf_teste(),
            }
        )

        self.assertRedirects(
            response,
            reverse('dashboard')
        )

        solicitacao = (
            SolicitacaoAgendamento.objects.get()
        )

        self.addCleanup(
            solicitacao.arquivo_tcc.delete,
            save=False
        )

        composicao = ComposicaoBanca.objects.get(
            solicitacao=solicitacao
        )

        self.assertEqual(
            composicao.coorientador,
            coorientador
        )

        self.assertEqual(
            composicao.segundo_avaliador_interno,
            segundo_avaliador
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

                'opcao_data_inicio': (
                    self.inicio_agendamento.strftime(
                        '%Y-%m-%dT%H:%M'
                    )
                ),

                'opcao_data_fim': (
                    self.fim_agendamento.strftime(
                        '%Y-%m-%dT%H:%M'
                    )
                ),

                'orientador':
                    self.docente.id,

                'avaliador_interno':
                    self.avaliador.id,

                'nome_avaliador_externo':
                    '',

                'instituicao_avaliador_externo':
                    '',

                'arquivo_tcc':
                    criar_pdf_teste(),
            }
        )

        # Após salvar, deve voltar ao Dashboard.
        self.assertRedirects(
            response,
            reverse('dashboard')
        )

        # Deve existir exatamente uma solicitação.
        self.assertEqual(
            SolicitacaoAgendamento.objects.count(),
            1
        )

        solicitacao = (
            SolicitacaoAgendamento.objects.first()
        )

        # Garante que o arquivo físico seja removido
        # depois que o teste terminar.
        self.addCleanup(
            solicitacao.arquivo_tcc.delete,
            save=False
        )

        # O PDF deve ter sido armazenado.
        self.assertTrue(
            solicitacao.arquivo_tcc.name.endswith(
                '.pdf'
            )
        )

        # A solicitação deve começar Em Análise.
        self.assertEqual(
            solicitacao.status,
            'EM_ANÁLISE'
        )

        # Deve pertencer ao docente logado.
        self.assertEqual(
            solicitacao.usuario_solicitante,
            self.docente
        )

        # Deve estar ligada ao projeto correto.
        self.assertEqual(
            solicitacao.projeto_tcc,
            self.projeto
        )

        # A composição da banca também deve ter sido criada.
        composicao = ComposicaoBanca.objects.get(
            projeto_tcc=self.projeto
        )

        # A composição deve pertencer exatamente
        # à solicitação recém-criada.
        self.assertEqual(
            composicao.solicitacao,
            solicitacao
        )

        self.assertEqual(
            composicao.orientador,
            self.docente
        )

        self.assertEqual(
            composicao.avaliador_interno,
            self.avaliador
        )
        # Os participantes adicionais são opcionais.
        self.assertIsNone(
            composicao.coorientador
        )

        self.assertIsNone(
            composicao.segundo_avaliador_interno
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

        # Testes da avaliação realizada pela Coordenação
class AvaliacaoSolicitacaoTests(TestCase):

    def setUp(self):

        # Usuário da Coordenação
        self.usuario_coordenacao = User.objects.create_user(
            username='coordenacao@ufac.br',
            password='Senha123!'
        )

        self.coordenacao = pUsuario.objects.create(
            usuario=self.usuario_coordenacao,
            perfil='COORDENACAO'
        )

        # Docente solicitante
        self.usuario_docente = User.objects.create_user(
            username='docente_avaliacao@ufac.br',
            password='Senha123!'
        )

        self.docente = pUsuario.objects.create(
            usuario=self.usuario_docente,
            perfil='DOCENTE'
        )

        # Avaliador interno
        self.usuario_avaliador = User.objects.create_user(
            username='avaliador_avaliacao@ufac.br',
            password='Senha123!'
        )

        self.avaliador = pUsuario.objects.create(
            usuario=self.usuario_avaliador,
            perfil='DOCENTE'
        )

        self.discente = Discente.objects.create(
            nome='Discente Avaliação',
            matricula='20260000002'
        )

        self.projeto = ProjetoTCC.objects.create(
            titulo='Projeto para Avaliação',
            resumo='Projeto utilizado nos testes da Coordenação.',
            semestre_letivo='2026.1',
            discente=self.discente
        )

        self.espaco = EspacoFisico.objects.create(
            nome='Laboratório de Avaliação'
        )

        inicio = timezone.now() + timedelta(days=30)
        fim = inicio + timedelta(hours=2)

        self.solicitacao = SolicitacaoAgendamento.objects.create(
            usuario_solicitante=self.docente,
            projeto_tcc=self.projeto,
            espaco=self.espaco,
            opcao_data_inicio=inicio,
            opcao_data_fim=fim,
            status='EM_ANÁLISE'
        )

        self.composicao = ComposicaoBanca.objects.create(
            projeto_tcc=self.projeto,
            solicitacao=self.solicitacao,
            orientador=self.docente,
            avaliador_interno=self.avaliador,
            nome_avaliador_externo='Avaliador Externo',
            instituicao_avaliador_externo='Instituição Externa'
        )

        self.url_avaliacao = reverse(
            'avaliar_solicitacao',
            args=[self.solicitacao.id]
        )

    def test_coordenacao_consegue_editar_solicitacao_pendente(
        self
    ):

        novo_espaco = EspacoFisico.objects.create(
            nome='Laboratório Editado'
        )

        novo_inicio = (
            timezone.localtime(
                timezone.now()
            )
            + timedelta(days=40)
        ).replace(
            second=0,
            microsecond=0
        )

        novo_fim = (
            novo_inicio
            + timedelta(hours=2)
        )

        DisponibilidadeEspaco.objects.create(
            espaco=novo_espaco,
            data_hora_inicio=(
                novo_inicio
                - timedelta(hours=1)
            ),
            data_hora_fim=(
                novo_fim
                + timedelta(hours=1)
            ),
            ativo=True,
            criada_por=self.usuario_coordenacao,
        )

        url_edicao = reverse(
            'editar_solicitacao_coordenacao',
            args=[self.solicitacao.id]
        )

        projeto_original = (
            self.solicitacao.projeto_tcc_id
        )

        arquivo_original = (
            self.solicitacao.arquivo_tcc.name
        )

        self.client.force_login(
            self.usuario_coordenacao
        )

        resposta_get = self.client.get(
            url_edicao
        )

        self.assertEqual(
            resposta_get.status_code,
            200
        )

        self.assertTemplateUsed(
            resposta_get,
            'editar_solicitacao_coordenacao.html'
        )

        campos_formulario = (
            resposta_get.context['form'].fields
        )

        self.assertNotIn(
            'projeto_tcc',
            campos_formulario
        )

        self.assertNotIn(
            'arquivo_tcc',
            campos_formulario
        )

        response = self.client.post(
            url_edicao,
            {
                'espaco': novo_espaco.id,

                'opcao_data_inicio': (
                    novo_inicio.strftime(
                        '%Y-%m-%dT%H:%M'
                    )
                ),

                'opcao_data_fim': (
                    novo_fim.strftime(
                        '%Y-%m-%dT%H:%M'
                    )
                ),

                'orientador': self.docente.id,

                'coorientador': '',

                'avaliador_interno': (
                    self.avaliador.id
                ),

                'segundo_avaliador_interno': '',

                'nome_avaliador_externo': (
                    'Nome Externo Corrigido'
                ),

                'instituicao_avaliador_externo': (
                    'Instituição Corrigida'
                ),
            }
        )

        self.assertRedirects(
            response,
            reverse(
                'avaliar_solicitacao',
                args=[self.solicitacao.id]
            )
        )

        self.solicitacao.refresh_from_db()
        self.composicao.refresh_from_db()

        self.assertEqual(
            self.solicitacao.espaco,
            novo_espaco
        )

        self.assertEqual(
            self.solicitacao.opcao_data_inicio,
            novo_inicio
        )

        self.assertEqual(
            self.solicitacao.opcao_data_fim,
            novo_fim
        )

        # Projeto e PDF original foram preservados.
        self.assertEqual(
            self.solicitacao.projeto_tcc_id,
            projeto_original
        )

        self.assertEqual(
            self.solicitacao.arquivo_tcc.name,
            arquivo_original
        )

        self.assertEqual(
            self.composicao.nome_avaliador_externo,
            'Nome Externo Corrigido'
        )

        self.assertEqual(
            self.composicao.instituicao_avaliador_externo,
            'Instituição Corrigida'
        )

    def test_docente_nao_pode_editar_solicitacao(
        self
    ):

        self.client.force_login(
            self.usuario_docente
        )

        response = self.client.get(
            reverse(
                'editar_solicitacao_coordenacao',
                args=[self.solicitacao.id]
            )
        )

        self.assertRedirects(
            response,
            reverse('dashboard')
        )

    def test_solicitacao_decidida_nao_pode_ser_editada(
        self
    ):

        self.solicitacao.status = 'RECUSADA'

        self.solicitacao.save(
            update_fields=['status']
        )

        self.client.force_login(
            self.usuario_coordenacao
        )

        response = self.client.get(
            reverse(
                'editar_solicitacao_coordenacao',
                args=[self.solicitacao.id]
            )
        )

        self.assertRedirects(
            response,
            reverse(
                'solicitacoes_coordenacao'
            )
        )

    def test_docente_nao_pode_acessar_avaliacao(self):

        self.client.force_login(
            self.usuario_docente
        )

        response = self.client.get(
            self.url_avaliacao
        )

        self.assertRedirects(
            response,
            reverse('dashboard')
        )

        self.solicitacao.refresh_from_db()

        self.assertEqual(
            self.solicitacao.status,
            'EM_ANÁLISE'
        )

    def test_abrir_pagina_nao_altera_solicitacao(self):

        self.client.force_login(
            self.usuario_coordenacao
        )

        response = self.client.get(
            self.url_avaliacao
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertTemplateUsed(
            response,
            'avaliar_solicitacao.html'
        )

        self.solicitacao.refresh_from_db()

        self.assertEqual(
            self.solicitacao.status,
            'EM_ANÁLISE'
        )

        self.assertEqual(
            BancaTCC.objects.count(),
            0
        )

    def test_justificativa_e_obrigatoria(self):

        self.client.force_login(
            self.usuario_coordenacao
        )

        response = self.client.post(
            self.url_avaliacao,
            {
                'acao': 'aprovar',
                'motivo_decisao': '',
            }
        )

        # Formulário inválido continua na página
        self.assertEqual(
            response.status_code,
            200
        )

        self.solicitacao.refresh_from_db()

        self.assertEqual(
            self.solicitacao.status,
            'EM_ANÁLISE'
        )

        self.assertIsNone(
            self.solicitacao.data_decisao
        )

        self.assertEqual(
            BancaTCC.objects.count(),
            0
        )

    def test_coordenacao_consegue_aprovar(self):

        self.client.force_login(
            self.usuario_coordenacao
        )

        response = self.client.post(
            self.url_avaliacao,
            {
                'acao': 'aprovar',
                'motivo_decisao': (
                    'Dados conferidos e horário disponível.'
                ),
            }
        )

        self.assertRedirects(
            response,
            reverse('dashboard')
        )

        self.solicitacao.refresh_from_db()
        self.projeto.refresh_from_db()

        self.assertEqual(
            self.solicitacao.status,
            'APROVADA'
        )

        self.assertEqual(
            self.solicitacao.motivo_decisao,
            'Dados conferidos e horário disponível.'
        )

        self.assertEqual(
            self.solicitacao.decidida_por,
            self.usuario_coordenacao
        )

        self.assertIsNotNone(
            self.solicitacao.data_decisao
        )

        self.assertEqual(
            self.projeto.status,
            'APROVADO'
        )

        banca = BancaTCC.objects.get(
            projeto_tcc=self.projeto
        )

        self.assertEqual(
            banca.espaco,
            self.espaco
        )

        self.assertEqual(
            banca.data_horario_inicio,
            self.solicitacao.opcao_data_inicio
        )

        self.assertEqual(
            banca.data_horario_fim,
            self.solicitacao.opcao_data_fim
        )

    def test_recusa_nao_cria_banca(self):

        self.client.force_login(
            self.usuario_coordenacao
        )

        response = self.client.post(
            self.url_avaliacao,
            {
                'acao': 'recusar',
                'motivo_decisao': (
                    'Horário indisponível para a defesa.'
                ),
            }
        )

        self.assertRedirects(
            response,
            reverse('dashboard')
        )

        self.solicitacao.refresh_from_db()
        self.projeto.refresh_from_db()

        self.assertEqual(
            self.solicitacao.status,
            'RECUSADA'
        )

        self.assertEqual(
            self.projeto.status,
            'RECUSADA'
        )

        self.assertEqual(
            self.solicitacao.motivo_decisao,
            'Horário indisponível para a defesa.'
        )

        self.assertEqual(
            self.solicitacao.decidida_por,
            self.usuario_coordenacao
        )

        self.assertIsNotNone(
            self.solicitacao.data_decisao
        )

        self.assertFalse(
            BancaTCC.objects.filter(
                projeto_tcc=self.projeto
            ).exists()
        )

    def test_solicitacao_nao_pode_ser_decidida_duas_vezes(self):

        self.client.force_login(
            self.usuario_coordenacao
        )

        self.client.post(
            self.url_avaliacao,
            {
                'acao': 'aprovar',
                'motivo_decisao': 'Primeira decisão.',
            }
        )

        segunda_resposta = self.client.post(
            self.url_avaliacao,
            {
                'acao': 'recusar',
                'motivo_decisao': 'Tentativa de segunda decisão.',
            }
        )

        self.assertRedirects(
            segunda_resposta,
            reverse('dashboard')
        )

        self.solicitacao.refresh_from_db()

        self.assertEqual(
            self.solicitacao.status,
            'APROVADA'
        )

        self.assertEqual(
            self.solicitacao.motivo_decisao,
            'Primeira decisão.'
        )

        self.assertEqual(
            BancaTCC.objects.filter(
                projeto_tcc=self.projeto
            ).count(),
            1
        )

    def test_historico_e_privado_da_coordenacao(self):

        self.client.force_login(
            self.usuario_coordenacao
        )

        motivo_privado = (
            'Justificativa administrativa privada.'
        )

        self.client.post(
            self.url_avaliacao,
            {
                'acao': 'recusar',
                'motivo_decisao': motivo_privado,
            }
        )

        # A Coordenação consegue visualizar o histórico.
        response_coordenacao = self.client.get(
            reverse('dashboard')
        )

        self.assertContains(
            response_coordenacao,
            'Histórico de Decisões'
        )

        self.assertContains(
            response_coordenacao,
            motivo_privado
        )

        # O docente não recebe o histórico administrativo.
        self.client.force_login(
            self.usuario_docente
        )

        response_docente = self.client.get(
            reverse('dashboard')
        )

        self.assertNotContains(
            response_docente,
            'Histórico de Decisões'
        )

        self.assertNotContains(
            response_docente,
            motivo_privado
        )

# Testes do acesso protegido ao arquivo do TCC
class DownloadTCCPermissionsTests(TestCase):

    def setUp(self):

        self.usuario_coordenacao = User.objects.create(
            username='coordenacao.download@ufac.br'
        )

        self.coordenacao = pUsuario.objects.create(
            usuario=self.usuario_coordenacao,
            perfil='COORDENACAO'
        )

        self.usuario_solicitante = User.objects.create(
            username='solicitante.download@ufac.br'
        )

        self.solicitante = pUsuario.objects.create(
            usuario=self.usuario_solicitante,
            perfil='DOCENTE'
        )

        self.usuario_orientador = User.objects.create(
            username='orientador.download@ufac.br'
        )

        self.orientador = pUsuario.objects.create(
            usuario=self.usuario_orientador,
            perfil='DOCENTE'
        )

        self.usuario_avaliador = User.objects.create(
            username='avaliador.download@ufac.br'
        )

        self.avaliador = pUsuario.objects.create(
            usuario=self.usuario_avaliador,
            perfil='DOCENTE'
        )

        self.usuario_sem_relacao = User.objects.create(
            username='sem.relacao@ufac.br'
        )

        self.docente_sem_relacao = pUsuario.objects.create(
            usuario=self.usuario_sem_relacao,
            perfil='DOCENTE'
        )

        self.discente = Discente.objects.create(
            nome='Discente Download',
            matricula='20269999999'
        )

        self.projeto = ProjetoTCC.objects.create(
            titulo='TCC para Teste de Download',
            resumo='Teste do acesso protegido ao PDF.',
            semestre_letivo='2026.1',
            discente=self.discente
        )

        self.espaco = EspacoFisico.objects.create(
            nome='Sala Download'
        )

        inicio = (
            timezone.now()
            + timedelta(days=30)
        )

        fim = (
            inicio
            + timedelta(hours=2)
        )

        self.solicitacao = (
            SolicitacaoAgendamento.objects.create(
                usuario_solicitante=self.solicitante,
                projeto_tcc=self.projeto,
                espaco=self.espaco,
                opcao_data_inicio=inicio,
                opcao_data_fim=fim,
                status='EM_ANÁLISE',
                arquivo_tcc=criar_pdf_teste(),
            )
        )

        self.addCleanup(
            self.solicitacao.arquivo_tcc.delete,
            save=False
        )

        self.composicao = ComposicaoBanca.objects.create(
            projeto_tcc=self.projeto,
            solicitacao=self.solicitacao,
            orientador=self.orientador,
            avaliador_interno=self.avaliador,
        )

        self.url_download = reverse(
            'baixar_tcc_solicitacao',
            args=[self.solicitacao.id]
        )

    def test_coordenacao_consegue_baixar_tcc(self):

        self.client.force_login(
            self.usuario_coordenacao
        )

        response = self.client.get(
            self.url_download
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertEqual(
            response['Content-Type'],
            'application/pdf'
        )

        response.close()

    def test_solicitante_consegue_baixar_tcc(self):

        self.client.force_login(
            self.usuario_solicitante
        )

        response = self.client.get(
            self.url_download
        )

        self.assertEqual(
            response.status_code,
            200
        )

        response.close()

    def test_membro_da_banca_consegue_baixar_tcc(self):

        self.client.force_login(
            self.usuario_avaliador
        )

        response = self.client.get(
            self.url_download
        )

        self.assertEqual(
            response.status_code,
            200
        )

        response.close()

    def test_docente_sem_relacao_nao_pode_baixar_tcc(self):

        self.client.force_login(
            self.usuario_sem_relacao
        )

        response = self.client.get(
            self.url_download
        )

        self.assertRedirects(
            response,
            reverse('dashboard')
        )