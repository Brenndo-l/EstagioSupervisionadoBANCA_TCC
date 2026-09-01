"""Configurações do SGTCC para desenvolvimento e produção."""

import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


def variavel_booleana(nome, padrao=False):
    """Converte uma variável de ambiente em booleano."""

    valor = os.environ.get(nome)

    if valor is None:
        return padrao

    return valor.strip().casefold() in {
        '1',
        'true',
        'sim',
        'yes',
        'on',
    }


def variavel_lista(nome, padrao=''):
    """Converte valores separados por vírgula em uma lista limpa."""

    return [
        item.strip()
        for item in os.environ.get(nome, padrao).split(',')
        if item.strip()
    ]


# O desenvolvimento local continua funcionando sem configuração adicional.
# Em produção, a chave passa a ser obrigatória por variável de ambiente.
DEBUG = variavel_booleana(
    'DJANGO_DEBUG',
    True
)

SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    ''
).strip()

if not SECRET_KEY:

    if DEBUG:
        SECRET_KEY = (
            'django-insecure-'
            '=c8+rq6rc7lhgj0koy!saasf%-%q7&9g!7dga&=g_p0+ar91#f'
        )

    else:
        raise ImproperlyConfigured(
            'Defina DJANGO_SECRET_KEY antes de iniciar o sistema '
            'com DJANGO_DEBUG=False.'
        )

ALLOWED_HOSTS = variavel_lista(
    'DJANGO_ALLOWED_HOSTS',
    '127.0.0.1,localhost,[::1],testserver'
    if DEBUG
    else ''
)

if not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        'Defina DJANGO_ALLOWED_HOSTS antes de iniciar o sistema '
        'em produção.'
    )

CSRF_TRUSTED_ORIGINS = variavel_lista(
    'DJANGO_CSRF_TRUSTED_ORIGINS'
)


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'bancasapp', 
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'America/Rio_Branco'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = 'static/'

STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Sessão persistente por 14 dias quando o usuário
# selecionar a opção "Manter conectado".
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14

# Por padrão, a sessão termina ao fechar o navegador.
# A tela de login poderá substituir essa configuração
# individualmente quando "Manter conectado" for marcado.
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# Proteções ativadas automaticamente quando DEBUG=False. O HSTS permanece
# configurável e começa em zero para evitar bloquear o domínio antes de o
# HTTPS definitivo estar validado.
SESSION_COOKIE_SECURE = variavel_booleana(
    'DJANGO_SESSION_COOKIE_SECURE',
    not DEBUG
)

CSRF_COOKIE_SECURE = variavel_booleana(
    'DJANGO_CSRF_COOKIE_SECURE',
    not DEBUG
)

SECURE_SSL_REDIRECT = variavel_booleana(
    'DJANGO_SECURE_SSL_REDIRECT',
    not DEBUG
)

SECURE_HSTS_SECONDS = int(
    os.environ.get(
        'DJANGO_SECURE_HSTS_SECONDS',
        '0'
    )
)

SECURE_HSTS_INCLUDE_SUBDOMAINS = variavel_booleana(
    'DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS',
    False
)

SECURE_HSTS_PRELOAD = variavel_booleana(
    'DJANGO_SECURE_HSTS_PRELOAD',
    False
)

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'

if variavel_booleana(
    'DJANGO_TRUST_PROXY_SSL_HEADER',
    False
):
    SECURE_PROXY_SSL_HEADER = (
        'HTTP_X_FORWARDED_PROTO',
        'https',
    )

# Durante o desenvolvimento, o conteúdo do e-mail aparece no terminal.
# Em produção, todas as opções podem ser definidas pelo serviço de SMTP.
EMAIL_BACKEND = os.environ.get(
    'DJANGO_EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend'
)

EMAIL_HOST = os.environ.get(
    'DJANGO_EMAIL_HOST',
    ''
)

EMAIL_PORT = int(
    os.environ.get(
        'DJANGO_EMAIL_PORT',
        '587'
    )
)

EMAIL_HOST_USER = os.environ.get(
    'DJANGO_EMAIL_HOST_USER',
    ''
)

EMAIL_HOST_PASSWORD = os.environ.get(
    'DJANGO_EMAIL_HOST_PASSWORD',
    ''
)

EMAIL_USE_TLS = variavel_booleana(
    'DJANGO_EMAIL_USE_TLS',
    True
)

EMAIL_USE_SSL = variavel_booleana(
    'DJANGO_EMAIL_USE_SSL',
    False
)

DEFAULT_FROM_EMAIL = os.environ.get(
    'DJANGO_DEFAULT_FROM_EMAIL',
    'SGTCC <nao-responda@ufac.br>'
)

# Validade do link de confirmação: 24 horas.
PASSWORD_RESET_TIMEOUT = 60 * 60 * 24
