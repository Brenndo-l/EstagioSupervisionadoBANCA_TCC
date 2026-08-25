from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .tokens import token_confirmacao_email


def enviar_email_confirmacao_docente(
    request,
    usuario
):

    uid = urlsafe_base64_encode(
        force_bytes(usuario.pk)
    )

    token = token_confirmacao_email.make_token(
        usuario
    )

    caminho_confirmacao = reverse(
        'confirmar_email_docente',
        kwargs={
            'uidb64': uid,
            'token': token,
        }
    )

    link_confirmacao = (
        request.build_absolute_uri(
            caminho_confirmacao
        )
    )

    # No ambiente local, mostra uma cópia limpa do link,
    # sem a codificação e as quebras do conteúdo do e-mail.
    if settings.DEBUG:

        print()
        print('=' * 70)
        print('LINK DE CONFIRMAÇÃO DO DOCENTE:')
        print(link_confirmacao)
        print('=' * 70)
        print()

    contexto = {
        'usuario': usuario,
        'link_confirmacao': link_confirmacao,
    }

    assunto = (
        'Confirme seu cadastro no SGTCC'
    )

    mensagem_texto = render_to_string(
        'emails/confirmacao_docente.txt',
        contexto
    )

    mensagem_html = render_to_string(
        'emails/confirmacao_docente.html',
        contexto
    )

    email = EmailMultiAlternatives(
        subject=assunto,
        body=mensagem_texto,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[usuario.email],
    )

    email.attach_alternative(
        mensagem_html,
        'text/html'
    )

    email.send(
        fail_silently=False
    )