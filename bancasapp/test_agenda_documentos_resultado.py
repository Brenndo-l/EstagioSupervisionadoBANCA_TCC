from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from docx import Document

from .documentos_banca import gerar_docx_ata, montar_dados_ata
from .forms import DisponibilidadeEspacoForm, RegistroNotaBancaForm
from .forms import SolicitacaoBancaForm
from .models import (
    BancaTCC,
    ComposicaoBanca,
    ConfiguracaoAgendamento,
    Discente,
    DisponibilidadeEspaco,
    EspacoFisico,
    ProjetoTCC,
    SolicitacaoAgendamento,
    pUsuario,
)
from .services import (
    SolicitacaoBancaInvalida,
    criar_solicitacao_banca_segura,
    montar_agenda_disponibilidades,
    montar_opcoes_agendamento,
)


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

    def formulario_pronto_para_envio(self):
        segundo = pUsuario.objects.create(
            usuario=User.objects.create_user(
                username='segundo.para.envio@ufac.br',
                email='segundo.para.envio@ufac.br',
                password='Senha123!',
            ),
            perfil='DOCENTE',
        )
        inicio = self.inicio
        fim = inicio + timedelta(hours=1)
        formulario = SolicitacaoBancaForm(
            data={
                'nome_discente': 'Discente reserva tardia',
                'matricula_discente': '20269990001',
                'titulo_tcc': 'Teste de concorrência da agenda',
                'resumo_tcc': 'Teste de validação tardia do horário.',
                'semestre_letivo': '2026.2',
                'espaco': self.espaco.pk,
                'opcao_data_inicio': inicio.strftime('%Y-%m-%dT%H:%M'),
                'opcao_data_fim': fim.strftime('%Y-%m-%dT%H:%M'),
                'avaliador_interno': self.avaliador.pk,
                'segundo_avaliador_interno': segundo.pk,
            },
            files={'arquivo_tcc': SimpleUploadedFile(
                'tcc.pdf', b'%PDF-1.4\nconteudo de teste',
                content_type='application/pdf',
            )},
            orientador=self.docente,
        )
        self.assertTrue(formulario.is_valid(), formulario.errors)
        return formulario, segundo

    def test_reserva_da_sala_apos_validacao_impede_gravacao(self):
        formulario, _ = self.formulario_pronto_para_envio()
        self.criar_solicitacao(
            self.inicio, self.inicio + timedelta(hours=1), 'APROVADA'
        )
        with self.assertRaises(SolicitacaoBancaInvalida) as erro:
            criar_solicitacao_banca_segura(
                form=formulario, orientador=self.docente
            )
        self.assertEqual(erro.exception.campo, 'espaco')
        self.assertEqual(SolicitacaoAgendamento.objects.count(), 1)

    def test_mudanca_da_duracao_apos_validacao_impede_gravacao(self):
        formulario, _ = self.formulario_pronto_para_envio()
        configuracao = ConfiguracaoAgendamento.carregar()
        configuracao.duracao_banca_minutos = 90
        configuracao.save()
        with self.assertRaises(SolicitacaoBancaInvalida) as erro:
            criar_solicitacao_banca_segura(
                form=formulario, orientador=self.docente
            )
        self.assertEqual(erro.exception.campo, 'opcao_data_inicio')
        self.assertFalse(SolicitacaoAgendamento.objects.exists())

    def test_docente_em_outra_sala_apos_validacao_impede_gravacao(self):
        formulario, _ = self.formulario_pronto_para_envio()
        outra_sala = EspacoFisico.objects.create(nome='Sala simultânea')
        existente = self.criar_solicitacao(
            self.inicio, self.inicio + timedelta(hours=1), 'APROVADA'
        )
        existente.espaco = outra_sala
        existente.save(update_fields=['espaco'])
        outro_orientador = pUsuario.objects.create(
            usuario=User.objects.create_user(
                username='orientador.outra@ufac.br',
                email='orientador.outra@ufac.br',
                password='Senha123!',
            ),
            perfil='DOCENTE',
        )
        ComposicaoBanca.objects.create(
            solicitacao=existente,
            projeto_tcc=existente.projeto_tcc,
            orientador=outro_orientador,
            avaliador_interno=self.avaliador,
        )
        with self.assertRaises(SolicitacaoBancaInvalida) as erro:
            criar_solicitacao_banca_segura(
                form=formulario, orientador=self.docente
            )
        self.assertIsNone(erro.exception.campo)
        self.assertEqual(SolicitacaoAgendamento.objects.count(), 1)

    def test_grade_de_uma_hora_nao_oferece_opcoes_sobrepostas(self):
        configuracao = ConfiguracaoAgendamento.carregar()
        configuracao.duracao_banca_minutos = 60
        configuracao.save()
        self.disponibilidade.data_hora_inicio = self.inicio.replace(
            hour=6, minute=30
        )
        self.disponibilidade.data_hora_fim = self.inicio.replace(
            hour=10, minute=30
        )
        self.disponibilidade.save()
        horarios = montar_opcoes_agendamento(
            [self.disponibilidade],
            agora=self.disponibilidade.data_hora_inicio - timedelta(hours=1),
        )['espacos'][str(self.espaco.pk)]['datas'][self.inicio.date().isoformat()]
        self.assertEqual(
            [(h['inicio'], h['fim']) for h in horarios],
            [('06:30', '07:30'), ('07:30', '08:30'),
             ('08:30', '09:30'), ('09:30', '10:30')],
        )

        # Uma reserva fora da grade antiga não cria horários deslocados.
        self.criar_solicitacao(
            self.inicio.replace(hour=7),
            self.inicio.replace(hour=8),
            'EM_ANÁLISE',
        )
        horarios = montar_opcoes_agendamento(
            [self.disponibilidade],
            agora=self.disponibilidade.data_hora_inicio - timedelta(hours=1),
        )['espacos'][str(self.espaco.pk)]['datas'][self.inicio.date().isoformat()]
        self.assertEqual(
            [h['inicio'] for h in horarios],
            ['08:30', '09:30'],
        )

    def test_grade_exibe_reservas_sem_permitir_selecao(self):
        agora = self.inicio - timedelta(hours=1)
        pendente = self.criar_solicitacao(
            self.inicio, self.inicio + timedelta(hours=1), 'EM_ANÁLISE'
        )
        self.criar_solicitacao(
            self.inicio + timedelta(hours=1),
            self.inicio + timedelta(hours=2),
            'APROVADA',
        )
        dados = montar_opcoes_agendamento(
            [self.disponibilidade], agora=agora
        )['espacos'][str(self.espaco.pk)]
        dia = self.inicio.date().isoformat()
        self.assertEqual(
            [(item['inicio'], item['situacao']) for item in dados['grade'][dia]],
            [('08:00', 'em_analise'), ('09:00', 'agendado'),
             ('10:00', 'disponivel'), ('11:00', 'disponivel')],
        )
        self.assertEqual(
            [item['inicio'] for item in dados['datas'][dia]],
            ['10:00', '11:00'],
        )

        pendente.status = 'RECUSADA'
        pendente.save(update_fields=['status'])
        dados = montar_opcoes_agendamento(
            [self.disponibilidade], agora=agora
        )['espacos'][str(self.espaco.pk)]
        self.assertEqual(dados['grade'][dia][0]['situacao'], 'disponivel')

    def test_dia_totalmente_reservado_permanece_visivel_na_grade(self):
        self.criar_solicitacao(self.inicio, self.fim, 'APROVADA')
        dados = montar_opcoes_agendamento(
            [self.disponibilidade], agora=self.inicio - timedelta(hours=1)
        )['espacos'][str(self.espaco.pk)]
        dia = self.inicio.date().isoformat()
        self.assertEqual(dados['datas'], {})
        self.assertEqual(len(dados['grade'][dia]), 4)
        self.assertTrue(all(
            item['situacao'] == 'agendado' for item in dados['grade'][dia]
        ))

    def test_tela_docente_publica_reserva_e_navegacao_com_icones(self):
        self.criar_solicitacao(
            self.inicio, self.inicio + timedelta(hours=1), 'EM_ANÁLISE'
        )
        self.client.force_login(self.docente.usuario)
        resposta = self.client.get(reverse('solicitar_banca'))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, '"situacao": "em_analise"')
        self.assertContains(resposta, '"situacao": "disponivel"')
        self.assertContains(resposta, 'data-calendar-next')
        self.assertContains(resposta, '<svg aria-hidden="true"')
        self.assertContains(resposta, 'Em análise')

    def test_disponibilidade_sobreposta_mesma_sala_e_rejeitada(self):
        inicio = self.inicio + timedelta(hours=1)
        fim = self.fim + timedelta(hours=1)
        dados = {
            'espaco': self.espaco.pk,
            'data_hora_inicio_0': inicio.strftime('%Y-%m-%d'),
            'data_hora_inicio_1': inicio.strftime('%H:%M'),
            'data_hora_fim_0': fim.strftime('%Y-%m-%d'),
            'data_hora_fim_1': fim.strftime('%H:%M'),
            'observacao': '',
        }
        form = DisponibilidadeEspacoForm(data=dados)
        self.assertFalse(form.is_valid())
        self.assertIn('coincide', str(form.errors))

        self.client.force_login(self.usuario_coordenacao)
        resposta = self.client.post(
            reverse('gerenciar_espacos'),
            {'tipo_formulario': 'disponibilidade', **{
                f'disponibilidade-{chave}': valor
                for chave, valor in dados.items()
            }},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(DisponibilidadeEspaco.objects.count(), 1)

    def test_auditoria_detecta_periodos_legados_sobrepostos(self):
        # O auditor é apenas leitura; não desativa registros em produção.
        duplicada = DisponibilidadeEspaco.objects.create(
            espaco=self.espaco,
            data_hora_inicio=self.inicio + timedelta(minutes=30),
            data_hora_fim=self.fim,
            ativo=True,
        )
        saida = StringIO()
        call_command('auditar_integridade_sgtcc', stdout=saida)
        self.assertIn('DISPONIBILIDADES_SOBREPOSTAS', saida.getvalue())
        self.assertIn(f'IDs: {duplicada.pk}', saida.getvalue())

        opcoes = montar_opcoes_agendamento(
            [duplicada, self.disponibilidade],
            agora=self.inicio - timedelta(hours=1),
        )['espacos'][str(self.espaco.pk)]['datas'][self.inicio.date().isoformat()]
        self.assertEqual([item['inicio'] for item in opcoes],
                         ['08:00', '09:00', '10:00', '11:00'])

    def test_mesma_grade_para_contas_docentes_diferentes(self):
        outro = User.objects.create_user(
            username='outro.agenda@ufac.br',
            email='outro.agenda@ufac.br',
            password='Senha123!',
        )
        pUsuario.objects.create(usuario=outro, perfil='DOCENTE')
        self.client.force_login(self.docente.usuario)
        primeira = self.client.get(reverse('solicitar_banca'))
        self.client.force_login(outro)
        segunda = self.client.get(reverse('solicitar_banca'))
        self.assertEqual(
            primeira.context['opcoes_agendamento']['espacos'],
            segunda.context['opcoes_agendamento']['espacos'],
        )
        self.assertContains(segunda, 'data-appointment-picker')

    def test_agenda_informativa_e_painel_mostram_janela_compacta(self):
        self.client.force_login(self.docente.usuario)
        painel = self.client.get(reverse('dashboard'))
        agenda = self.client.get(reverse('agenda_disponivel'))
        self.assertEqual(painel.status_code, 200)
        self.assertEqual(agenda.status_code, 200)
        self.assertContains(painel, self.espaco.nome)
        self.assertContains(agenda, self.espaco.nome)
        self.assertContains(agenda, '08:00–12:00')
        self.assertContains(painel, '08:00–12:00')
        self.assertNotContains(agenda, '08:00–09:00')
        self.assertNotContains(agenda, 'data-agenda-slot')

    def test_reserva_divide_apenas_janelas_livres_na_consulta(self):
        self.criar_solicitacao(
            self.inicio + timedelta(hours=1),
            self.inicio + timedelta(hours=2),
            'EM_ANÁLISE',
        )
        self.client.force_login(self.docente.usuario)
        resposta = self.client.get(reverse('agenda_disponivel'))
        self.assertContains(resposta, '08:00–09:00')
        self.assertContains(resposta, '10:00–12:00')
        self.assertNotContains(resposta, '10:00–11:00')

    def test_espaco_ocupado_nao_aparece_na_agenda(self):
        self.criar_solicitacao(self.inicio, self.fim, 'APROVADA')
        self.client.force_login(self.docente.usuario)
        painel = self.client.get(reverse('dashboard'))
        agenda = self.client.get(reverse('agenda_disponivel'))
        self.assertEqual(painel.context['total_salas'], 0)
        self.assertNotContains(agenda, self.espaco.nome)

    def test_termino_2359_e_valido_no_widget(self):
        hora = self.inicio.replace(hour=23, minute=59)
        formulario = DisponibilidadeEspacoForm(data={
            'espaco': self.espaco.pk,
            'data_hora_inicio_0': hora.strftime('%Y-%m-%d'),
            'data_hora_inicio_1': '12:30',
            'data_hora_fim_0': hora.strftime('%Y-%m-%d'),
            'data_hora_fim_1': '23:59',
        })
        # O período 12:30–23:59 começa após a janela 08:00–12:00.
        self.assertTrue(formulario.is_valid(), formulario.errors)
        self.assertIn('23:59', str(formulario['data_hora_fim']))
        self.assertIn('step="60"', str(formulario['data_hora_fim']))

    def test_datas_limitam_ano_no_formulario_e_rejeitam_ano_extenso(self):
        formulario = DisponibilidadeEspacoForm(data={
            'espaco': self.espaco.pk,
            'data_hora_inicio_0': '222222-02-22',
            'data_hora_inicio_1': '08:00',
            'data_hora_fim_0': '222222-02-22',
            'data_hora_fim_1': '09:00',
        })
        self.assertIn('max="9999-12-31"', str(formulario['data_hora_inicio']))
        self.assertIn('max="9999-12-31"', str(formulario['data_hora_fim']))
        self.assertFalse(formulario.is_valid())
        self.assertIn('data_hora_inicio', formulario.errors)

    def test_matricula_e_semestre_rejeitam_digitos_nao_ascii(self):
        formulario, _ = self.formulario_pronto_para_envio()
        self.assertIn('data-digits-only', str(formulario['matricula_discente']))
        self.assertIn('data-semester-format', str(formulario['semestre_letivo']))

        for campo, valor in (
            ('matricula_discente', '٢٠٢٦٩٩٩٠٠٠١'),
            ('semestre_letivo', '٢٠٢٦.٢'),
        ):
            with self.subTest(campo=campo):
                dados = dict(formulario.data)
                dados[campo] = valor
                invalido = SolicitacaoBancaForm(
                    data=dados,
                    files=formulario.files,
                    orientador=self.docente,
                )
                self.assertFalse(invalido.is_valid())
                self.assertIn(campo, invalido.errors)

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

    def test_agenda_preserva_limites_exatos_ao_dividir_periodo(self):

        inicio_disponivel = self.inicio.replace(
            hour=6,
            minute=30,
        )
        fim_disponivel = self.inicio.replace(
            hour=18,
            minute=30,
        )
        self.disponibilidade.data_hora_inicio = inicio_disponivel
        self.disponibilidade.data_hora_fim = fim_disponivel
        self.disponibilidade.save(
            update_fields=[
                'data_hora_inicio',
                'data_hora_fim',
            ]
        )

        self.criar_solicitacao(
            self.inicio.replace(hour=7),
            self.inicio.replace(hour=8),
            'EM_ANÁLISE',
        )

        agenda = montar_agenda_disponibilidades(
            [self.disponibilidade],
            agora=inicio_disponivel - timedelta(hours=1),
        )

        livres = agenda[0].intervalos_livres

        self.assertEqual(
            (livres[0]['inicio'], livres[0]['fim']),
            (
                inicio_disponivel,
                self.inicio.replace(hour=7),
            ),
        )
        self.assertEqual(
            (livres[1]['inicio'], livres[1]['fim']),
            (
                self.inicio.replace(hour=8),
                fim_disponivel,
            ),
        )

    def test_nova_banca_pode_comecar_quando_anterior_termina(self):

        self.criar_solicitacao(
            self.inicio.replace(hour=10),
            self.inicio.replace(hour=11),
            'APROVADA',
        )

        opcoes = montar_opcoes_agendamento(
            [self.disponibilidade],
            agora=self.inicio - timedelta(hours=1),
        )

        horarios = opcoes['espacos'][str(self.espaco.id)]['datas'][
            self.inicio.date().isoformat()
        ]

        self.assertIn(
            '11:00',
            [horario['inicio'] for horario in horarios],
        )

    def test_duracao_definida_pela_coordenacao_gera_termino(self):

        configuracao = ConfiguracaoAgendamento.carregar()
        configuracao.duracao_banca_minutos = 90
        configuracao.save()

        opcoes = montar_opcoes_agendamento(
            [self.disponibilidade],
            agora=self.inicio - timedelta(hours=1),
        )

        primeira = opcoes['espacos'][str(self.espaco.id)]['datas'][
            self.inicio.date().isoformat()
        ][0]

        self.assertEqual(primeira['inicio'], '08:00')
        self.assertEqual(primeira['fim'], '09:30')

    def test_coordenacao_pode_alterar_duracao_das_bancas(self):

        self.client.force_login(self.usuario_coordenacao)

        response = self.client.post(
            reverse('gerenciar_espacos'),
            {
                'tipo_formulario': 'configuracao',
                'configuracao-duracao_banca_minutos': '45',
            },
        )

        self.assertRedirects(response, reverse('gerenciar_espacos'))
        self.assertEqual(
            ConfiguracaoAgendamento.carregar().duracao_banca_minutos,
            45,
        )

    def test_disponibilidade_deve_comecar_e_terminar_no_mesmo_dia(self):

        inicio = self.inicio
        fim = inicio + timedelta(days=1, hours=1)

        formulario = DisponibilidadeEspacoForm(
            data={
                'espaco': self.espaco.pk,
                'data_hora_inicio_0': inicio.strftime('%Y-%m-%d'),
                'data_hora_inicio_1': inicio.strftime('%H:%M'),
                'data_hora_fim_0': fim.strftime('%Y-%m-%d'),
                'data_hora_fim_1': fim.strftime('%H:%M'),
                'observacao': '',
            }
        )

        self.assertFalse(formulario.is_valid())
        self.assertIn(
            'mesma data',
            formulario.errors['data_hora_fim'][0],
        )

    def test_tela_exibe_seletor_sem_agenda_duplicada(self):

        self.preparar_reservas()

        self.client.force_login(
            self.docente.usuario
        )

        response = self.client.get(
            reverse('solicitar_banca')
        )

        self.assertContains(
            response,
            'Escolha um horário disponível'
        )

        self.assertContains(
            response,
            'Selecione o dia da banca'
        )

        self.assertContains(
            response,
            'Selecione o horário inicial'
        )

        self.assertContains(
            response,
            'data-appointment-picker'
        )

        self.assertContains(
            response,
            'solicitacao-agendamento-dados'
        )

        self.assertNotContains(
            response,
            'data-agenda-slot'
        )


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

        self.client.force_login(
            self.usuario_coordenacao
        )

        response = self.client.get(
            reverse('documentos')
        )

        self.assertContains(
            response,
            'Docente solicitante'
        )

        self.assertContains(
            response,
            'Helena Orientadora'
        )

        self.assertContains(
            response,
            reverse(
                'detalhar_solicitacao',
                args=[self.solicitacao.id],
            ),
        )

        self.assertContains(
            response,
            'DETALHES'
        )

    def test_docente_tambem_acessa_detalhes_pela_area_documentos(self):

        self.client.force_login(
            self.docente.usuario
        )

        response = self.client.get(
            reverse(
                'detalhar_solicitacao',
                args=[self.solicitacao.id],
            )
        )

        self.assertEqual(
            response.status_code,
            200
        )


class ResultadoNotaTests(BaseAgendaResultadoTests):

    def test_nota_abaixo_de_oito_resulta_em_reprovacao(self):

        banca = BancaTCC(
            nota=Decimal('7.99')
        )

        self.assertEqual(
            banca.resultado_final,
            'REPROVAÇÃO',
        )

    def test_nota_oito_resulta_em_aprovacao(self):

        banca = BancaTCC(
            nota=Decimal('8.00')
        )

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

        documento = Document(
            gerar_docx_ata(dados)
        )

        texto = '\n'.join(
            paragrafo.text
            for paragrafo in documento.paragraphs
        )

        self.assertIn(
            'deliberou pela REPROVAÇÃO',
            texto
        )
