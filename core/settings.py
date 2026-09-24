"""Configurações do SGTCC para desenvolvimento e produção."""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from django.utils.csp import CSP

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# A Vercel define estas variáveis durante build e execução. A identificação
# explícita permite aplicar limites compatíveis com o ambiente serverless e
# falhar cedo quando algum serviço obrigatório não estiver conectado.
VERCEL_RUNTIME = bool(
    os.environ.get('VERCEL', '').strip()
    or os.environ.get('VERCEL_ENV', '').strip()
)

def variavel_booleana(nome, padrao=False):
    """Converte uma variável de ambiente em booleano."""

    valor = os.environ.get(nome)

    if valor is None:
        return padrao

    valor_normalizado = valor.strip().casefold()

    if valor_normalizado in {
        '1',
        'true',
        'sim',
        'yes',
        'on',
    }:
        return True

    if valor_normalizado in {
        '0',
        'false',
        'nao',
        'não',
        'no',
        'off',
    }:
        return False

    raise ImproperlyConfigured(
        f'{nome} deve receber True ou False.'
    )


def variavel_lista(nome, padrao=''):
    """Converte valores separados por vírgula em uma lista limpa."""

    return [
        item.strip()
        for item in os.environ.get(nome, padrao).split(',')
        if item.strip()
    ]


def variavel_obrigatoria(nome):
    """Lê uma variável obrigatória sem expor seu conteúdo em erros."""

    valor = os.environ.get(nome, '').strip()

    if not valor:
        raise ImproperlyConfigured(
            f'Defina a variável de ambiente {nome}.'
        )

    return valor


def variavel_inteira(nome, padrao, minimo=0, maximo=None):
    """Lê uma variável inteira e rejeita configurações perigosas."""

    valor_bruto = os.environ.get(nome, str(padrao)).strip()

    try:
        valor = int(valor_bruto)
    except ValueError as erro:
        raise ImproperlyConfigured(
            f'{nome} deve receber um número inteiro.'
        ) from erro

    if valor < minimo or (maximo is not None and valor > maximo):
        intervalo = f'entre {minimo} e {maximo}' if maximo else f'maior ou igual a {minimo}'

        raise ImproperlyConfigured(
            f'{nome} deve ser {intervalo}.'
        )

    return valor


# O desenvolvimento local continua funcionando sem configuração adicional.
# Em produção, a chave passa a ser obrigatória por variável de ambiente.
DEBUG = variavel_booleana(
    'DJANGO_DEBUG',
    not VERCEL_RUNTIME
)

if VERCEL_RUNTIME and DEBUG:
    raise ImproperlyConfigured(
        'DJANGO_DEBUG deve ser False na Vercel. '
        'Remova a variável ou altere seu valor antes do deploy.'
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

if not DEBUG and (
    len(SECRET_KEY) < 50
    or SECRET_KEY.startswith('django-insecure-')
):
    raise ImproperlyConfigured(
        'DJANGO_SECRET_KEY deve possuir pelo menos 50 caracteres, '
        'ser aleatória e não pode usar o prefixo de desenvolvimento.'
    )

ALLOWED_HOSTS = variavel_lista(
    'DJANGO_ALLOWED_HOSTS',
    '127.0.0.1,localhost,[::1],testserver'
    if DEBUG
    else ''
)

# Os domínios gerados pela própria Vercel mudam entre Production e Preview.
# Eles são fornecidos sem protocolo e podem ser incluídos sem abrir o sistema
# para qualquer host da internet.
for nome_variavel in (
    'VERCEL_URL',
    'VERCEL_BRANCH_URL',
    'VERCEL_PROJECT_PRODUCTION_URL',
):
    host_vercel = os.environ.get(nome_variavel, '').strip().lower()

    if (
        host_vercel
        and '://' not in host_vercel
        and '/' not in host_vercel
        and host_vercel not in ALLOWED_HOSTS
    ):
        ALLOWED_HOSTS.append(host_vercel)

if not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        'Defina DJANGO_ALLOWED_HOSTS antes de iniciar o sistema '
        'em produção.'
    )

if not DEBUG and '*' in ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        'Não use * em DJANGO_ALLOWED_HOSTS na produção.'
    )

CSRF_TRUSTED_ORIGINS = variavel_lista(
    'DJANGO_CSRF_TRUSTED_ORIGINS'
)

for host_vercel in ALLOWED_HOSTS:
    if host_vercel.endswith('.vercel.app'):
        origem_vercel = f'https://{host_vercel}'

        if origem_vercel not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(origem_vercel)


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
    'django.middleware.csp.ContentSecurityPolicyMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'bancasapp.middleware.CabecalhosSegurancaMiddleware',
    'bancasapp.middleware.LimiteRequisicoesAutenticacaoMiddleware',
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


# Banco de dados
# Na Vercel/Neon, DATABASE_URL é fornecida automaticamente.
# Localmente, sem DATABASE_URL, o SQLite continua sendo o padrão.
DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    '',
).strip()

if VERCEL_RUNTIME and not DATABASE_URL:
    raise ImproperlyConfigured(
        'Defina DATABASE_URL na Vercel conectando o banco PostgreSQL '
        'do Neon ao projeto.'
    )

if DATABASE_URL:

    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=variavel_inteira(
                'DJANGO_DB_CONN_MAX_AGE',
                0,
                minimo=0,
            ),
            conn_health_checks=True,
        )
    }

    # O endereço recomendado do Neon utiliza PgBouncer.
    # Desativar cursores no servidor evita incompatibilidades
    # com o pool de conexões em ambiente serverless.
    DATABASES['default']['DISABLE_SERVER_SIDE_CURSORS'] = True

else:

    # SQLite continua sendo o padrão local. Também permanece possível
    # configurar PostgreSQL manualmente pelas variáveis DJANGO_DB_*.
    SGTCC_DATABASE_ENGINE = os.environ.get(
        'DJANGO_DB_ENGINE',
        'sqlite',
    ).strip().casefold()

    if SGTCC_DATABASE_ENGINE == 'sqlite':

        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': os.environ.get(
                    'DJANGO_DB_NAME',
                    str(BASE_DIR / 'db.sqlite3'),
                ),
            }
        }

    elif SGTCC_DATABASE_ENGINE in {
        'postgres',
        'postgresql',
    }:

        opcoes_postgresql = {}

        modo_ssl = os.environ.get(
            'DJANGO_DB_SSLMODE',
            '',
        ).strip()

        if modo_ssl:
            opcoes_postgresql['sslmode'] = modo_ssl

        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': variavel_obrigatoria(
                    'DJANGO_DB_NAME'
                ),
                'USER': variavel_obrigatoria(
                    'DJANGO_DB_USER'
                ),
                'PASSWORD': variavel_obrigatoria(
                    'DJANGO_DB_PASSWORD'
                ),
                'HOST': variavel_obrigatoria(
                    'DJANGO_DB_HOST'
                ),
                'PORT': variavel_inteira(
                    'DJANGO_DB_PORT',
                    5432,
                    minimo=1,
                    maximo=65535,
                ),
                'CONN_MAX_AGE': variavel_inteira(
                    'DJANGO_DB_CONN_MAX_AGE',
                    60,
                    minimo=0,
                ),
                'CONN_HEALTH_CHECKS': True,
                'OPTIONS': opcoes_postgresql,
            }
        }

    else:

        raise ImproperlyConfigured(
            'DJANGO_DB_ENGINE deve ser sqlite ou postgresql.'
        )


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 12,
        },
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

# O sistema de arquivos da Vercel é somente leitura e não preserva uploads.
# Ao conectar um Vercel Blob privado, a integração cria automaticamente esta
# variável. Sem ela, o desenvolvimento local continua usando a pasta media.
BLOB_READ_WRITE_TOKEN = (
    os.environ.get(
        'BLOB_READ_WRITE_TOKEN',
        '',
    ).strip()
    or os.environ.get(
        'VERCEL_BLOB_READ_WRITE_TOKEN',
        '',
    ).strip()
)

BLOB_STORE_ID = os.environ.get(
    'BLOB_STORE_ID',
    '',
).strip()

if VERCEL_RUNTIME and not BLOB_READ_WRITE_TOKEN:
    raise ImproperlyConfigured(
        'O Vercel Blob privado precisa fornecer BLOB_READ_WRITE_TOKEN. '
        'BLOB_STORE_ID e BLOB_WEBHOOK_PUBLIC_KEY não autorizam leitura '
        'ou gravação. Na conexão do Blob com o projeto, ative a opção '
        'de adicionar o token de leitura e escrita e faça novo deploy.'
    )

STORAGES = {
    'default': {
        'BACKEND': (
            'bancasapp.storage_backends.VercelBlobStorage'
            if BLOB_READ_WRITE_TOKEN
            else 'django.core.files.storage.FileSystemStorage'
        ),
    },
    'staticfiles': {
        'BACKEND': (
            'django.contrib.staticfiles.storage.StaticFilesStorage'
        ),
    },
}

# A Vercel limita o corpo de cada requisição e resposta da Function. O teto de
# 4 MB deixa margem para os demais campos do formulário. Em um servidor
# tradicional, os limites históricos do SGTCC continuam disponíveis.
SGTCC_MAX_TCC_UPLOAD_MB = variavel_inteira(
    'SGTCC_MAX_TCC_UPLOAD_MB',
    4 if VERCEL_RUNTIME else 25,
    minimo=1,
    maximo=4 if VERCEL_RUNTIME else 25,
)

SGTCC_MAX_MODELO_UPLOAD_MB = variavel_inteira(
    'SGTCC_MAX_MODELO_UPLOAD_MB',
    4 if VERCEL_RUNTIME else 10,
    minimo=1,
    maximo=4 if VERCEL_RUNTIME else 10,
)

# Sessão persistente por 14 dias quando o usuário
# selecionar a opção "Manter conectado".
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14

# Por padrão, a sessão termina ao fechar o navegador.
# A tela de login poderá substituir essa configuração
# individualmente quando "Manter conectado" for marcado.
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'

# Limites internos complementam o limite de corpo configurado no proxy.
# A validação individual dos arquivos continua nos formulários do SGTCC.
DATA_UPLOAD_MAX_MEMORY_SIZE = 2_621_440
FILE_UPLOAD_MAX_MEMORY_SIZE = 2_621_440
DATA_UPLOAD_MAX_NUMBER_FIELDS = 200
DATA_UPLOAD_MAX_NUMBER_FILES = 1
FILE_UPLOAD_PERMISSIONS = 0o640
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o750

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

SECURE_HSTS_SECONDS = variavel_inteira(
    'DJANGO_SECURE_HSTS_SECONDS',
    3600 if VERCEL_RUNTIME and not DEBUG else 0,
    minimo=0,
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
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'

# Política aplicada a todas as respostas HTML. O JavaScript é aceito somente
# quando vem dos arquivos estáticos do próprio sistema. Estilos inline ainda
# são permitidos porque existem em telas legadas e documentos de visualização.
SECURE_CSP = {
    'default-src': [CSP.SELF],
    'base-uri': [CSP.SELF],
    'connect-src': [CSP.SELF],
    'font-src': [CSP.SELF],
    'form-action': [CSP.SELF],
    'frame-ancestors': [CSP.NONE],
    'frame-src': [CSP.SELF],
    'img-src': [CSP.SELF, 'data:'],
    'object-src': [CSP.NONE],
    'script-src': [CSP.SELF],
    'style-src': [CSP.SELF, CSP.UNSAFE_INLINE],
}

# Proteção contra força bruta e abuso de envio de e-mails. Os contadores são
# armazenados no banco apenas como HMAC, sem e-mail, usuário ou IP legível.
SGTCC_RATE_LIMIT_ENABLED = variavel_booleana(
    'SGTCC_RATE_LIMIT_ENABLED',
    True,
)
SGTCC_RATE_LIMIT_LOGIN_ATTEMPTS = variavel_inteira(
    'SGTCC_RATE_LIMIT_LOGIN_ATTEMPTS',
    8,
    minimo=2,
)
SGTCC_RATE_LIMIT_LOGIN_WINDOW = variavel_inteira(
    'SGTCC_RATE_LIMIT_LOGIN_WINDOW',
    900,
    minimo=60,
)
SGTCC_RATE_LIMIT_EMAIL_ATTEMPTS = variavel_inteira(
    'SGTCC_RATE_LIMIT_EMAIL_ATTEMPTS',
    5,
    minimo=2,
)
SGTCC_RATE_LIMIT_EMAIL_WINDOW = variavel_inteira(
    'SGTCC_RATE_LIMIT_EMAIL_WINDOW',
    3600,
    minimo=60,
)
SGTCC_RATE_LIMIT_IP_ATTEMPTS = variavel_inteira(
    'SGTCC_RATE_LIMIT_IP_ATTEMPTS',
    40,
    minimo=5,
)
SGTCC_RATE_LIMIT_IP_WINDOW = variavel_inteira(
    'SGTCC_RATE_LIMIT_IP_WINDOW',
    900,
    minimo=60,
)
SGTCC_RATE_LIMIT_RETENTION_DAYS = variavel_inteira(
    'SGTCC_RATE_LIMIT_RETENTION_DAYS',
    7,
    minimo=1,
)
SGTCC_TRUST_PROXY_CLIENT_IP = variavel_booleana(
    'SGTCC_TRUST_PROXY_CLIENT_IP',
    False,
)

if variavel_booleana(
    'DJANGO_TRUST_PROXY_SSL_HEADER',
    VERCEL_RUNTIME
):
    SECURE_PROXY_SSL_HEADER = (
        'HTTP_X_FORWARDED_PROTO',
        'https',
    )

# Durante o desenvolvimento, o conteúdo do e-mail aparece no terminal.
# Em produção, todas as opções podem ser definidas pelo serviço de SMTP.
EMAIL_BACKEND = os.environ.get(
    'DJANGO_EMAIL_BACKEND',
    (
        'django.core.mail.backends.console.EmailBackend'
        if DEBUG
        else 'django.core.mail.backends.smtp.EmailBackend'
    ),
).strip()

EMAIL_HOST = os.environ.get(
    'DJANGO_EMAIL_HOST',
    ''
).strip()

EMAIL_PORT = variavel_inteira(
    'DJANGO_EMAIL_PORT',
    587,
    minimo=1,
    maximo=65535,
)

EMAIL_HOST_USER = os.environ.get(
    'DJANGO_EMAIL_HOST_USER',
    ''
).strip()

EMAIL_HOST_PASSWORD = os.environ.get(
    'DJANGO_EMAIL_HOST_PASSWORD',
    ''
).strip()

EMAIL_USE_TLS = variavel_booleana(
    'DJANGO_EMAIL_USE_TLS',
    True
)

EMAIL_USE_SSL = variavel_booleana(
    'DJANGO_EMAIL_USE_SSL',
    False
)

if EMAIL_USE_TLS and EMAIL_USE_SSL:
    raise ImproperlyConfigured(
        'Ative somente uma opção: DJANGO_EMAIL_USE_TLS ou '
        'DJANGO_EMAIL_USE_SSL.'
    )

EMAIL_TIMEOUT = variavel_inteira(
    'DJANGO_EMAIL_TIMEOUT',
    15,
    minimo=1,
    maximo=120,
)

DEFAULT_FROM_EMAIL = os.environ.get(
    'DJANGO_DEFAULT_FROM_EMAIL',
    'SGTCC <sistemas.ccet@ufac.br>'
).strip()

SMTP_EMAIL_BACKEND = (
    'django.core.mail.backends.smtp.EmailBackend'
)

if VERCEL_RUNTIME:

    if EMAIL_BACKEND != SMTP_EMAIL_BACKEND:
        raise ImproperlyConfigured(
            'DJANGO_EMAIL_BACKEND deve usar '
            'django.core.mail.backends.smtp.EmailBackend na Vercel. '
            'O backend de console apenas escreve o e-mail nos logs.'
        )

    configuracoes_smtp_obrigatorias = {
        'DJANGO_EMAIL_HOST': EMAIL_HOST,
        'DJANGO_EMAIL_HOST_USER': EMAIL_HOST_USER,
        'DJANGO_EMAIL_HOST_PASSWORD': EMAIL_HOST_PASSWORD,
        'DJANGO_DEFAULT_FROM_EMAIL': os.environ.get(
            'DJANGO_DEFAULT_FROM_EMAIL',
            '',
        ).strip(),
    }

    configuracoes_smtp_ausentes = [
        nome
        for nome, valor in configuracoes_smtp_obrigatorias.items()
        if not valor
    ]

    if configuracoes_smtp_ausentes:
        raise ImproperlyConfigured(
            'Configure o SMTP real na Vercel. Variáveis ausentes: '
            + ', '.join(configuracoes_smtp_ausentes)
            + '.'
        )

# Validade do link de confirmação: 24 horas.
PASSWORD_RESET_TIMEOUT = 60 * 60 * 24


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'sgtcc': {
            'format': '{asctime} {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'sgtcc',
        },
    },
    'loggers': {
        'django.request': {
            'handlers': ['console'],
            'level': os.environ.get('DJANGO_LOG_LEVEL', 'WARNING'),
            'propagate': False,
        },
        'bancasapp': {
            'handlers': ['console'],
            'level': os.environ.get('SGTCC_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    },
}
