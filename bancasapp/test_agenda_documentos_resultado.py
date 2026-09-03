from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from docx import Document

from .documentos_banca import gerar_docx_ata, montar_dados_ata
from .forms import RegistroNotaBancaForm
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
from .services import montar_agenda_disponibilidades


class BaseAgendaResultadoTests(TestCase):

    def setUp(self):

        usuario_docente = User.objects.create_user(
            username='agenda.docente@ufac.br',
            email='agenda.docente@ufac.br',
            password='Senha123!',
            first_name='Helena',
            last_name='Orientadora',
            is_active=True,
        )

        self.docente = pUsuario.objects.create(
            usuario=usuario_docente,
            perfil='DOCENTE',
            titulacao='PROFA_DRA',
        )

        usuario_avaliador = User.objects.create_user(
            username='agenda.avaliador@ufac.br',
            email='agenda.avaliador@ufac.br',
            password='Senha123!',
            first_name='Paulo',
            last_name='Avaliador',
            is_active=True,
        )

        self.avaliador = pUsuario.objects.create(
            usuario=usuario_avaliador,
            perfil='DOCENTE',
            titulacao='PROF_DR',
        )

        self.usuario_coordenacao = User.objects.create_user(
            username='agenda.coordenacao@ufac.br',
            password='Senha123!',
            is_active=True,
        )

        pUsuario.objects.create(
            usuario=self.usuario_coordenacao,
            perfil='COORDENACAO',
        )

        self.espaco = EspacoFisico.objects.create(
            nome='Laboratório da Agenda',
        )

        futuro = timezone.localtime(
            timezone.now() + timedelta(days=20)
        )

        self.inicio = futuro.replace(
            hour=8,
            minute=0,
            second=0,
            microsecond=0,
        )
        self.fim = self.inicio.replace(hour=12)

        self.disponibilidade = DisponibilidadeEspaco.objects.create(
            espaco=self.espaco,
            data_hora_inicio=self.inicio,
            data_hora_fim=self.fim,
            ativo=True,
        )

        self.contador = 0

    def criar_solicitacao(self, inicio, fim, status):

        self.contador += 1

        discente = Discente.objects.create(
            nome=f'Discente {self.contador}',
            matricula=f'{20260000000 + self.contador}',
        )

        projeto = ProjetoTCC.objects.create(
            titulo=f'Projeto da agenda {self.contador}',
            resumo='Resumo válido para o projeto da agenda.',
            semestre_letivo='2026.2',
            discente=discente,
            status=(
                'APROVADO'
                if status == 'APROVADA'
                else 'EM_ANÁLISE'
            ),
        )

        return SolicitacaoAgendamento.objects.create(
            usuario_solicitante=self.docente,
            projeto_tcc=projeto,
            espaco=self.espaco,
            opcao_data_inicio=inicio,
            opcao_data_fim=fim,
            status=status,
        )


class AgendaDisponibilidadesTests(BaseAgendaResultadoTests):

    def preparar_reservas(self):

        self.criar_solicitacao(
            self.inicio.replace(hour=9),
            self.inicio.replace(hour=10),
            'EM_ANÁLISE',
        )
        self.criar_solicitacao(
            self.inicio.replace(hour=10),
            self.inicio.replace(hour=10, minute=30),
            'APROVADA',
        )
        self.criar_solicitacao(
            self.inicio.replace(hour=10, minute=30),
            self.inicio.replace(hour=11),
            'RECUSADA',
        )
        self.criar_solicitacao(
            self.inicio.replace(hour=11),
            self.inicio.replace(hour=11, minute=30),
            'EXPIRADA',
        )

    def test_agenda_une_reservas_consecutivas(self):

        self.preparar_reservas()

        agenda = montar_agenda_disponibilidades(
            [self.disponibilidade],
            agora=self.inicio - timedelta(hours=1),
        )

        ocupados = agenda[0].intervalos_ocupados

        self.assertEqual(len(ocupados), 1)
        self.assertEqual(
            ocupados[0]['inicio'],
            self.inicio.replace(hour=9),
        )
        self.assertEqual(
            ocupados[0]['fim'],
            self.inicio.replace(hour=10, minute=30),
        )

    def test_recusada_e_expirada_nao_bloqueiam_horario(self):

        self.preparar_reservas()

        agenda = montar_agenda_disponibilidades(
            [self.disponibilidade],
            agora=self.inicio - timedelta(hours=1),
        )

        livres = agenda[0].intervalos_livres

        self.assertEqual(len(livres), 2)
        self.assertEqual(
            (livres[0]['inicio'], livres[0]['fim']),
            (
                self.inicio,
                self.inicio.replace(hour=9),
            ),
        )
        self.assertEqual(
            (livres[1]['inicio'], livres[1]['fim']),
            (
                self.inicio.replace(hour=10, minute=30),
                self.fim,
            ),
        )

    def test_tela_exibe_agenda_e_atalho_de_preenchimento(self):

        self.preparar_reservas()
        self.client.force_login(self.docente.usuario)

        response = self.client.get(reverse('solicitar_banca'))

        self.assertContains(response, 'Agenda de horários disponíveis')
        self.assertContains(response, 'Usar período')
        self.assertContains(response, 'Reservados ou em análise')
        self.assertContains(response, 'data-usar-periodo')


class DocumentoNavegacaoTests(BaseAgendaResultadoTests):

    def setUp(self):

        super().setUp()

        self.solicitacao = self.criar_solicitacao(
            self.inicio,
            self.inicio + timedelta(hours=1),
            'APROVADA',
        )

        self.composicao = ComposicaoBanca.objects.create(
            projeto_tcc=self.solicitacao.projeto_tcc,
            solicitacao=self.solicitacao,
            orientador=self.docente,
            avaliador_interno=self.avaliador,
            presidente=self.docente,
        )

        self.banca = BancaTCC.objects.create(
            solicitacao=self.solicitacao,
            projeto_tcc=self.solicitacao.projeto_tcc,
            espaco=self.espaco,
            data_horario_inicio=self.solicitacao.opcao_data_inicio,
            data_horario_fim=self.solicitacao.opcao_data_fim,
            status='AGENDADA',
        )

    def test_documentos_mostra_docente_e_link_para_detalhes(self):

        self.client.force_login(self.usuario_coordenacao)

        response = self.client.get(reverse('documentos'))

        self.assertContains(response, 'Docente solicitante')
        self.assertContains(response, 'Helena Orientadora')
        self.assertContains(
            response,
            reverse(
                'detalhar_solicitacao',
                args=[self.solicitacao.id],
            ),
        )
        self.assertContains(response, 'DETALHES')

    def test_docente_tambem_acessa_detalhes_pela_area_documentos(self):

        self.client.force_login(self.docente.usuario)

        response = self.client.get(
            reverse(
                'detalhar_solicitacao',
                args=[self.solicitacao.id],
            )
        )

        self.assertEqual(response.status_code, 200)


class ResultadoNotaTests(BaseAgendaResultadoTests):

    def test_nota_abaixo_de_oito_resulta_em_reprovacao(self):

        banca = BancaTCC(nota=Decimal('7.99'))

        self.assertEqual(
            banca.resultado_final,
            'REPROVAÇÃO',
        )

    def test_nota_oito_resulta_em_aprovacao(self):

        banca = BancaTCC(nota=Decimal('8.00'))

        self.assertEqual(
            banca.resultado_final,
            'APROVAÇÃO',
        )

    def test_formulario_informa_nota_minima(self):

        formulario = RegistroNotaBancaForm()

        self.assertIn(
            'nota mínima para aprovação é 8,00',
            formulario.fields['nota'].help_text,
        )

    def test_documento_final_exibe_reprovacao(self):

        solicitacao = self.criar_solicitacao(
            self.inicio,
            self.inicio + timedelta(hours=1),
            'APROVADA',
        )

        composicao = ComposicaoBanca.objects.create(
            projeto_tcc=solicitacao.projeto_tcc,
            solicitacao=solicitacao,
            orientador=self.docente,
            avaliador_interno=self.avaliador,
            presidente=self.docente,
        )

        banca = BancaTCC.objects.create(
            solicitacao=solicitacao,
            projeto_tcc=solicitacao.projeto_tcc,
            espaco=self.espaco,
            data_horario_inicio=solicitacao.opcao_data_inicio,
            data_horario_fim=solicitacao.opcao_data_fim,
            status='FINALIZADA',
            nota=Decimal('7.50'),
        )

        dados = montar_dados_ata(
            solicitacao,
            composicao,
            banca,
        )

        documento = Document(gerar_docx_ata(dados))
        texto = '\n'.join(
            paragrafo.text
            for paragrafo in documento.paragraphs
        )

        self.assertIn('deliberou pela REPROVAÇÃO', texto)

