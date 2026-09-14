from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
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
from .services import SolicitacaoBancaInvalida


def arquivo_pdf_teste():
    return SimpleUploadedFile(
        'tcc.pdf',
        b'%PDF-1.4\n% arquivo de teste\n',
        content_type='application/pdf',
    )


class RegraMatriculaTCCTests(TestCase):

    def setUp(self):
        self.orientador = self._criar_docente(
            'orientador.matricula@ufac.br',
            'Orientador Matrícula',
        )
        self.outro_orientador = self._criar_docente(
            'outro.orientador@ufac.br',
            'Outro Orientador',
        )
        self.avaliador = self._criar_docente(
            'avaliador.matricula@ufac.br',
            'Avaliador Matrícula',
        )

        self.espaco = EspacoFisico.objects.create(
            nome='Laboratório Regra Matrícula',
        )

        self.inicio = (
            timezone.localtime(timezone.now())
            + timedelta(days=20)
        ).replace(
            hour=14,
            minute=0,
            second=0,
            microsecond=0,
        )

        DisponibilidadeEspaco.objects.create(
            espaco=self.espaco,
            data_hora_inicio=self.inicio - timedelta(hours=1),
            data_hora_fim=self.inicio + timedelta(hours=6),
            ativo=True,
            criada_por=self.orientador.usuario,
        )

    def _criar_docente(self, email, nome):
        usuario = User.objects.create_user(
            username=email,
            email=email,
            first_name=nome,
            password='SenhaForte#2026',
        )
        return pUsuario.objects.create(
            usuario=usuario,
            perfil='DOCENTE',
        )

    def _dados_post(
        self,
        *,
        matricula,
        nome='Discente da Regra',
        deslocamento_horas=0,
    ):
        inicio = self.inicio + timedelta(hours=deslocamento_horas)
        fim = inicio + timedelta(hours=1)

        return {
            'nome_discente': nome,
            'matricula_discente': matricula,
            'titulo_tcc': f'TCC da matrícula {matricula}',
            'resumo_tcc': 'Resumo válido para testar a regra da matrícula.',
            'semestre_letivo': '2026.2',
            'espaco': self.espaco.id,
            'opcao_data_inicio': inicio.strftime('%Y-%m-%dT%H:%M'),
            'opcao_data_fim': fim.strftime('%Y-%m-%dT%H:%M'),
            'coorientador': '',
            'avaliador_interno': self.avaliador.id,
            'segundo_avaliador_interno': '',
            'presidente': '',
            'nome_avaliador_externo': '',
            'titulacao_avaliador_externo': '',
            'instituicao_avaliador_externo': '',
            'arquivo_tcc': arquivo_pdf_teste(),
        }

    def _criar_fluxo(
        self,
        *,
        matricula,
        status_solicitacao,
        status_banca=None,
        nota=None,
        orientador=None,
    ):
        orientador = orientador or self.orientador
        discente = Discente.objects.create(
            nome='Discente da Regra',
            matricula=matricula,
        )
        projeto = ProjetoTCC.objects.create(
            titulo=f'Projeto anterior {matricula}',
            resumo='Resumo do projeto anterior.',
            semestre_letivo='2026.1',
            discente=discente,
            status=(
                'RECUSADA'
                if status_solicitacao == 'RECUSADA'
                else 'APROVADO'
                if status_solicitacao == 'APROVADA'
                else 'EM_ANÁLISE'
            ),
        )

        inicio_anterior = self.inicio - timedelta(days=10)
        fim_anterior = inicio_anterior + timedelta(hours=1)

        if status_banca in {'AGENDADA', 'AGUARDANDO_NOTA'}:
            inicio_anterior = self.inicio + timedelta(days=1)
            fim_anterior = inicio_anterior + timedelta(hours=1)

        solicitacao = SolicitacaoAgendamento.objects.create(
            usuario_solicitante=orientador,
            projeto_tcc=projeto,
            espaco=self.espaco,
            opcao_data_inicio=inicio_anterior,
            opcao_data_fim=fim_anterior,
            status=status_solicitacao,
        )
        ComposicaoBanca.objects.create(
            solicitacao=solicitacao,
            projeto_tcc=projeto,
            orientador=orientador,
            avaliador_interno=self.avaliador,
        )

        if status_banca:
            BancaTCC.objects.create(
                solicitacao=solicitacao,
                projeto_tcc=projeto,
                espaco=self.espaco,
                data_horario_inicio=inicio_anterior,
                data_horario_fim=fim_anterior,
                status=status_banca,
                nota=nota,
            )

        return solicitacao

    def _enviar(self, docente, **dados):
        self.client.force_login(docente.usuario)
        return self.client.post(
            reverse('solicitar_banca'),
            self._dados_post(**dados),
        )

    def test_docente_pode_enviar_varias_solicitacoes_para_discentes_diferentes(
        self,
    ):
        primeira = self._enviar(
            self.orientador,
            matricula='20260001001',
            deslocamento_horas=0,
        )
        segunda = self._enviar(
            self.orientador,
            matricula='20260001002',
            nome='Outro Discente',
            deslocamento_horas=2,
        )

        self.assertRedirects(primeira, reverse('dashboard'))
        self.assertRedirects(segunda, reverse('dashboard'))
        self.assertEqual(SolicitacaoAgendamento.objects.count(), 2)

    def test_solicitacao_em_analise_bloqueia_qualquer_outro_docente(self):
        self._criar_fluxo(
            matricula='20260001003',
            status_solicitacao='EM_ANÁLISE',
        )

        resposta = self._enviar(
            self.outro_orientador,
            matricula='20260001003',
            deslocamento_horas=2,
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(
            resposta,
            'já possui uma solicitação de TCC em análise',
        )
        self.assertEqual(SolicitacaoAgendamento.objects.count(), 1)

    def test_solicitacao_aprovada_sem_banca_continua_bloqueando(self):
        self._criar_fluxo(
            matricula='20260001004',
            status_solicitacao='APROVADA',
        )

        resposta = self._enviar(
            self.orientador,
            matricula='20260001004',
        )

        self.assertContains(
            resposta,
            'solicitação de TCC aprovada e ainda não finalizada',
        )
        self.assertEqual(SolicitacaoAgendamento.objects.count(), 1)

    def test_banca_agendada_ou_aguardando_nota_bloqueia_novo_tcc(self):
        for indice, status in enumerate(
            ['AGENDADA', 'AGUARDANDO_NOTA'],
            start=5,
        ):
            with self.subTest(status=status):
                matricula = f'202600010{indice:02d}'
                self._criar_fluxo(
                    matricula=matricula,
                    status_solicitacao='APROVADA',
                    status_banca=status,
                )

                resposta = self._enviar(
                    self.outro_orientador,
                    matricula=matricula,
                )

                self.assertContains(
                    resposta,
                    'banca agendada, em andamento ou aguardando nota',
                )

    def test_recusa_ou_expiracao_libera_nova_tentativa(self):
        for indice, status in enumerate(
            ['RECUSADA', 'EXPIRADA'],
            start=7,
        ):
            with self.subTest(status=status):
                matricula = f'202600010{indice:02d}'
                self._criar_fluxo(
                    matricula=matricula,
                    status_solicitacao=status,
                )

                resposta = self._enviar(
                    self.outro_orientador,
                    matricula=matricula,
                    deslocamento_horas=indice - 7,
                )

                self.assertRedirects(resposta, reverse('dashboard'))
                self.assertEqual(
                    SolicitacaoAgendamento.objects.filter(
                        projeto_tcc__discente__matricula=matricula,
                    ).count(),
                    2,
                )

    def test_finalizacao_com_reprovacao_libera_nova_tentativa(self):
        matricula = '20260001009'
        self._criar_fluxo(
            matricula=matricula,
            status_solicitacao='APROVADA',
            status_banca='FINALIZADA',
            nota=Decimal('7.99'),
        )

        resposta = self._enviar(
            self.outro_orientador,
            matricula=matricula,
        )

        self.assertRedirects(resposta, reverse('dashboard'))
        self.assertEqual(
            SolicitacaoAgendamento.objects.filter(
                projeto_tcc__discente__matricula=matricula,
            ).count(),
            2,
        )

    def test_finalizacao_com_aprovacao_bloqueia_definitivamente(self):
        matricula = '20260001010'
        self._criar_fluxo(
            matricula=matricula,
            status_solicitacao='APROVADA',
            status_banca='FINALIZADA',
            nota=Decimal('8.00'),
        )

        resposta = self._enviar(
            self.outro_orientador,
            matricula=matricula,
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(
            resposta,
            'TCC finalizado com aprovação',
        )
        self.assertEqual(SolicitacaoAgendamento.objects.count(), 1)

    def test_revalidacao_transacional_exibe_erro_sem_gravar(self):
        self.client.force_login(self.orientador.usuario)

        with patch(
            'bancasapp.views.criar_solicitacao_banca_segura',
            side_effect=SolicitacaoBancaInvalida(
                'A matrícula ficou indisponível durante o envio.'
            ),
        ):
            resposta = self.client.post(
                reverse('solicitar_banca'),
                self._dados_post(matricula='20260001011'),
            )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(
            resposta,
            'A matrícula ficou indisponível durante o envio.',
        )
        self.assertEqual(SolicitacaoAgendamento.objects.count(), 0)
        self.assertEqual(ProjetoTCC.objects.count(), 0)

    def test_auditoria_identifica_fluxos_simultaneos_apos_aprovacao(self):
        matricula = '20260001012'
        self._criar_fluxo(
            matricula=matricula,
            status_solicitacao='APROVADA',
            status_banca='FINALIZADA',
            nota=Decimal('9.00'),
        )
        discente = Discente.objects.get(matricula=matricula)

        for indice in range(2):
            projeto = ProjetoTCC.objects.create(
                titulo=f'Fluxo indevido {indice}',
                resumo='Fluxo criado para a auditoria.',
                semestre_letivo='2026.2',
                discente=discente,
                status='EM_ANÁLISE',
            )
            solicitacao = SolicitacaoAgendamento.objects.create(
                usuario_solicitante=self.orientador,
                projeto_tcc=projeto,
                espaco=self.espaco,
                opcao_data_inicio=(
                    self.inicio + timedelta(hours=indice)
                ),
                opcao_data_fim=(
                    self.inicio + timedelta(hours=indice + 1)
                ),
                status='EM_ANÁLISE',
            )
            ComposicaoBanca.objects.create(
                solicitacao=solicitacao,
                projeto_tcc=projeto,
                orientador=self.orientador,
                avaliador_interno=self.avaliador,
            )

        saida = StringIO()
        call_command(
            'auditar_integridade_sgtcc',
            stdout=saida,
        )
        texto = saida.getvalue()

        self.assertIn('MATRICULA_COM_FLUXOS_SIMULTANEOS', texto)
        self.assertIn('MATRICULA_APROVADA_COM_FLUXO_ATIVO', texto)
        self.assertIn(str(discente.id), texto)
