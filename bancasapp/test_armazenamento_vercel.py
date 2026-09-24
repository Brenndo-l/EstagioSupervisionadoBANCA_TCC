from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.exceptions import ImproperlyConfigured
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from vercel.blob import BlobNotFoundError

from .storage_backends import VercelBlobStorage


class VercelBlobStorageTests(SimpleTestCase):

    def setUp(self):

        self.storage = VercelBlobStorage(
            token='token-de-teste',
        )
        self.cliente = MagicMock()
        self.contexto = MagicMock()
        self.contexto.__enter__.return_value = self.cliente

        self.patcher = patch.object(
            self.storage,
            '_cliente',
            return_value=self.contexto,
        )
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_salva_arquivo_privado_e_retorna_pathname(self):

        self.cliente.head.side_effect = BlobNotFoundError()
        self.cliente.put.return_value = SimpleNamespace(
            pathname='tcc/solicitacoes/2026/09/trabalho.pdf'
        )

        nome = self.storage.save(
            'tcc/solicitacoes/2026/09/trabalho.pdf',
            SimpleUploadedFile(
                'trabalho.pdf',
                b'%PDF-1.4 teste',
                content_type='application/pdf',
            ),
        )

        self.assertEqual(
            nome,
            'tcc/solicitacoes/2026/09/trabalho.pdf',
        )
        self.cliente.put.assert_called_once_with(
            'tcc/solicitacoes/2026/09/trabalho.pdf',
            b'%PDF-1.4 teste',
            access='private',
            content_type='application/pdf',
            add_random_suffix=False,
            overwrite=False,
        )

    def test_abre_arquivo_privado(self):

        self.cliente.get.return_value = SimpleNamespace(
            content=b'%PDF-1.4 conteudo',
        )

        with self.storage.open('tcc/trabalho.pdf', 'rb') as arquivo:
            conteudo = arquivo.read()

        self.assertEqual(
            conteudo,
            b'%PDF-1.4 conteudo',
        )
        self.cliente.get.assert_called_once_with(
            'tcc/trabalho.pdf',
            access='private',
            use_cache=False,
        )

    def test_informa_quando_arquivo_nao_existe(self):

        self.cliente.head.side_effect = BlobNotFoundError()

        self.assertFalse(
            self.storage.exists('tcc/inexistente.pdf')
        )

    def test_exclusao_de_arquivo_inexistente_e_idempotente(self):

        self.cliente.delete.side_effect = BlobNotFoundError()

        self.storage.delete('tcc/inexistente.pdf')

        self.cliente.delete.assert_called_once_with(
            'tcc/inexistente.pdf'
        )

    def test_rejeita_store_id_sem_token_de_leitura_e_escrita(self):

        with patch.dict(
            'os.environ',
            {
                'BLOB_STORE_ID': 'store_teste',
                'BLOB_READ_WRITE_TOKEN': '',
                'VERCEL_BLOB_READ_WRITE_TOKEN': '',
            },
            clear=False,
        ):
            with self.assertRaisesMessage(
                ImproperlyConfigured,
                'BLOB_READ_WRITE_TOKEN',
            ):
                VercelBlobStorage(token='')

    def test_aceita_nome_alternativo_do_token(self):

        with patch.dict(
            'os.environ',
            {
                'BLOB_READ_WRITE_TOKEN': '',
                'VERCEL_BLOB_READ_WRITE_TOKEN': 'token-alternativo',
            },
            clear=False,
        ):
            storage = VercelBlobStorage(token='')

        self.assertEqual(
            storage.token,
            'token-alternativo',
        )
