from io import BytesIO, StringIO
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import (
    RequestFactory,
    SimpleTestCase,
    TestCase,
    override_settings,
)
from django.urls import reverse
from django.utils import timezone

from .forms import ModeloDocumentoForm
from .models import (
    BancaTCC,
    ComposicaoBanca,
    Discente,
    DisponibilidadeEspaco,
    EspacoFisico,
    ModeloDocumento,
    ProjetoTCC,
    SolicitacaoAgendamento,
    pUsuario,
)
from .views import erro_403, erro_500


def arquivo_docx_minimo():

    memoria = BytesIO()

    with ZipFile(
        memoria,
        mode='w',
        compression=ZIP_DEFLATED
    ) as pacote:
        pacote.writestr(
            '[Content_Types].xml',
            '<Types />'
        )
        pacote.writestr(
            'word/document.xml',
            '<w:document />'
        )

    return memoria.getvalue()


class ValidacaoModeloDocumentoTests(SimpleTestCase):

    def formulario(self, arquivo):

        return ModeloDocumentoForm(
            data={
                'nome': 'Modelo para teste',
                'tipo': 'ATA_DEFESA',
            },
            files={
                'arquivo': arquivo,
            }
        )

    def test_pdf_renomeado_e_rejeitado(self):

        form = self.formulario(
            SimpleUploadedFile(
                'modelo.pdf',
                b'conteudo que nao e pdf',
                content_type='application/pdf'
            )
        )

        self.assertFalse(form.is_valid())
        self.assertIn(
            'não parece ser um PDF válido',
            str(form.errors['arquivo'])
        )

    def test_docx_renomeado_e_rejeitado(self):

        form = self.formulario(
            SimpleUploadedFile(
                'modelo.docx',
                b'arquivo que nao e um pacote docx',
                content_type=(
                    'application/vnd.openxmlformats-officedocument.'
                    'wordprocessingml.document'
                )
            )
        )

        self.assertFalse(form.is_valid())
        self.assertIn(
            'não corresponde ao formato DOCX',
            str(form.errors['arquivo'])
        )

    def test_docx_com_estrutura_minima_e_aceito(self):

        form = self.formulario(
            SimpleUploadedFile(
                'modelo.docx',
                arquivo_docx_minimo(),
                content_type=(
                    'application/vnd.openxmlformats-officedocument.'
                    'wordprocessingml.document'
                )
            )
        )

        self.assertTrue(
            form.is_valid(),
            form.errors
        )

    def test_modelo_maior_que_dez_mb_e_rejeitado(self):

        form = self.formulario(
            SimpleUploadedFile(
                'modelo.pdf',
                b'%PDF-' + b'0' * (10 * 1024 * 1024),
                content_type='application/pdf'
            )
        )

        self.assertFalse(form.is_valid())
        self.assertIn(
            'não pode ultrapassar 10 MB',
            str(form.errors['arquivo'])
        )


class PaginasErroTests(SimpleTestCase):

    @override_settings(DEBUG=False)
    def test_rota_inexistente_usa_pagina_404(self):

        response = self.client.get(
            '/endereco-que-nao-existe-no-sgtcc/'
        )

        self.assertEqual(
            response.status_code,
            404
        )

        self.assertTemplateUsed(
            response,
            'erro_sistema.html'
        )

        self.assertContains(
            response,
            'Página não encontrada',
            status_code=404
        )

    def test_pagina_403_nao_expoe_detalhes_internos(self):

        request = RequestFactory().get(
            '/restrito/'
        )

        request.user = User()

        response = erro_403(
            request
        )

        self.assertEqual(
            response.status_code,
            403
        )

        self.assertIn(
            'Acesso não autorizado'.encode('utf-8'),
            response.content
        )

    def test_pagina_500_nao_expoe_excecao(self):

        request = RequestFactory().get(
            '/falha/'
        )

        request.user = User()

        response = erro_500(
            request
        )

        self.assertEqual(
            response.status_code,
            500
        )

        self.assertIn(
            b'falha inesperada',
            response.content
        )

        self.assertNotIn(
            b'Traceback',
            response.content
        )


class LimpezaDemonstracaoTests(TestCase):

    def setUp(self):

        self.pasta_temporaria = TemporaryDirectory()

        self.configuracao_media = override_settings(
            MEDIA_ROOT=self.pasta_temporaria.name
        )

        self.configuracao_media.enable()

        usuario = User.objects.create_user(
            username='demo@ufac.br',
            email='demo@ufac.br',
            password='Senha123!'
        )

        self.perfil = pUsuario.objects.create(
            usuario=usuario,
            perfil='DOCENTE'
        )

        self.espaco = EspacoFisico.objects.create(
            nome='Sala de demonstração'
        )

        inicio = timezone.now() + timedelta(
            days=10
        )

        fim = inicio + timedelta(
            hours=2
        )

        self.disponibilidade = (
            DisponibilidadeEspaco.objects.create(
                espaco=self.espaco,
                data_hora_inicio=(
                    inicio - timedelta(hours=1)
                ),
                data_hora_fim=(
                    fim + timedelta(hours=1)
                ),
                criada_por=usuario
            )
        )

        discente = Discente.objects.create(
            nome='Discente de demonstração',
            matricula='20260000001'
        )

        projeto = ProjetoTCC.objects.create(
            titulo='TCC de demonstração',
            resumo='Resumo do TCC utilizado na demonstração.',
            semestre_letivo='2026.2',
            discente=discente
        )

        self.solicitacao = (
            SolicitacaoAgendamento.objects.create(
                usuario_solicitante=self.perfil,
                projeto_tcc=projeto,
                espaco=self.espaco,
                opcao_data_inicio=inicio,
                opcao_data_fim=fim,
                arquivo_tcc=SimpleUploadedFile(
                    'tcc_demo.pdf',
                    b'%PDF-1.4\nArquivo de demonstracao.',
                    content_type='application/pdf'
                )
            )
        )

        ComposicaoBanca.objects.create(
            solicitacao=self.solicitacao,
            projeto_tcc=projeto,
            orientador=self.perfil,
            avaliador_interno=self.perfil
        )

        self.modelo = ModeloDocumento.objects.create(
            nome='Modelo preservado',
            tipo='ATA_DEFESA',
            arquivo=SimpleUploadedFile(
                'modelo.pdf',
                b'%PDF-1.4\nModelo de demonstracao.',
                content_type='application/pdf'
            ),
            enviado_por=usuario
        )

        self.arquivo_tcc = Path(
            self.solicitacao.arquivo_tcc.path
        )

        self.arquivo_modelo = Path(
            self.modelo.arquivo.path
        )

    def tearDown(self):

        self.configuracao_media.disable()
        self.pasta_temporaria.cleanup()

    def test_sem_confirmacao_exibe_previa_e_nao_remove(self):

        saida = StringIO()

        call_command(
            'limpar_dados_demonstracao',
            stdout=saida
        )

        self.assertIn(
            'Nenhum dado foi removido',
            saida.getvalue()
        )

        self.assertTrue(
            SolicitacaoAgendamento.objects.exists()
        )

        self.assertTrue(
            self.arquivo_tcc.exists()
        )

    def test_confirmacao_remove_operacao_e_preserva_configuracao(self):

        call_command(
            'limpar_dados_demonstracao',
            confirmar='LIMPAR-DEMONSTRACAO',
            stdout=StringIO()
        )

        self.assertFalse(
            SolicitacaoAgendamento.objects.exists()
        )

        self.assertFalse(
            ProjetoTCC.objects.exists()
        )

        self.assertFalse(
            Discente.objects.exists()
        )

        self.assertTrue(
            User.objects.filter(
                username='demo@ufac.br'
            ).exists()
        )

        self.assertTrue(
            EspacoFisico.objects.filter(
                pk=self.espaco.pk
            ).exists()
        )

        self.assertTrue(
            DisponibilidadeEspaco.objects.filter(
                pk=self.disponibilidade.pk
            ).exists()
        )

        self.assertTrue(
            ModeloDocumento.objects.filter(
                pk=self.modelo.pk
            ).exists()
        )

        self.assertFalse(
            self.arquivo_tcc.exists()
        )

        self.assertTrue(
            self.arquivo_modelo.exists()
        )

    def test_opcoes_removem_disponibilidades_e_modelos(self):

        call_command(
            'limpar_dados_demonstracao',
            confirmar='LIMPAR-DEMONSTRACAO',
            incluir_disponibilidades=True,
            incluir_modelos=True,
            stdout=StringIO()
        )

        self.assertFalse(
            DisponibilidadeEspaco.objects.exists()
        )

        self.assertFalse(
            ModeloDocumento.objects.exists()
        )

        self.assertFalse(
            self.arquivo_modelo.exists()
        )

        self.assertTrue(
            EspacoFisico.objects.filter(
                pk=self.espaco.pk
            ).exists()
        )

        self.assertTrue(
            User.objects.filter(
                username='demo@ufac.br'
            ).exists()
        )
