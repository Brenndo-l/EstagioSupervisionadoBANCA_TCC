"""Armazenamentos de arquivos usados pelo SGTCC em produção."""

import mimetypes
import os
from io import BytesIO

from django.core.exceptions import ImproperlyConfigured
from django.core.files.base import File
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible


@deconstructible
class VercelBlobStorage(Storage):
    """Armazena arquivos privados no Vercel Blob.

    O banco guarda apenas o ``pathname`` retornado pelo Blob. As leituras
    continuam sendo feitas pelas views protegidas do SGTCC, portanto o
    navegador nunca precisa receber o token do armazenamento.
    """

    def __init__(self, token=None, access='private'):

        self.token = (
            token
            or os.environ.get(
                'BLOB_READ_WRITE_TOKEN',
                '',
            ).strip()
        )
        self.access = access

        if (
            not self.token
            and not os.environ.get(
                'BLOB_STORE_ID',
                '',
            ).strip()
        ):
            raise ImproperlyConfigured(
                'Conecte um Vercel Blob ao projeto ou defina '
                'BLOB_READ_WRITE_TOKEN.'
            )

        if self.access != 'private':
            raise ImproperlyConfigured(
                'Os documentos do SGTCC devem utilizar Blob privado.'
            )

    @staticmethod
    def _normalizar_nome(name):

        return str(name).replace('\\', '/').lstrip('/')

    def _cliente(self):

        # Importação tardia: o desenvolvimento local não depende do SDK
        # enquanto o armazenamento padrão for o sistema de arquivos.
        from vercel.blob import BlobClient

        return BlobClient(token=self._obter_token())

    def _obter_token(self):

        if self.token:
            return self.token

        # Em produção a Vercel fornece um token OIDC curto e rotativo. O SDK
        # consulta o contexto da requisição para não manter credencial fixa.
        from vercel.oidc import (
            VercelOidcTokenError,
            get_vercel_oidc_token,
        )

        try:
            return get_vercel_oidc_token()
        except VercelOidcTokenError as erro:
            raise OSError(
                'Não foi possível autenticar o Vercel Blob por OIDC.'
            ) from erro

    def _open(self, name, mode='rb'):

        if mode not in {'r', 'rb'}:
            raise ValueError(
                'O Vercel Blob permite somente leitura neste método.'
            )

        from vercel.blob import BlobError, BlobNotFoundError

        nome = self._normalizar_nome(name)

        try:
            with self._cliente() as cliente:
                resultado = cliente.get(
                    nome,
                    access=self.access,
                    use_cache=False,
                )
        except BlobNotFoundError as erro:
            raise FileNotFoundError(nome) from erro
        except BlobError as erro:
            raise OSError(
                'Não foi possível ler o arquivo no Vercel Blob.'
            ) from erro

        arquivo = File(
            BytesIO(resultado.content),
            name=nome,
        )
        arquivo.size = len(resultado.content)

        return arquivo

    def _save(self, name, content):

        from vercel.blob import BlobError

        nome = self._normalizar_nome(name)

        try:
            content.open('rb')
        except (AttributeError, TypeError):
            pass

        dados = content.read()

        if isinstance(dados, str):
            dados = dados.encode()

        tipo_conteudo = (
            getattr(content, 'content_type', None)
            or mimetypes.guess_type(nome)[0]
            or 'application/octet-stream'
        )

        try:
            with self._cliente() as cliente:
                resultado = cliente.put(
                    nome,
                    dados,
                    access=self.access,
                    content_type=tipo_conteudo,
                    add_random_suffix=False,
                    overwrite=False,
                )
        except BlobError as erro:
            raise OSError(
                'Não foi possível salvar o arquivo no Vercel Blob.'
            ) from erro

        return resultado.pathname

    def delete(self, name):

        if not name:
            return

        from vercel.blob import BlobError, BlobNotFoundError

        nome = self._normalizar_nome(name)

        try:
            with self._cliente() as cliente:
                cliente.delete(nome)
        except BlobNotFoundError:
            return
        except BlobError as erro:
            raise OSError(
                'Não foi possível excluir o arquivo do Vercel Blob.'
            ) from erro

    def exists(self, name):

        from vercel.blob import BlobError, BlobNotFoundError

        nome = self._normalizar_nome(name)

        try:
            with self._cliente() as cliente:
                cliente.head(nome)
        except BlobNotFoundError:
            return False
        except BlobError as erro:
            raise OSError(
                'Não foi possível consultar o Vercel Blob.'
            ) from erro

        return True

    def size(self, name):

        return self._cabecalho(name).size

    def url(self, name):

        # A URL permanece privada. O SGTCC entrega o conteúdo somente pelas
        # views de download que já verificam o usuário e sua participação.
        return self._cabecalho(name).url

    def get_created_time(self, name):

        return self._cabecalho(name).uploaded_at

    def get_modified_time(self, name):

        return self._cabecalho(name).uploaded_at

    def _cabecalho(self, name):

        from vercel.blob import BlobError, BlobNotFoundError

        nome = self._normalizar_nome(name)

        try:
            with self._cliente() as cliente:
                return cliente.head(nome)
        except BlobNotFoundError as erro:
            raise FileNotFoundError(nome) from erro
        except BlobError as erro:
            raise OSError(
                'Não foi possível consultar o Vercel Blob.'
            ) from erro
