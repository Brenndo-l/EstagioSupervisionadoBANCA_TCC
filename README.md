SGTCC - Sistema de Gerenciamento de Bancas de TCC

Sistema desenvolvido para apoiar a Coordenação do Curso de Bacharelado em
Sistemas de Informação da Universidade Federal do Acre no agendamento, na
análise e no acompanhamento de bancas de Trabalho de Conclusão de Curso.

Funcionalidades principais

cadastro e confirmação de docentes com e-mail institucional @ufac.br;

recuperação de senha por e-mail;

perfis separados de Coordenação e docente;

gerenciamento de salas, laboratórios e disponibilidades;

solicitação integrada aos dados do discente e do TCC;

autocomplete dos integrantes internos da banca;

prevenção de conflitos de espaço e de todos os integrantes;

análise, edição, aprovação, recusa e expiração de solicitações;

ciclo da banca: agendada, aguardando nota e finalizada;

registro da nota exclusivamente pelo orientador;

geração da Ata de Apresentação em PDF e DOCX;

repositório institucional de arquivos de referência;

notificações por e-mail;

páginas de erro e permissões protegidas pelo backend;

backup, auditoria e limpeza controlada da demonstração.

Requisitos

Python 3.12 ou versão compatível com Django 6;

pip;

ambiente virtual recomendado.

Dependências declaradas em requirements.txt:

Django;

python-docx;

ReportLab.

Instalação no Windows

No PowerShell, dentro da pasta do projeto:

python -m venv venv
venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

O sistema ficará disponível em:

http://127.0.0.1:8000/

Configuração por ambiente

O arquivo .env.example documenta as variáveis suportadas. Ele é somente uma
referência e não é carregado automaticamente pelo Django.

No desenvolvimento local, o projeto utiliza valores seguros para teste sem
exigir configuração adicional. Em produção, configure pelo menos:

DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<chave longa e aleatória>
DJANGO_ALLOWED_HOSTS=<domínio do sistema>
DJANGO_CSRF_TRUSTED_ORIGINS=https://<domínio do sistema>

As credenciais SMTP também devem ser cadastradas como variáveis de ambiente.
Nunca grave senhas, chaves ou credenciais reais no Git.

Perfis do sistema

Docente

envia solicitações de banca;

torna-se automaticamente o orientador do TCC solicitado;

acompanha solicitações das quais participa;

acessa os documentos autorizados;

registra a nota quando é o orientador da banca.

Coordenação

gerencia salas e disponibilidades;

analisa e edita solicitações pendentes;

define ou confirma o presidente entre os integrantes internos;

aprova ou recusa solicitações;

consulta todas as bancas e documentos;

gerencia o repositório institucional de referência.

Regras centrais da banca

o docente solicitante é sempre o orientador;

o presidente deve ser um dos integrantes internos indicados;

o orientador pode exercer a função de presidente;

todos os integrantes internos participam da validação de conflito;

uma solicitação aprovada cria o registro oficial da banca;

somente o orientador registra a nota;

a nota deve estar entre 0,00 e 10,00, com até duas casas decimais;

depois da defesa, a banca passa para AGUARDANDO_NOTA;

após o registro da nota, passa para FINALIZADA;

o prazo da versão final é de 30 dias corridos após a defesa.

Documentos

A tela possui duas áreas diferentes:

Atas geradas automaticamente: PDF e DOCX preenchidos com os dados da
solicitação, da composição e da banca.

Repositório institucional de referência: modelos oficiais em branco,
orientações e arquivos auxiliares enviados pela Coordenação.

Os arquivos do repositório não alteram automaticamente a geração das atas.

Testes automatizados

Antes de entregar uma alteração, execute:

python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py test

Para conferir as proteções de produção depois de configurar as variáveis:

python manage.py check --deploy

Auditoria de integridade

O comando abaixo procura registros legados ou incoerentes sem alterar o banco:

python manage.py auditar_integridade_sgtcc

Para utilizar a auditoria em um procedimento de QA e retornar erro quando
existir alguma inconsistência:

python manage.py auditar_integridade_sgtcc --falhar-em-inconsistencia

Entre outras verificações, a auditoria identifica:

solicitação sem composição;

orientador diferente do solicitante;

presidente fora da composição;

solicitação aprovada sem presidente ou banca;

banca antiga sem solicitação;

divergência de projeto, espaço ou horários;

banca finalizada sem nota;

nota registrada fora do estado finalizado.

Backup do desenvolvimento e da demonstração

Para criar um ZIP consistente do SQLite e da pasta media:

python manage.py criar_backup_sgtcc

O backup será gravado em backups/ e conterá:

cópia consistente do db.sqlite3;

arquivos da pasta media;

manifesto JSON com contagens, tamanhos e hashes SHA-256.

É possível escolher outro destino:

python manage.py criar_backup_sgtcc --saida "C:\Backups\sgtcc.zip"

O comando não sobrescreve um arquivo existente. Em produção com PostgreSQL,
deve ser utilizada a ferramenta de backup da hospedagem ou o pg_dump.

Limpeza do ambiente de demonstração

O comando sem confirmação apenas mostra uma prévia:

python manage.py limpar_dados_demonstracao

Depois de criar e conferir um backup, a limpeza operacional pode ser executada
com a confirmação literal:

python manage.py limpar_dados_demonstracao --confirmar LIMPAR-DEMONSTRACAO

Por padrão, usuários, perfis, espaços, disponibilidades e modelos de referência
são preservados. Consulte a ajuda antes de usar opções adicionais:

python manage.py limpar_dados_demonstracao --help

Arquivos estáticos e mídia

arquivos CSS, JavaScript e imagens da interface ficam em static/;

PDFs de TCC e modelos enviados ficam em media/;

media/, bancos locais, backups e segredos não devem ser versionados;

em produção, a mídia precisa utilizar armazenamento persistente;

execute python manage.py collectstatic durante a implantação.

Preparação para produção

Antes do deploy definitivo:

utilizar PostgreSQL;

configurar armazenamento persistente de mídia;

cadastrar todas as variáveis de ambiente;

configurar SMTP e domínio reais;

ativar HTTPS e cookies seguros;

executar migrations e collectstatic;

executar check --deploy, auditoria e todos os testes;

criar a conta real da Coordenação;

homologar o fluxo completo com a Coordenação.

Observação institucional

Os documentos gerados não inserem números de processo, códigos verificadores,
CRC, blocos de assinatura eletrônica ou outros elementos acrescentados pelo
SEI. Esses elementos pertencem ao fluxo posterior dentro do próprio sistema
institucional.