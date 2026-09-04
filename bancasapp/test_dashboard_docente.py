from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    BancaTCC,
    ComposicaoBanca,
    Discente,
    DisponibilidadeEspaco,
    EspacoFisico,
    ProjetoTCC,
    SolicitacaoAgendamento,
    pUsuario,
)


class DashboardDocenteTests(TestCase):

    def setUp(self):

        usuario_docente = User.objects.create_user(
            username='painel.docente@ufac.br',
            email='painel.docente@ufac.br',
            password='Senha123!',
            first_name='Ana',
            last_name='Docente',
            is_active=True,
        )

        self.docente = pUsuario.objects.create(
            usuario=usuario_docente,
            perfil='DOCENTE',
        )

        usuario_outro = User.objects.create_user(
            username='painel.outro@ufac.br',
            email='painel.outro@ufac.br',
            password='Senha123!',
            first_name='Bruno',
            last_name='Docente',
            is_active=True,
        )

        self.outro_docente = pUsuario.objects.create(
            usuario=usuario_outro,
            perfil='DOCENTE',
        )

        usuario_terceiro = User.objects.create_user(
            username='painel.terceiro@ufac.br',
            email='painel.terceiro@ufac.br',
            password='Senha123!',
            first_name='Carla',
            last_name='Docente',
            is_active=True,
        )

        self.terceiro_docente = pUsuario.objects.create(
            usuario=usuario_terceiro,
            perfil='DOCENTE',
        )

        self.usuario_coordenacao = User.objects.create_user(
            username='painel.coordenacao@ufac.br',
            email='painel.coordenacao@ufac.br',
            password='Senha123!',
            is_active=True,
        )

        pUsuario.objects.create(
            usuario=self.usuario_coordenacao,
            perfil='COORDENACAO',
        )

        self.inicio = (
            timezone.localtime(
                timezone.now() + timedelta(days=10)
            )
            .replace(
                hour=14,
                minute=0,
                second=0,
                microsecond=0,
            )
        )

        self.contador = 0

    def criar_solicitacao(
        self,
        solicitante,
        espaco,
        inicio,
        fim,
        status='EM_ANÁLISE',
        titulo=None,
    ):

        self.contador += 1

        discente = Discente.objects.create(
            nome=f'Discente do painel {self.contador}',
            matricula=f'{20269000000 + self.contador}',
        )

        projeto = ProjetoTCC.objects.create(
            titulo=(
                titulo
                or f'Projeto do painel {self.contador}'
            ),
            resumo='Resumo do projeto usado no painel.',
            semestre_letivo='2026.2',
            discente=discente,
            status=(
                'APROVADO'
                if status == 'APROVADA'
                else 'EM_ANÁLISE'
            ),
        )

        return SolicitacaoAgendamento.objects.create(
            usuario_solicitante=solicitante,
            projeto_tcc=projeto,
            espaco=espaco,
            opcao_data_inicio=inicio,
            opcao_data_fim=fim,
            status=status,
        )

    def test_conta_somente_salas_com_horario_realmente_livre(self):

        sala_livre = EspacoFisico.objects.create(
            nome='Laboratório com horário livre'
        )

        sala_ocupada = EspacoFisico.objects.create(
            nome='Laboratório totalmente ocupado'
        )

        sala_inativa = EspacoFisico.objects.create(
            nome='Laboratório inativo',
            ativo=False,
        )

        fim = self.inicio + timedelta(hours=4)

        for sala in [
            sala_livre,
            sala_ocupada,
            sala_inativa
        ]:
            DisponibilidadeEspaco.objects.create(
                espaco=sala,
                data_hora_inicio=self.inicio,
                data_hora_fim=fim,
                ativo=True,
            )

        self.criar_solicitacao(
            self.outro_docente,
            sala_ocupada,
            self.inicio,
            fim,
            status='APROVADA',
        )

        self.client.force_login(
            self.docente.usuario
        )

        response = self.client.get(
            reverse('dashboard')
        )

        self.assertEqual(
            response.context['total_salas'],
            1
        )

        self.assertContains(
            response,
            'Salas disponíveis'
        )

        self.assertContains(
            response,
            sala_livre.nome
        )

        self.assertNotContains(
            response,
            sala_ocupada.nome
        )

        self.assertNotContains(
            response,
            sala_inativa.nome
        )

    def test_agenda_do_painel_e_somente_informativa(self):

        sala = EspacoFisico.objects.create(
            nome='Sala para consulta manual'
        )

        DisponibilidadeEspaco.objects.create(
            espaco=sala,
            data_hora_inicio=self.inicio,
            data_hora_fim=(
                self.inicio + timedelta(hours=2)
            ),
            ativo=True,
        )

        self.client.force_login(
            self.docente.usuario
        )

        response = self.client.get(
            reverse('dashboard')
        )

        self.assertContains(
            response,
            'Próximos horários livres'
        )

        self.assertContains(
            response,
            '14:00–16:00'
        )

        self.assertContains(
            response,
            'informe manualmente'
        )

        self.assertNotContains(
            response,
            'Usar período'
        )

        self.assertNotContains(
            response,
            'data-usar-periodo'
        )

    def test_solicitacoes_recentes_mostram_apenas_as_do_docente(
        self
    ):

        sala = EspacoFisico.objects.create(
            nome='Sala das solicitações recentes'
        )

        self.criar_solicitacao(
            self.docente,
            sala,
            self.inicio,
            self.inicio + timedelta(hours=1),
            titulo='Solicitação visível da docente',
        )

        self.criar_solicitacao(
            self.outro_docente,
            sala,
            self.inicio + timedelta(hours=1),
            self.inicio + timedelta(hours=2),
            titulo='Solicitação privada de outro docente',
        )

        self.client.force_login(
            self.docente.usuario
        )

        response = self.client.get(
            reverse('dashboard')
        )

        self.assertContains(
            response,
            'Solicitação visível da docente'
        )

        self.assertNotContains(
            response,
            'Solicitação privada de outro docente'
        )

    def test_banca_agendada_conta_docente_que_participa(
        self
    ):

        sala = EspacoFisico.objects.create(
            nome='Sala da banca participante'
        )

        solicitacao = self.criar_solicitacao(
            self.outro_docente,
            sala,
            self.inicio,
            self.inicio + timedelta(hours=1),
            status='APROVADA',
        )

        ComposicaoBanca.objects.create(
            solicitacao=solicitacao,
            projeto_tcc=solicitacao.projeto_tcc,
            orientador=self.outro_docente,
            avaliador_interno=self.docente,
            presidente=self.outro_docente,
        )

        BancaTCC.objects.create(
            solicitacao=solicitacao,
            projeto_tcc=solicitacao.projeto_tcc,
            espaco=sala,
            data_horario_inicio=(
                solicitacao.opcao_data_inicio
            ),
            data_horario_fim=(
                solicitacao.opcao_data_fim
            ),
            status='AGENDADA',
        )

        solicitacao_alheia = self.criar_solicitacao(
            self.outro_docente,
            sala,
            self.inicio + timedelta(hours=1),
            self.inicio + timedelta(hours=2),
            status='APROVADA',
        )

        ComposicaoBanca.objects.create(
            solicitacao=solicitacao_alheia,
            projeto_tcc=solicitacao_alheia.projeto_tcc,
            orientador=self.outro_docente,
            avaliador_interno=self.terceiro_docente,
            presidente=self.outro_docente,
        )

        BancaTCC.objects.create(
            solicitacao=solicitacao_alheia,
            projeto_tcc=solicitacao_alheia.projeto_tcc,
            espaco=sala,
            data_horario_inicio=(
                solicitacao_alheia.opcao_data_inicio
            ),
            data_horario_fim=(
                solicitacao_alheia.opcao_data_fim
            ),
            status='AGENDADA',
        )

        self.client.force_login(
            self.docente.usuario
        )

        response = self.client.get(
            reverse('dashboard')
        )

        self.assertEqual(
            response.context['total_bancas'],
            1
        )

    def test_coordenacao_continua_vendo_total_cadastrado(
        self
    ):

        EspacoFisico.objects.create(
            nome='Sala ativa sem disponibilidade'
        )

        EspacoFisico.objects.create(
            nome='Sala inativa cadastrada',
            ativo=False,
        )

        self.client.force_login(
            self.usuario_coordenacao
        )

        response = self.client.get(
            reverse('dashboard')
        )

        self.assertEqual(
            response.context['total_salas'],
            2
        )

        self.assertContains(
            response,
            'Salas cadastradas'
        )

        self.assertNotContains(
            response,
            'Próximos horários livres'
        )

    def test_historico_identifica_o_docente_solicitante(self):

        sala = EspacoFisico.objects.create(
            nome='Sala do histórico administrativo'
        )

        self.criar_solicitacao(
            self.docente,
            sala,
            self.inicio,
            self.inicio + timedelta(hours=1),
            status='APROVADA',
            titulo='Decisão identificada pelo docente',
        )

        self.client.force_login(
            self.usuario_coordenacao
        )

        response = self.client.get(
            reverse('dashboard')
        )

        self.assertContains(
            response,
            'Docente solicitante'
        )

        self.assertContains(
            response,
            str(self.docente)
        )

        self.assertNotContains(
            response,
            '<th>Discente</th>',
            html=True,
        )