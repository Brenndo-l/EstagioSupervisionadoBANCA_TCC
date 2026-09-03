import hashlib
import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.utils import timezone


def calcular_sha256(caminho):

    resumo = hashlib.sha256()

    with caminho.open('rb') as arquivo:

        for bloco in iter(
            lambda: arquivo.read(1024 * 1024),
            b''
        ):
            resumo.update(bloco)

    return resumo.hexdigest()


class Command(BaseCommand):
    help = (
        'Cria um backup consistente do SQLite e dos arquivos de mídia '
        'sem alterar os dados do sistema.'
    )

    def add_arguments(self, parser):

        parser.add_argument(
            '--saida',
            help=(
                'Caminho do ZIP de destino. Quando omitido, o arquivo '
                'é criado na pasta backups do projeto.'
            ),
        )

        parser.add_argument(
            '--banco',
            default='default',
            help='Alias do banco configurado no Django. Padrão: default.',
        )

    def handle(self, *args, **options):

        alias = options['banco']

        if alias not in connections:
            raise CommandError(
                f'O banco "{alias}" não está configurado.'
            )

        conexao_django = connections[alias]

        if conexao_django.vendor != 'sqlite':
            raise CommandError(
                'Este comando é exclusivo para o SQLite usado no '
                'desenvolvimento e na demonstração. Em produção, utilize '
                'a ferramenta de backup do PostgreSQL ou da hospedagem.'
            )

        caminho_banco = Path(
            conexao_django.settings_dict['NAME']
        ).resolve()

        if not caminho_banco.is_file():
            raise CommandError(
                f'O arquivo do banco não foi encontrado: {caminho_banco}'
            )

        destino = self._obter_destino(
            options.get('saida')
        )

        if destino.exists():
            raise CommandError(
                f'O arquivo de destino já existe: {destino}'
            )

        destino.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with TemporaryDirectory(
            prefix='sgtcc_backup_',
            dir=destino.parent
        ) as diretorio_temporario:

            caminho_temporario = Path(
                diretorio_temporario
            )

            copia_banco = (
                caminho_temporario
                / 'db.sqlite3'
            )

            self._copiar_sqlite_consistente(
                conexao_django,
                copia_banco
            )

            zip_temporario = (
                caminho_temporario
                / 'backup.zip'
            )

            manifesto = self._criar_zip(
                copia_banco,
                Path(settings.MEDIA_ROOT),
                zip_temporario,
                alias
            )

            zip_temporario.replace(destino)

        self.stdout.write(
            self.style.SUCCESS(
                'Backup criado com sucesso.'
            )
        )
        self.stdout.write(
            f'Arquivo: {destino}'
        )
        self.stdout.write(
            f'Banco: {manifesto["banco"]["sha256"]}'
        )
        self.stdout.write(
            (
                'Mídia: '
                f'{manifesto["midia"]["quantidade_arquivos"]} '
                'arquivo(s)'
            )
        )

    def _obter_destino(self, saida):

        if saida:
            destino = Path(saida).expanduser().resolve()
        else:
            instante = timezone.localtime().strftime(
                '%Y%m%d_%H%M%S'
            )
            destino = (
                Path(settings.BASE_DIR)
                / 'backups'
                / f'sgtcc_backup_{instante}.zip'
            ).resolve()

        if destino.suffix.casefold() != '.zip':
            raise CommandError(
                'O arquivo de saída precisa utilizar a extensão .zip.'
            )

        return destino

    def _copiar_sqlite_consistente(
        self,
        conexao_django,
        destino
    ):

        conexao_django.ensure_connection()

        origem = conexao_django.connection

        copia = sqlite3.connect(destino)

        try:
            origem.backup(copia)
        finally:
            copia.close()

    def _criar_zip(
        self,
        caminho_banco,
        diretorio_media,
        destino,
        alias
    ):

        criado_em = timezone.localtime().isoformat()
        arquivos_media = []
        tamanho_total_media = 0

        with ZipFile(
            destino,
            mode='w',
            compression=ZIP_DEFLATED,
        ) as pacote:

            pacote.write(
                caminho_banco,
                arcname='database/db.sqlite3'
            )

            if diretorio_media.is_dir():

                for arquivo in sorted(
                    diretorio_media.rglob('*')
                ):

                    if not arquivo.is_file() or arquivo.is_symlink():
                        continue

                    relativo = arquivo.relative_to(
                        diretorio_media
                    ).as_posix()

                    nome_zip = f'media/{relativo}'

                    pacote.write(
                        arquivo,
                        arcname=nome_zip
                    )

                    tamanho = arquivo.stat().st_size
                    tamanho_total_media += tamanho

                    arquivos_media.append(
                        {
                            'arquivo': nome_zip,
                            'tamanho_bytes': tamanho,
                            'sha256': calcular_sha256(arquivo),
                        }
                    )

            manifesto = {
                'formato': 'backup-sgtcc-v1',
                'criado_em': criado_em,
                'banco': {
                    'alias': alias,
                    'arquivo': 'database/db.sqlite3',
                    'tamanho_bytes': caminho_banco.stat().st_size,
                    'sha256': calcular_sha256(caminho_banco),
                },
                'midia': {
                    'quantidade_arquivos': len(arquivos_media),
                    'tamanho_total_bytes': tamanho_total_media,
                    'arquivos': arquivos_media,
                },
                'contagens': {
                    modelo._meta.label: modelo.objects.count()
                    for modelo in apps.get_models()
                },
            }

            pacote.writestr(
                'manifesto.json',
                json.dumps(
                    manifesto,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                ).encode('utf-8')
            )

        return manifesto
