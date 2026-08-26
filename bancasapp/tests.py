from django.test import TestCase
from django.contrib.auth.tokens import default_token_generator
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
from django.core import mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from .tokens import token_confirmacao_email

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

    def test_login_sem_manter_conectado_expira_ao_fechar_navegador(
        self
    ):
        response = self.client.post(
            reverse('login'),
            {
                'email': 'docente@ufac.br',
                'senha': 'Senha123!',
            }
        )

        self.assertRedirects(
            response,
            reverse('dashboard')
        )

        self.assertTrue(
            self.client.session.get_expire_at_browser_close()
        )

    def test_login_com_manter_conectado_cria_sessao_persistente(
        self
    ):
        response = self.client.post(
            reverse('login'),
            {
                'email': 'docente@ufac.br',
                'senha': 'Senha123!',
                'manter_conectado': 'on',
            }
        )

        self.assertRedirects(
            response,
            reverse('dashboard')
        )

        self.assertFalse(
            self.client.session.get_expire_at_browser_close()
        )

        self.assertGreater(
            self.client.session.get_expiry_age(),
            0
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

class CadastroDocenteTests(TestCase):

    def setUp(self):

        self.url_cadastro = reverse(
            'cadastrar_docente'
        )

        self.senha = (
            'T9!qZ4@mP7#vL2'
        )

    def dados_validos(self):

        return {
            'first_name': 'Maria',
            'last_name': 'Docente da Silva',
            'email': 'maria.docente@ufac.br',
            'password1': self.senha,
            'password2': self.senha,
        }

    def cadastrar_docente(self):

        response = self.client.post(
            self.url_cadastro,
            self.dados_validos()
        )

        usuario = User.objects.get(
            username='maria.docente@ufac.br'
        )

        return response, usuario

    def url_confirmacao(self, usuario):

        uid = urlsafe_base64_encode(
            force_bytes(usuario.pk)
        )

        token = token_confirmacao_email.make_token(
            usuario
        )

        return reverse(
            'confirmar_email_docente',
            kwargs={
                'uidb64': uid,
                'token': token,
            }
        )

    def test_tela_cadastro_docente_abre(self):

        response = self.client.get(
            self.url_cadastro
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertTemplateUsed(
            response,
            'cadastro_docente.html'
        )

    def test_email_nao_institucional_e_rejeitado(self):

        dados = self.dados_validos()

        dados['email'] = (
            'maria.docente@gmail.com'
        )

        response = self.client.post(
            self.url_cadastro,
            dados
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertContains(
            response,
            'terminado em @ufac.br'
        )

        self.assertEqual(
            User.objects.count(),
            0
        )

    def test_cadastro_valido_cria_docente_nao_confirmado(self):

        response, usuario = (
            self.cadastrar_docente()
        )

        self.assertRedirects(
            response,
            reverse('login')
        )

        perfil = pUsuario.objects.get(
            usuario=usuario
        )

        self.assertEqual(
            usuario.email,
            'maria.docente@ufac.br'
        )

        self.assertEqual(
            usuario.get_full_name(),
            'Maria Docente da Silva'
        )

        self.assertFalse(
            usuario.is_active
        )

        self.assertEqual(
            perfil.perfil,
            'DOCENTE'
        )

        self.assertIsNone(
            perfil.data_confirmacao_email
        )

        self.assertEqual(
            len(mail.outbox),
            1
        )

        self.assertEqual(
            mail.outbox[0].to,
            ['maria.docente@ufac.br']
        )

        self.assertIn(
            '/cadastro/docente/confirmar/',
            mail.outbox[0].body
        )

    def test_email_duplicado_e_rejeitado(self):

        usuario = User.objects.create_user(
            username='maria.docente@ufac.br',
            email='maria.docente@ufac.br',
            password=self.senha
        )

        pUsuario.objects.create(
            usuario=usuario,
            perfil='DOCENTE'
        )

        response = self.client.post(
            self.url_cadastro,
            self.dados_validos()
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertContains(
            response,
            'Já existe um cadastro'
        )

        self.assertEqual(
            User.objects.count(),
            1
        )

    def test_docente_nao_confirmado_nao_consegue_entrar(self):

        usuario = User.objects.create_user(
            username='pendente@ufac.br',
            email='pendente@ufac.br',
            password=self.senha,
            is_active=False
        )

        pUsuario.objects.create(
            usuario=usuario,
            perfil='DOCENTE'
        )

        response = self.client.post(
            reverse('login'),
            {
                'email': 'pendente@ufac.br',
                'senha': self.senha,
            }
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertContains(
            response,
            'Confirme seu e-mail institucional'
        )

        self.assertNotIn(
            '_auth_user_id',
            self.client.session
        )

    def test_link_valido_confirma_email(self):

        _, usuario = self.cadastrar_docente()

        response = self.client.get(
            self.url_confirmacao(
                usuario
            )
        )

        self.assertRedirects(
            response,
            reverse('login')
        )

        usuario.refresh_from_db()

        perfil = pUsuario.objects.get(
            usuario=usuario
        )

        self.assertTrue(
            usuario.is_active
        )

        self.assertIsNotNone(
            perfil.data_confirmacao_email
        )

    def test_docente_confirmado_consegue_entrar(self):

        _, usuario = self.cadastrar_docente()

        self.client.get(
            self.url_confirmacao(
                usuario
            )
        )

        response = self.client.post(
            reverse('login'),
            {
                'email': usuario.email,
                'senha': self.senha,
            }
        )

        self.assertRedirects(
            response,
            reverse('dashboard')
        )

        self.assertIn(
            '_auth_user_id',
            self.client.session
        )

    def test_link_invalido_nao_ativa_usuario(self):

        _, usuario = self.cadastrar_docente()

        uid = urlsafe_base64_encode(
            force_bytes(usuario.pk)
        )

        response = self.client.get(
            reverse(
                'confirmar_email_docente',
                kwargs={
                    'uidb64': uid,
                    'token': 'token-invalido',
                }
            )
        )

        self.assertRedirects(
            response,
            reverse('login')
        )

        usuario.refresh_from_db()

        self.assertFalse(
            usuario.is_active
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
            hour=14,
            minute=0,
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

    def dados_academicos_solicitacao(self):

        return {
            'nome_discente': self.discente.nome,
            'matricula_discente': self.discente.matricula,
            'titulo_tcc': 'Novo Projeto Criado na Solicitação',
            'resumo_tcc': (
                'Resumo acadêmico criado durante a solicitação.'
            ),
            'semestre_letivo': '2026.1',
        }

    def test_horario_fora_da_disponibilidade_e_recusado(self):

        self.client.force_login(
            self.usuario_docente
        )

        inicio_fora = (
            self.disponibilidade.data_hora_fim
            + timedelta(minutes=30)
        )

        fim_fora = (
            inicio_fora
            + timedelta(hours=2)
        )

        response = self.client.post(
            reverse('solicitar_banca'),
            {
                **self.dados_academicos_solicitacao(),

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

                'arquivo_tcc': criar_pdf_teste(),
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
                **self.dados_academicos_solicitacao(),
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
                **self.dados_academicos_solicitacao(),
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
                **self.dados_academicos_solicitacao(),
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
                **self.dados_academicos_solicitacao(),
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
                **self.dados_academicos_solicitacao(),
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

        # O projeto é criado automaticamente pela solicitação.
        self.assertNotEqual(
            solicitacao.projeto_tcc,
            self.projeto
        )

        self.assertEqual(
            solicitacao.projeto_tcc.discente,
            self.discente
        )

        self.assertEqual(
            solicitacao.projeto_tcc.titulo,
            'Novo Projeto Criado na Solicitação'
        )

        self.assertEqual(
            solicitacao.projeto_tcc.status,
            'EM_ANÁLISE'
        )

        # A composição da banca também deve ter sido criada.
        composicao = ComposicaoBanca.objects.get(
            solicitacao=solicitacao
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

        # Deve estar ligada ao projeto criado no novo fluxo.
        self.assertEqual(
            solicitacao.projeto_tcc.discente,
            self.discente
        )

        # A composição da banca também deve ter sido criada
        composicao = ComposicaoBanca.objects.get(
            solicitacao=solicitacao
        )

        self.assertEqual(
            composicao.orientador,
            self.docente
        )

        self.assertEqual(
            composicao.avaliador_interno,
            self.avaliador
        )

    def test_formulario_reune_discente_e_tcc_na_solicitacao(self):

        self.client.force_login(
            self.usuario_docente
        )

        response = self.client.get(
            reverse('solicitar_banca')
        )

        campos = response.context[
            'form'
        ].fields

        self.assertIn(
            'nome_discente',
            campos
        )

        self.assertIn(
            'titulo_tcc',
            campos
        )

        self.assertNotIn(
            'projeto_tcc',
            campos
        )

        self.assertNotIn(
            'status',
            campos
        )

    def test_matricula_existente_com_nome_diferente_e_rejeitada(self):

        self.client.force_login(
            self.usuario_docente
        )

        dados = self.dados_academicos_solicitacao()

        dados.update(
            {
                'nome_discente': 'Outro Nome',
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
                'arquivo_tcc': criar_pdf_teste(),
            }
        )

        response = self.client.post(
            reverse('solicitar_banca'),
            dados
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertContains(
            response,
            'Esta matrícula já pertence ao discente'
        )

        self.assertEqual(
            SolicitacaoAgendamento.objects.count(),
            0
        )

        self.assertEqual(
            ProjetoTCC.objects.count(),
            1
        )

    def test_banca_deve_comecar_e_terminar_no_mesmo_dia(self):

        inicio = self.inicio_agendamento.replace(
            hour=23,
            minute=0
        )

        fim = inicio + timedelta(hours=2)

        self.disponibilidade.data_hora_inicio = (
            inicio - timedelta(hours=1)
        )

        self.disponibilidade.data_hora_fim = (
            fim + timedelta(hours=1)
        )

        self.disponibilidade.save()

        self.client.force_login(
            self.usuario_docente
        )

        dados = self.dados_academicos_solicitacao()

        dados.update(
            {
                'espaco': self.espaco.id,
                'opcao_data_inicio': inicio.strftime(
                    '%Y-%m-%dT%H:%M'
                ),
                'opcao_data_fim': fim.strftime(
                    '%Y-%m-%dT%H:%M'
                ),
                'orientador': self.docente.id,
                'avaliador_interno': self.avaliador.id,
                'arquivo_tcc': criar_pdf_teste(),
            }
        )

        response = self.client.post(
            reverse('solicitar_banca'),
            dados
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertContains(
            response,
            'A banca deve começar e terminar no mesmo dia.'
        )

        self.assertEqual(
            SolicitacaoAgendamento.objects.count(),
            0
        )

    def test_rotas_antigas_redirecionam_para_solicitacao(self):

        self.client.force_login(
            self.usuario_docente
        )

        for nome_rota in [
            'cadastrar_aluno',
            'cadastrar_projeto',
        ]:

            response = self.client.get(
                reverse(nome_rota)
            )

            self.assertRedirects(
                response,
                reverse('solicitar_banca')
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

        self.disponibilidade = (
            DisponibilidadeEspaco.objects.create(
                espaco=self.espaco,
                data_hora_inicio=(
                    inicio
                    - timedelta(hours=1)
                ),
                data_hora_fim=(
                    fim
                    + timedelta(hours=1)
                ),
                ativo=True,
                criada_por=self.usuario_coordenacao,
            )
        )

        self.composicao = ComposicaoBanca.objects.create(
            projeto_tcc=self.projeto,
            solicitacao=self.solicitacao,
            orientador=self.docente,
            avaliador_interno=self.avaliador,
            presidente=self.avaliador,
            nome_avaliador_externo='Avaliador Externo',
            instituicao_avaliador_externo='Instituição Externa'
        )

        self.url_avaliacao = reverse(
            'avaliar_solicitacao',
            args=[self.solicitacao.id]
        )
    def test_coordenacao_consegue_gerar_minuta_pdf(
        self
    ):

        self.solicitacao.status = 'APROVADA'

        self.solicitacao.save(
            update_fields=['status']
        )

        self.client.force_login(
            self.usuario_coordenacao
        )

        response = self.client.get(
            reverse(
                'gerar_pdf_banca',
                args=[self.solicitacao.id]
            )
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertEqual(
            response['Content-Type'],
            'application/pdf'
        )

        self.assertTrue(
            response.content.startswith(
                b'%PDF'
            )
        )


    def test_docente_participante_consegue_gerar_minuta(
        self
    ):

        self.solicitacao.status = 'APROVADA'

        self.solicitacao.save(
            update_fields=['status']
        )

        self.client.force_login(
            self.usuario_docente
        )

        response = self.client.get(
            reverse(
                'gerar_pdf_banca',
                args=[self.solicitacao.id]
            )
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertEqual(
            response['Content-Type'],
            'application/pdf'
        )


    def test_docente_sem_vinculo_nao_gera_minuta(
        self
    ):

        usuario_sem_vinculo = (
            User.objects.create_user(
                username='semvinculo@ufac.br',
                password='Senha123!'
            )
        )

        pUsuario.objects.create(
            usuario=usuario_sem_vinculo,
            perfil='DOCENTE'
        )

        self.solicitacao.status = 'APROVADA'

        self.solicitacao.save(
            update_fields=['status']
        )

        self.client.force_login(
            usuario_sem_vinculo
        )

        response = self.client.get(
            reverse(
                'gerar_pdf_banca',
                args=[self.solicitacao.id]
            )
        )

        self.assertRedirects(
            response,
            reverse('documentos')
        )    

    def test_solicitacao_vencida_e_marcada_como_expirada(
    self
    ):

        agora = timezone.now()

        self.solicitacao.opcao_data_inicio = (
            agora
            - timedelta(minutes=10)
        )

        self.solicitacao.opcao_data_fim = (
            agora
            + timedelta(hours=1)
        )

        self.solicitacao.save(
            update_fields=[
                'opcao_data_inicio',
                'opcao_data_fim',
            ]
        )

        self.client.force_login(
            self.usuario_coordenacao
        )

        response = self.client.get(
            reverse('solicitacoes_coordenacao')
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.solicitacao.refresh_from_db()

        self.assertEqual(
            self.solicitacao.status,
            'EXPIRADA'
        )

        self.assertContains(
            response,
            'Expirada'
        )


    def test_solicitacao_expirada_nao_pode_ser_avaliada(
        self
    ):

        agora = timezone.now()

        self.solicitacao.opcao_data_inicio = (
            agora
            - timedelta(hours=2)
        )

        self.solicitacao.opcao_data_fim = (
            agora
            - timedelta(hours=1)
        )

        self.solicitacao.save(
            update_fields=[
                'opcao_data_inicio',
                'opcao_data_fim',
            ]
        )

        self.client.force_login(
            self.usuario_coordenacao
        )

        response = self.client.get(
            self.url_avaliacao
        )

        self.assertRedirects(
            response,
            reverse('solicitacoes_coordenacao')
        )

        self.solicitacao.refresh_from_db()

        self.assertEqual(
            self.solicitacao.status,
            'EXPIRADA'
        )

        self.assertEqual(
            BancaTCC.objects.count(),
            0
        )


    def test_aprovacao_revalida_disponibilidade(
        self
    ):

        self.disponibilidade.ativo = False

        self.disponibilidade.save(
            update_fields=['ativo']
        )

        self.client.force_login(
            self.usuario_coordenacao
        )

        response = self.client.post(
            self.url_avaliacao,
            {
                'acao': 'aprovar',
                'motivo_decisao': (
                    'Tentativa depois da indisponibilidade.'
                ),
            }
        )

        self.assertRedirects(
            response,
            reverse(
                'editar_solicitacao_coordenacao',
                args=[self.solicitacao.id]
            )
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

    def test_presidente_e_obrigatorio_para_aprovar(self):

        self.composicao.presidente = None

        self.composicao.save(
            update_fields=['presidente']
        )

        self.client.force_login(
            self.usuario_coordenacao
        )

        response = self.client.post(
            self.url_avaliacao,
            {
                'acao': 'aprovar',
                'presidente': '',
                'motivo_decisao': (
                    'Tentativa sem definir presidente.'
                ),
            }
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertContains(
            response,
            'Selecione o presidente da banca'
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

    def test_coordenacao_define_presidente_ao_aprovar(self):

        self.composicao.presidente = None

        self.composicao.save(
            update_fields=['presidente']
        )

        self.client.force_login(
            self.usuario_coordenacao
        )

        response = self.client.post(
            self.url_avaliacao,
            {
                'acao': 'aprovar',
                'presidente': self.avaliador.id,
                'motivo_decisao': (
                    'Presidente definido pela Coordenação.'
                ),
            }
        )

        self.assertRedirects(
            response,
            reverse('dashboard')
        )

        self.solicitacao.refresh_from_db()
        self.composicao.refresh_from_db()

        self.assertEqual(
            self.solicitacao.status,
            'APROVADA'
        )

        self.assertEqual(
            self.composicao.presidente,
            self.avaliador
        )

        self.assertEqual(
            BancaTCC.objects.count(),
            1
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
    def test_aprovacao_envia_email_ao_docente(self):

        self.client.force_login(
            self.usuario_coordenacao
        )

        self.client.post(
            self.url_avaliacao,
            {
                'acao': 'aprovar',
                'motivo_decisao': (
                    'Dados conferidos pela Coordenação.'
                ),
            }
        )

        self.assertEqual(
            len(mail.outbox),
            1
        )

        email = mail.outbox[0]

        self.assertEqual(
            email.to,
            ['docente_avaliacao@ufac.br']
        )

        self.assertIn(
            'Banca aprovada no SGTCC',
            email.subject
        )

        self.assertIn(
            'Dados conferidos pela Coordenação.',
            email.body
        )

        self.assertIn(
            reverse(
                'detalhar_solicitacao',
                args=[self.solicitacao.id]
            ),
            email.body
        )

    def test_recusa_envia_email_com_justificativa(self):

        self.client.force_login(
            self.usuario_coordenacao
        )

        self.client.post(
            self.url_avaliacao,
            {
                'acao': 'recusar',
                'motivo_decisao': (
                    'Solicitação recusada por conflito administrativo.'
                ),
            }
        )

        self.assertEqual(
            len(mail.outbox),
            1
        )

        email = mail.outbox[0]

        self.assertEqual(
            email.to,
            ['docente_avaliacao@ufac.br']
        )

        self.assertIn(
            'Solicitação de banca recusada no SGTCC',
            email.subject
        )

        self.assertIn(
            'Solicitação recusada por conflito administrativo.',
            email.body
        )

        self.assertIn(
            reverse(
                'detalhar_solicitacao',
                args=[self.solicitacao.id]
            ),
            email.body
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
            reverse('solicitacoes_coordenacao')
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

class ReenvioConfirmacaoTests(TestCase):

    def setUp(self):

        self.url_reenvio = reverse(
            'reenviar_confirmacao_docente'
        )

        self.email = (
            'docente.reenvio@ufac.br'
        )

        self.senha = (
            'T9!qZ4@mP7#vL2'
        )

    def criar_docente(
        self,
        ativo=False
    ):

        usuario = User.objects.create_user(
            username=self.email,
            email=self.email,
            password=self.senha,
            is_active=ativo
        )

        pUsuario.objects.create(
            usuario=usuario,
            perfil='DOCENTE'
        )

        return usuario

    def test_tela_reenvio_abre(self):

        response = self.client.get(
            self.url_reenvio
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertTemplateUsed(
            response,
            'reenviar_confirmacao.html'
        )

    def test_reenvio_para_docente_nao_confirmado(
        self
    ):

        self.criar_docente(
            ativo=False
        )

        response = self.client.post(
            self.url_reenvio,
            {
                'email': self.email,
            }
        )

        self.assertRedirects(
            response,
            reverse('login')
        )

        self.assertEqual(
            len(mail.outbox),
            1
        )

        self.assertEqual(
            mail.outbox[0].to,
            [
                self.email,
            ]
        )

        self.assertIn(
            '/cadastro/docente/confirmar/',
            mail.outbox[0].body
        )

    def test_conta_confirmada_nao_recebe_novo_link(
        self
    ):

        self.criar_docente(
            ativo=True
        )

        response = self.client.post(
            self.url_reenvio,
            {
                'email': self.email,
            }
        )

        self.assertRedirects(
            response,
            reverse('login')
        )

        self.assertEqual(
            len(mail.outbox),
            0
        )

    def test_email_inexistente_nao_revela_cadastro(
        self
    ):

        response = self.client.post(
            self.url_reenvio,
            {
                'email': 'inexistente@ufac.br',
            }
        )

        self.assertRedirects(
            response,
            reverse('login')
        )

        self.assertEqual(
            len(mail.outbox),
            0
        )

    def test_reenvio_respeita_intervalo_de_60_segundos(
        self
    ):

        self.criar_docente(
            ativo=False
        )

        primeiro_reenvio = self.client.post(
            self.url_reenvio,
            {
                'email': self.email,
            }
        )

        self.assertRedirects(
            primeiro_reenvio,
            reverse('login')
        )

        segundo_reenvio = self.client.post(
            self.url_reenvio,
            {
                'email': self.email,
            }
        )

        self.assertEqual(
            segundo_reenvio.status_code,
            200
        )

        self.assertContains(
            segundo_reenvio,
            'Aguarde 60 segundos'
        )

        self.assertEqual(
            len(mail.outbox),
            1
        )

class RecuperacaoSenhaTests(TestCase):

    def setUp(self):

        self.url_recuperacao = reverse(
            'recuperar_senha'
        )

        self.email = 'docente.senha@ufac.br'
        self.senha_antiga = 'T9!qZ4@mP7#vL2'
        self.senha_nova = 'N8@vaSenha#2026'

        self.usuario = User.objects.create_user(
            username=self.email,
            email=self.email,
            password=self.senha_antiga,
            first_name='Docente',
            last_name='Teste',
            is_active=True
        )

        pUsuario.objects.create(
            usuario=self.usuario,
            perfil='DOCENTE'
        )

    def criar_url_redefinicao(self):

        uid = urlsafe_base64_encode(
            force_bytes(
                self.usuario.pk
            )
        )

        token = default_token_generator.make_token(
            self.usuario
        )

        return reverse(
            'redefinir_senha',
            kwargs={
                'uidb64': uid,
                'token': token,
            }
        )

    def test_tela_recuperacao_senha_abre(self):

        response = self.client.get(
            self.url_recuperacao
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertTemplateUsed(
            response,
            'recuperar_senha.html'
        )

    def test_conta_ativa_recebe_link_recuperacao(self):

        response = self.client.post(
            self.url_recuperacao,
            {
                'email': self.email.upper(),
            }
        )

        self.assertRedirects(
            response,
            reverse(
                'recuperar_senha_enviada'
            )
        )

        self.assertEqual(
            len(mail.outbox),
            1
        )

        self.assertEqual(
            mail.outbox[0].to,
            [
                self.email,
            ]
        )

        self.assertIn(
            '/senha/redefinir/',
            mail.outbox[0].body
        )

    def test_conta_inativa_nao_recebe_link(self):

        self.usuario.is_active = False

        self.usuario.save(
            update_fields=[
                'is_active',
            ]
        )

        response = self.client.post(
            self.url_recuperacao,
            {
                'email': self.email,
            }
        )

        self.assertRedirects(
            response,
            reverse(
                'recuperar_senha_enviada'
            )
        )

        self.assertEqual(
            len(mail.outbox),
            0
        )

    def test_email_inexistente_nao_revela_cadastro(self):

        response = self.client.post(
            self.url_recuperacao,
            {
                'email': 'nao.existe@ufac.br',
            }
        )

        self.assertRedirects(
            response,
            reverse(
                'recuperar_senha_enviada'
            )
        )

        self.assertEqual(
            len(mail.outbox),
            0
        )

    def test_link_valido_permite_alterar_senha(self):

        url_original = (
            self.criar_url_redefinicao()
        )

        primeira_resposta = self.client.get(
            url_original
        )

        self.assertEqual(
            primeira_resposta.status_code,
            302
        )

        response = self.client.post(
            primeira_resposta.url,
            {
                'new_password1': self.senha_nova,
                'new_password2': self.senha_nova,
            }
        )

        self.assertRedirects(
            response,
            reverse(
                'redefinir_senha_concluida'
            )
        )

        self.usuario.refresh_from_db()

        self.assertTrue(
            self.usuario.check_password(
                self.senha_nova
            )
        )

        self.assertFalse(
            self.usuario.check_password(
                self.senha_antiga
            )
        )

    def test_link_utilizado_nao_pode_ser_reutilizado(self):

        url_original = (
            self.criar_url_redefinicao()
        )

        primeira_resposta = self.client.get(
            url_original
        )

        self.client.post(
            primeira_resposta.url,
            {
                'new_password1': self.senha_nova,
                'new_password2': self.senha_nova,
            }
        )

        response = self.client.get(
            url_original
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertContains(
            response,
            'Link inválido'
        )

        self.assertContains(
            response,
            'Solicitar outro link'
        )

    def test_token_invalido_e_rejeitado(self):

        uid = urlsafe_base64_encode(
            force_bytes(
                self.usuario.pk
            )
        )

        response = self.client.get(
            reverse(
                'redefinir_senha',
                kwargs={
                    'uidb64': uid,
                    'token': 'token-invalido',
                }
            )
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertContains(
            response,
            'Link inválido'
        )

        self.assertContains(
            response,
            'Solicitar outro link'
        )

class PermissoesPerfilTests(TestCase):

    def setUp(self):

        self.senha = 'T9!qZ4@mP7#vL2'

        self.usuario_coordenacao = User.objects.create_user(
            username='coordenacao.permissoes@ufac.br',
            email='coordenacao.permissoes@ufac.br',
            password=self.senha,
            is_active=True
        )

        self.coordenacao = pUsuario.objects.create(
            usuario=self.usuario_coordenacao,
            perfil='COORDENACAO'
        )

        self.usuario_docente = User.objects.create_user(
            username='docente.permissoes@ufac.br',
            email='docente.permissoes@ufac.br',
            password=self.senha,
            is_active=True
        )

        self.docente = pUsuario.objects.create(
            usuario=self.usuario_docente,
            perfil='DOCENTE'
        )

        self.usuario_outro_docente = User.objects.create_user(
            username='outro.docente@ufac.br',
            email='outro.docente@ufac.br',
            password=self.senha,
            is_active=True
        )

        self.outro_docente = pUsuario.objects.create(
            usuario=self.usuario_outro_docente,
            perfil='DOCENTE'
        )

        self.espaco = EspacoFisico.objects.create(
            nome='Sala de Teste de Permissões',
            ativo=True
        )

        self.discente_docente = Discente.objects.create(
            nome='Aluno do Docente Logado',
            matricula='20260000031'
        )

        self.projeto_docente = ProjetoTCC.objects.create(
            titulo='Projeto Visível do Docente',
            resumo='Projeto pertencente ao docente logado.',
            semestre_letivo='2026.2',
            discente=self.discente_docente
        )

        self.discente_outro = Discente.objects.create(
            nome='Aluno de Outro Docente',
            matricula='20260000032'
        )

        self.projeto_outro = ProjetoTCC.objects.create(
            titulo='Projeto Privado de Outro Docente',
            resumo='Projeto que não pertence ao docente logado.',
            semestre_letivo='2026.2',
            discente=self.discente_outro
        )

        inicio = timezone.now() + timedelta(
            days=30
        )

        fim = inicio + timedelta(
            hours=2
        )

        self.solicitacao_docente = (
            SolicitacaoAgendamento.objects.create(
                usuario_solicitante=self.docente,
                projeto_tcc=self.projeto_docente,
                espaco=self.espaco,
                opcao_data_inicio=inicio,
                opcao_data_fim=fim,
                status='EM_ANÁLISE'
            )
        )

        self.solicitacao_outro = (
            SolicitacaoAgendamento.objects.create(
                usuario_solicitante=self.outro_docente,
                projeto_tcc=self.projeto_outro,
                espaco=self.espaco,
                opcao_data_inicio=(
                    inicio + timedelta(days=1)
                ),
                opcao_data_fim=(
                    fim + timedelta(days=1)
                ),
                status='EM_ANÁLISE'
            )
        )

    def test_menu_coordenacao_exibe_apenas_funcoes_administrativas(
        self
    ):

        self.client.force_login(
            self.usuario_coordenacao
        )

        response = self.client.get(
            reverse('dashboard')
        )

        self.assertContains(
            response,
            'ANALISAR SOLICITAÇÕES'
        )

        self.assertContains(
            response,
            'GERENCIAR SALAS'
        )

        for texto_indisponivel in [
            'MINHAS SOLICITAÇÕES',
            'SOLICITAR BANCA',
            'CADASTRAR ALUNO',
            'CADASTRAR PROJETO',
            'BANCAS CADASTRADAS',
        ]:

            self.assertNotContains(
                response,
                texto_indisponivel
            )

    def test_menu_docente_nao_exibe_funcoes_administrativas(
        self
    ):

        self.client.force_login(
            self.usuario_docente
        )

        response = self.client.get(
            reverse('dashboard')
        )

        self.assertContains(
            response,
            'MINHAS SOLICITAÇÕES'
        )

        self.assertContains(
            response,
            'SOLICITAR BANCA'
        )

        self.assertNotContains(
            response,
            'ANALISAR SOLICITAÇÕES'
        )

        self.assertNotContains(
            response,
            'GERENCIAR SALAS'
        )

        self.assertNotContains(
            response,
            'BANCAS CADASTRADAS'
        )

    def test_coordenacao_nao_acessa_rotas_exclusivas_docente(
        self
    ):

        self.client.force_login(
            self.usuario_coordenacao
        )

        rotas_docente = [
            'visualizar_bancas',
            'solicitar_banca',
            'cadastrar_aluno',
            'cadastrar_projeto',
            'meus_tccs',
        ]

        for nome_rota in rotas_docente:

            response = self.client.get(
                reverse(nome_rota)
            )

            self.assertRedirects(
                response,
                reverse('dashboard')
            )

    def test_docente_nao_acessa_rotas_exclusivas_coordenacao(
        self
    ):

        self.client.force_login(
            self.usuario_docente
        )

        rotas_coordenacao = [
            'solicitacoes_coordenacao',
            'gerenciar_espacos',
        ]

        for nome_rota in rotas_coordenacao:

            response = self.client.get(
                reverse(nome_rota)
            )

            self.assertRedirects(
                response,
                reverse('dashboard')
            )

    def test_url_antiga_meus_tccs_redireciona_docente(
        self
    ):

        self.client.force_login(
            self.usuario_docente
        )

        response = self.client.get(
            reverse('meus_tccs')
        )

        self.assertRedirects(
            response,
            reverse('visualizar_bancas')
        )

    def test_pesquisa_docente_nao_exibe_solicitacao_alheia(
        self
    ):

        self.client.force_login(
            self.usuario_docente
        )

        response = self.client.get(
            reverse('pesquisar'),
            {
                'q': 'Projeto',
            }
        )

        self.assertContains(
            response,
            self.projeto_docente.titulo
        )

        self.assertNotContains(
            response,
            self.projeto_outro.titulo
        )

    def test_pesquisa_docente_exibe_banca_em_que_participa(
        self
    ):

        ComposicaoBanca.objects.create(
            projeto_tcc=self.projeto_outro,
            solicitacao=self.solicitacao_outro,
            orientador=self.outro_docente,
            avaliador_interno=self.docente
        )

        self.client.force_login(
            self.usuario_docente
        )

        response = self.client.get(
            reverse('pesquisar'),
            {
                'q': self.projeto_outro.titulo,
            }
        )

        self.assertContains(
            response,
            self.projeto_outro.titulo
        )

    def test_pesquisa_coordenacao_exibe_todas_solicitacoes(
        self
    ):

        self.client.force_login(
            self.usuario_coordenacao
        )

        response = self.client.get(
            reverse('pesquisar'),
            {
                'q': 'Projeto',
            }
        )

        self.assertContains(
            response,
            self.projeto_docente.titulo
        )

        self.assertContains(
            response,
            self.projeto_outro.titulo
        )

    def test_usuario_sem_perfil_nao_acessa_area_interna(
        self
    ):

        usuario_sem_perfil = User.objects.create_user(
            username='sem.perfil@ufac.br',
            email='sem.perfil@ufac.br',
            password=self.senha,
            is_active=True
        )

        self.client.force_login(
            usuario_sem_perfil
        )

        response = self.client.get(
            reverse('documentos')
        )

        self.assertRedirects(
            response,
            reverse('login')
        )

        self.assertNotIn(
            '_auth_user_id',
            self.client.session
        )

class DetalhesSolicitacaoTests(TestCase):

    def setUp(self):
        self.senha = 'T9!qZ4@mP7#vL2'

        self.usuario_coordenacao = User.objects.create_user(
            username='coordenacao.detalhes@ufac.br',
            password=self.senha,
            is_active=True
        )

        pUsuario.objects.create(
            usuario=self.usuario_coordenacao,
            perfil='COORDENACAO'
        )

        self.usuario_solicitante = User.objects.create_user(
            username='solicitante.detalhes@ufac.br',
            password=self.senha,
            is_active=True
        )

        self.solicitante = pUsuario.objects.create(
            usuario=self.usuario_solicitante,
            perfil='DOCENTE'
        )

        self.usuario_orientador = User.objects.create_user(
            username='orientador.detalhes@ufac.br',
            password=self.senha,
            is_active=True
        )

        self.orientador = pUsuario.objects.create(
            usuario=self.usuario_orientador,
            perfil='DOCENTE'
        )

        self.usuario_avaliador = User.objects.create_user(
            username='avaliador.detalhes@ufac.br',
            password=self.senha,
            is_active=True
        )

        self.avaliador = pUsuario.objects.create(
            usuario=self.usuario_avaliador,
            perfil='DOCENTE'
        )

        self.usuario_sem_vinculo = User.objects.create_user(
            username='sem.vinculo.detalhes@ufac.br',
            password=self.senha,
            is_active=True
        )

        pUsuario.objects.create(
            usuario=self.usuario_sem_vinculo,
            perfil='DOCENTE'
        )

        self.discente = Discente.objects.create(
            nome='Discente dos Detalhes',
            matricula='20260000041'
        )

        self.projeto = ProjetoTCC.objects.create(
            titulo='Projeto da Tela de Detalhes',
            resumo='Resumo exibido na tela de detalhes.',
            semestre_letivo='2026.2',
            discente=self.discente
        )

        self.espaco = EspacoFisico.objects.create(
            nome='Sala dos Detalhes',
            ativo=True
        )

        inicio = timezone.now() + timedelta(days=30)

        self.solicitacao = SolicitacaoAgendamento.objects.create(
            usuario_solicitante=self.solicitante,
            projeto_tcc=self.projeto,
            espaco=self.espaco,
            opcao_data_inicio=inicio,
            opcao_data_fim=inicio + timedelta(hours=2),
            status='EM_ANÁLISE'
        )

        self.composicao = ComposicaoBanca.objects.create(
            projeto_tcc=self.projeto,
            solicitacao=self.solicitacao,
            orientador=self.orientador,
            avaliador_interno=self.avaliador
        )

        self.url_detalhes = reverse(
            'detalhar_solicitacao',
            args=[self.solicitacao.id]
        )

    def test_coordenacao_acessa_detalhes(self):
        self.client.force_login(
            self.usuario_coordenacao
        )

        response = self.client.get(
            self.url_detalhes
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertTemplateUsed(
            response,
            'detalhar_solicitacao.html'
        )

        self.assertContains(
            response,
            'AVALIAR SOLICITAÇÃO'
        )

    def test_solicitante_acessa_detalhes(self):
        self.client.force_login(
            self.usuario_solicitante
        )

        response = self.client.get(
            self.url_detalhes
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertContains(
            response,
            self.projeto.titulo
        )

        self.assertNotContains(
            response,
            'AVALIAR SOLICITAÇÃO'
        )

    def test_integrante_da_banca_acessa_detalhes(self):
        self.client.force_login(
            self.usuario_orientador
        )

        response = self.client.get(
            self.url_detalhes
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertContains(
            response,
            self.projeto.titulo
        )

    def test_docente_sem_vinculo_nao_acessa_detalhes(self):
        self.client.force_login(
            self.usuario_sem_vinculo
        )

        response = self.client.get(
            self.url_detalhes
        )

        self.assertRedirects(
            response,
            reverse('visualizar_bancas')
        )

    def test_lista_docente_exibe_link_de_detalhes(self):
        self.client.force_login(
            self.usuario_solicitante
        )

        response = self.client.get(
            reverse('visualizar_bancas')
        )

        self.assertContains(
            response,
            self.url_detalhes
        )

    def test_pesquisa_exibe_link_de_detalhes(self):
        self.client.force_login(
            self.usuario_solicitante
        )

        response = self.client.get(
            reverse('pesquisar'),
            {
                'q': self.projeto.titulo,
            }
        )

        self.assertContains(
            response,
            self.url_detalhes
        )

    def test_solicitacao_recusada_exibe_justificativa(self):
        self.solicitacao.status = 'RECUSADA'

        self.solicitacao.motivo_decisao = (
            'A composição precisa ser corrigida.'
        )

        self.solicitacao.data_decisao = timezone.now()

        self.solicitacao.save(
            update_fields=[
                'status',
                'motivo_decisao',
                'data_decisao',
            ]
        )

        self.client.force_login(
            self.usuario_solicitante
        )

        response = self.client.get(
            self.url_detalhes
        )

        self.assertContains(
            response,
            'A composição precisa ser corrigida.'
        )

    def test_solicitante_nao_membro_gera_documento_aprovado(
        self
    ):
        self.solicitacao.status = 'APROVADA'

        self.solicitacao.save(
            update_fields=['status']
        )

        self.client.force_login(
            self.usuario_solicitante
        )

        response = self.client.get(
            reverse(
                'gerar_pdf_banca',
                args=[self.solicitacao.id]
            )
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertEqual(
            response['Content-Type'],
            'application/pdf'
        )
