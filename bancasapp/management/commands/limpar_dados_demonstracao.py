from django.core.management.base import BaseCommand
from django.db import transaction

from bancasapp.models import (
    BancaTCC,
    ComposicaoBanca,
    Discente,
    DisponibilidadeEspaco,
    DocumentoEmitido,
    ModeloDocumento,
    ProjetoTCC,
    SolicitacaoAgendamento,
)


CONFIRMACAO_EXATA = 'LIMPAR-DEMONSTRACAO'


class Command(BaseCommand):
    help = (
        'Mostra ou remove dados operacionais de demonstração sem apagar '
        'usuários e espaços físicos.'
    )

    def add_arguments(self, parser):

        parser.add_argument(
            '--confirmar',
            default='',
            help=(
                'Para executar a exclusão, informe exatamente: '
                f'{CONFIRMACAO_EXATA}'
            ),
        )

        parser.add_argument(
            '--incluir-disponibilidades',
            action='store_true',
            help=(
                'Também remove os períodos disponibilizados. '
                'Os espaços físicos são preservados.'
            ),
        )

        parser.add_argument(
            '--incluir-modelos',
            action='store_true',
            help=(
                'Também remove os modelos enviados e seus arquivos físicos.'
            ),
        )

    def handle(self, *args, **options):

        incluir_disponibilidades = options[
            'incluir_disponibilidades'
        ]

        incluir_modelos = options[
            'incluir_modelos'
        ]

        contagens = {
            'bancas': BancaTCC.objects.count(),
            'composicoes': ComposicaoBanca.objects.count(),
            'solicitacoes': SolicitacaoAgendamento.objects.count(),
            'projetos': ProjetoTCC.objects.count(),
            'discentes': Discente.objects.count(),
            'documentos_emitidos': DocumentoEmitido.objects.count(),
            'disponibilidades': (
                DisponibilidadeEspaco.objects.count()
                if incluir_disponibilidades
                else 0
            ),
            'modelos': (
                ModeloDocumento.objects.count()
                if incluir_modelos
                else 0
            ),
        }

        self.stdout.write(
            self.style.WARNING(
                'Prévia da limpeza de dados de demonstração:'
            )
        )

        for nome, quantidade in contagens.items():
            self.stdout.write(
                f'  {nome}: {quantidade}'
            )

        self.stdout.write(
            '  preservados: usuários, perfis e espaços físicos'
        )

        if options['confirmar'] != CONFIRMACAO_EXATA:

            self.stdout.write('')
            self.stdout.write(
                self.style.WARNING(
                    'Nenhum dado foi removido. Para executar, use:'
                )
            )
            self.stdout.write(
                'python manage.py limpar_dados_demonstracao '
                f'--confirmar {CONFIRMACAO_EXATA}'
            )

            return

        campo_tcc = (
            SolicitacaoAgendamento
            ._meta
            .get_field('arquivo_tcc')
        )

        arquivos_tcc = list(
            SolicitacaoAgendamento.objects
            .exclude(arquivo_tcc='')
            .values_list(
                'arquivo_tcc',
                flat=True
            )
        )

        arquivos_modelos = []
        campo_modelo = None

        if incluir_modelos:

            campo_modelo = (
                ModeloDocumento
                ._meta
                .get_field('arquivo')
            )

            arquivos_modelos = list(
                ModeloDocumento.objects
                .exclude(arquivo='')
                .values_list(
                    'arquivo',
                    flat=True
                )
            )

        with transaction.atomic():

            DocumentoEmitido.objects.all().delete()
            BancaTCC.objects.all().delete()
            ComposicaoBanca.objects.all().delete()
            SolicitacaoAgendamento.objects.all().delete()
            ProjetoTCC.objects.all().delete()
            Discente.objects.all().delete()

            if incluir_disponibilidades:
                DisponibilidadeEspaco.objects.all().delete()

            if incluir_modelos:
                ModeloDocumento.objects.all().delete()

        falhas_arquivos = 0

        for nome_arquivo in arquivos_tcc:

            try:
                campo_tcc.storage.delete(
                    nome_arquivo
                )
            except OSError:
                falhas_arquivos += 1

        if campo_modelo:

            for nome_arquivo in arquivos_modelos:

                try:
                    campo_modelo.storage.delete(
                        nome_arquivo
                    )
                except OSError:
                    falhas_arquivos += 1

        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(
                'Dados de demonstração removidos com sucesso.'
            )
        )

        if falhas_arquivos:
            self.stdout.write(
                self.style.WARNING(
                    f'{falhas_arquivos} arquivo(s) físico(s) não puderam '
                    'ser removidos. Verifique o armazenamento.'
                )
            )
