"""Cria com segurança a primeira conta da Coordenação."""

import getpass
import os

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from bancasapp.models import pUsuario


class Command(BaseCommand):
    help = (
        'Cria a conta inicial da Coordenação e o perfil correspondente. '
        'A senha é lida de forma oculta ou da variável '
        'SGTCC_COORDENACAO_PASSWORD.'
    )

    def add_arguments(self, parser):

        parser.add_argument(
            '--usuario',
            required=True,
            help='Usuário usado no login (por exemplo, coordenacao).',
        )
        parser.add_argument(
            '--email',
            required=True,
            help='E-mail da Coordenação.',
        )
        parser.add_argument(
            '--nome',
            default='',
            help='Primeiro nome da pessoa responsável.',
        )
        parser.add_argument(
            '--sobrenome',
            default='',
            help='Sobrenome da pessoa responsável.',
        )
        parser.add_argument(
            '--superusuario',
            action='store_true',
            help='Também concede acesso ao Django Admin.',
        )

    def handle(self, *args, **options):

        usuario_login = options['usuario'].strip()
        email = options['email'].strip().lower()

        if not usuario_login:
            raise CommandError('O usuário não pode ficar vazio.')

        if not email:
            raise CommandError('O e-mail não pode ficar vazio.')

        if User.objects.filter(username__iexact=usuario_login).exists():
            raise CommandError(
                'Já existe uma conta com esse usuário. '
                'Nenhum dado foi alterado.'
            )

        if User.objects.filter(email__iexact=email).exists():
            raise CommandError(
                'Já existe uma conta com esse e-mail. '
                'Nenhum dado foi alterado.'
            )

        senha = os.environ.get(
            'SGTCC_COORDENACAO_PASSWORD',
            '',
        )

        if not senha:
            senha = getpass.getpass('Senha da Coordenação: ')
            confirmacao = getpass.getpass('Confirme a senha: ')

            if senha != confirmacao:
                raise CommandError('As senhas informadas não coincidem.')

        usuario = User(
            username=usuario_login,
            email=email,
            first_name=options['nome'].strip(),
            last_name=options['sobrenome'].strip(),
            is_active=True,
            is_staff=options['superusuario'],
            is_superuser=options['superusuario'],
        )

        try:
            validate_password(senha, user=usuario)
        except ValidationError as erro:
            raise CommandError(' '.join(erro.messages)) from erro

        with transaction.atomic():
            usuario.set_password(senha)
            usuario.save()

            pUsuario.objects.create(
                usuario=usuario,
                perfil='COORDENACAO',
            )

        perfil_administrativo = (
            ' com acesso ao Django Admin'
            if options['superusuario']
            else ''
        )

        self.stdout.write(
            self.style.SUCCESS(
                'Conta da Coordenação criada com sucesso'
                f'{perfil_administrativo}.'
            )
        )
