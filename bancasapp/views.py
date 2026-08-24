from django.shortcuts import render, redirect, get_object_or_404
from .forms import SolicitacaoBancaForm, EdicaoSolicitacaoCoordenacaoForm, DiscenteForm, ProjetoTCCForm, ModeloDocumentoForm, AvaliacaoSolicitacaoForm, EspacoFisicoForm, DisponibilidadeEspacoForm
from .models import ProjetoTCC, pUsuario, SolicitacaoAgendamento, BancaTCC, EspacoFisico, ComposicaoBanca, ModeloDocumento, DisponibilidadeEspaco
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import FileResponse, HttpResponse
from pathlib import Path
from django.template.loader import get_template
from xhtml2pdf import pisa
from .permissions import (
    usuario_e_coordenacao,
    usuario_interno_required,
    docente_required,
    coordenacao_required,
)
from django.db import transaction
from django.utils import timezone
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
from .services import expirar_solicitacoes_vencidas



# 1. Tela inicial do sistema (Dashboard com os botões principais)
# 1. Tela inicial do sistema
@usuario_interno_required
def dashboard(request):

    expirar_solicitacoes_vencidas() 

    is_coordenacao = usuario_e_coordenacao(
        request.user
    )

    # Valores usados somente pela Coordenação.
    historico_decisoes = None
    status_historico = ''

    if is_coordenacao:

        # Agora a aprovação cria uma BancaTCC oficial.
        total_bancas = BancaTCC.objects.count()

        total_pendentes = (
            SolicitacaoAgendamento.objects.filter(
                status='EM_ANÁLISE'
            ).count()
        )

        # Últimas cinco solicitações aguardando avaliação.
        ultimos_pedidos = (
            SolicitacaoAgendamento.objects
            .select_related(
                'projeto_tcc',
                'projeto_tcc__discente',
                'espaco',
                'usuario_solicitante',
                'usuario_solicitante__usuario'
            )
            .filter(
                status='EM_ANÁLISE'
            )
            .order_by('-data_solicitacao', '-id')[:5]
        )

        # Lê o filtro selecionado na tela.
        status_historico = (
            request.GET.get('historico', '').strip()
        )

        # Aceita somente os dois estados possíveis no histórico.
        if status_historico not in [
            'APROVADA',
            'RECUSADA'
        ]:
            status_historico = ''

        # Consulta base do histórico administrativo.
        historico_queryset = (
            SolicitacaoAgendamento.objects
            .select_related(
                'projeto_tcc',
                'projeto_tcc__discente',
                'espaco',
                'usuario_solicitante',
                'usuario_solicitante__usuario',
                'decidida_por',
            )
            .filter(
                status__in=['APROVADA', 'RECUSADA']
            )
            .order_by(
                '-data_decisao',
                '-id'
            )
        )

        # Aplica o filtro, caso a Coordenação tenha escolhido um.
        if status_historico:
            historico_queryset = (
                historico_queryset.filter(
                    status=status_historico
                )
            )

        # Exibe dez decisões por página.
        paginador = Paginator(
            historico_queryset,
            10
        )

        numero_pagina = request.GET.get('pagina')

        historico_decisoes = paginador.get_page(
            numero_pagina
        )

    else:

        perfil_logado = pUsuario.objects.get(
            usuario=request.user,
            perfil='DOCENTE'
        )

        total_bancas = (
            SolicitacaoAgendamento.objects.filter(
                usuario_solicitante=perfil_logado,
                status='APROVADA'
            ).count()
        )

        total_pendentes = (
            SolicitacaoAgendamento.objects.filter(
                usuario_solicitante=perfil_logado,
                status='EM_ANÁLISE'
            ).count()
        )

        # Docentes não recebem informações administrativas.
        ultimos_pedidos = None
        historico_decisoes = None

    total_salas = EspacoFisico.objects.count()

    contexto = {
        'total_bancas': total_bancas,
        'total_pendentes': total_pendentes,
        'total_salas': total_salas,
        'is_coordenacao': is_coordenacao,
        'ultimos_pedidos': ultimos_pedidos,
        'historico_decisoes': historico_decisoes,
        'status_historico': status_historico,
    }

    return render(
        request,
        'dashboard.html',
        contexto
    )

@coordenacao_required
def solicitacoes_coordenacao(request):

    expirar_solicitacoes_vencidas()

    status_atual = request.GET.get(
        'status',
        'EM_ANÁLISE'
    )

    status_permitidos = {
        'EM_ANÁLISE',
        'APROVADA',
        'RECUSADA',
        'EXPIRADA',
        'TODAS',
    }

    if status_atual not in status_permitidos:
        status_atual = 'EM_ANÁLISE'

    consulta = (
        SolicitacaoAgendamento.objects
        .select_related(
            'projeto_tcc',
            'projeto_tcc__discente',
            'espaco',
            'usuario_solicitante',
            'usuario_solicitante__usuario',
            'decidida_por',
        )
        .order_by(
            '-data_solicitacao',
            '-id'
        )
    )

    if status_atual != 'TODAS':

        consulta = consulta.filter(
            status=status_atual
        )

    paginador = Paginator(
        consulta,
        10
    )

    solicitacoes = paginador.get_page(
        request.GET.get('pagina')
    )

    contexto = {
        'solicitacoes': solicitacoes,
        'status_atual': status_atual,

        'total_pendentes': (
            SolicitacaoAgendamento.objects.filter(
                status='EM_ANÁLISE'
            ).count()
        ),

        'total_aprovadas': (
            SolicitacaoAgendamento.objects.filter(
                status='APROVADA'
            ).count()
        ),

        'total_recusadas': (
            SolicitacaoAgendamento.objects.filter(
                status='RECUSADA'
            ).count()
        ),
        'total_expiradas': (
            SolicitacaoAgendamento.objects.filter(
                status='EXPIRADA'
            ).count()
        ),
    }

    return render(
        request,
        'solicitacoes_coordenacao.html',
        contexto
    )

@coordenacao_required
def editar_solicitacao_coordenacao(
    request,
    solicitacao_id
):

    expirar_solicitacoes_vencidas()

    solicitacao = get_object_or_404(
        SolicitacaoAgendamento.objects.select_related(
            'projeto_tcc',
            'projeto_tcc__discente',
            'espaco',
            'usuario_solicitante',
            'usuario_solicitante__usuario',
        ),
        pk=solicitacao_id
    )

    # Após uma decisão, os dados passam a fazer
    # parte do histórico e não podem ser alterados.
    if solicitacao.status == 'EXPIRADA':

        messages.warning(
            request,
            'O horário desta solicitação passou '
            'antes que ela fosse avaliada.'
        )

        return redirect(
            'solicitacoes_coordenacao'
        )

    if solicitacao.status != 'EM_ANÁLISE':

        messages.warning(
            request,
            'Esta solicitação já foi avaliada '
            'pela Coordenação.'
        )

        return redirect(
            'solicitacoes_coordenacao'
        )

    composicao = (
        ComposicaoBanca.objects
        .select_related(
            'orientador__usuario',
            'coorientador__usuario',
            'avaliador_interno__usuario',
            'segundo_avaliador_interno__usuario',
        )
        .filter(
            solicitacao=solicitacao
        )
        .first()
    )

    if composicao is None:

        messages.error(
            request,
            'A composição desta solicitação '
            'não foi encontrada.'
        )

        return redirect(
            'avaliar_solicitacao',
            solicitacao_id=solicitacao.id
        )

    dados_iniciais = {
        'orientador': (
            composicao.orientador
        ),

        'coorientador': (
            composicao.coorientador
        ),

        'avaliador_interno': (
            composicao.avaliador_interno
        ),

        'segundo_avaliador_interno': (
            composicao.segundo_avaliador_interno
        ),

        'nome_avaliador_externo': (
            composicao.nome_avaliador_externo
        ),

        'instituicao_avaliador_externo': (
            composicao.instituicao_avaliador_externo
        ),
    }

    if request.method == 'POST':

        form = EdicaoSolicitacaoCoordenacaoForm(
            request.POST,
            instance=solicitacao,
            initial=dados_iniciais
        )

        if form.is_valid():

            with transaction.atomic():

                # Impede que uma solicitação seja
                # aprovada e editada simultaneamente.
                solicitacao_bloqueada = (
                    get_object_or_404(
                        SolicitacaoAgendamento.objects
                        .select_for_update(),
                        pk=solicitacao.id
                    )
                )

                if (
                    solicitacao_bloqueada.status
                    != 'EM_ANÁLISE'
                ):

                    messages.warning(
                        request,
                        'Esta solicitação acabou de ser '
                        'avaliada e não pode mais ser editada.'
                    )

                    return redirect(
                        'solicitacoes_coordenacao'
                    )

                composicao_bloqueada = (
                    get_object_or_404(
                        ComposicaoBanca.objects
                        .select_for_update(),
                        pk=composicao.id
                    )
                )

                # Atualiza somente sala e horários.
                # Projeto, solicitante e PDF permanecem
                # exatamente como estavam.
                solicitacao_bloqueada.espaco = (
                    form.cleaned_data['espaco']
                )

                solicitacao_bloqueada.opcao_data_inicio = (
                    form.cleaned_data[
                        'opcao_data_inicio'
                    ]
                )

                solicitacao_bloqueada.opcao_data_fim = (
                    form.cleaned_data[
                        'opcao_data_fim'
                    ]
                )

                solicitacao_bloqueada.save(
                    update_fields=[
                        'espaco',
                        'opcao_data_inicio',
                        'opcao_data_fim',
                    ]
                )

                composicao_bloqueada.orientador = (
                    form.cleaned_data['orientador']
                )

                composicao_bloqueada.coorientador = (
                    form.cleaned_data['coorientador']
                )

                composicao_bloqueada.avaliador_interno = (
                    form.cleaned_data[
                        'avaliador_interno'
                    ]
                )

                composicao_bloqueada.segundo_avaliador_interno = (
                    form.cleaned_data[
                        'segundo_avaliador_interno'
                    ]
                )

                composicao_bloqueada.nome_avaliador_externo = (
                    form.cleaned_data[
                        'nome_avaliador_externo'
                    ]
                )

                composicao_bloqueada.instituicao_avaliador_externo = (
                    form.cleaned_data[
                        'instituicao_avaliador_externo'
                    ]
                )

                composicao_bloqueada.save(
                    update_fields=[
                        'orientador',
                        'coorientador',
                        'avaliador_interno',
                        'segundo_avaliador_interno',
                        'nome_avaliador_externo',
                        'instituicao_avaliador_externo',
                    ]
                )

            messages.success(
                request,
                'Solicitação atualizada com sucesso.'
            )

            return redirect(
                'avaliar_solicitacao',
                solicitacao_id=solicitacao.id
            )

        # O CSS atual esconde as errorlists do Django.
        # Por isso também mostramos os erros como mensagens.
        for erros in form.errors.values():

            for erro in erros:

                messages.error(
                    request,
                    erro
                )

    else:

        form = EdicaoSolicitacaoCoordenacaoForm(
            instance=solicitacao,
            initial=dados_iniciais
        )

    return render(
        request,
        'editar_solicitacao_coordenacao.html',
        {
            'solicitacao': solicitacao,
            'form': form,
        }
    )

# 2. Tela onde aparecem as bancas já marcadas
@usuario_interno_required
def visualizar_bancas(request):

    expirar_solicitacoes_vencidas()

    consulta = (
        SolicitacaoAgendamento.objects
        .select_related(
            'projeto_tcc',
            'projeto_tcc__discente',
            'espaco',
            'usuario_solicitante',
            'usuario_solicitante__usuario'
        )
    )

    if usuario_e_coordenacao(request.user):

        # A Coordenação visualiza todas as solicitações.
        solicitacoes = consulta.all()

    else:

        # O docente visualiza apenas as próprias solicitações.
        perfil_logado = pUsuario.objects.get(
            usuario=request.user,
            perfil='DOCENTE'
        )

        solicitacoes = (
            consulta
            .filter(
                Q(
                    usuario_solicitante=perfil_logado
                )
                | Q(
                    composicao_banca__orientador=(
                        perfil_logado
                    )
                )
                | Q(
                    composicao_banca__coorientador=(
                        perfil_logado
                    )
                )
                | Q(
                    composicao_banca__avaliador_interno=(
                        perfil_logado
                    )
                )
                | Q(
                    composicao_banca__segundo_avaliador_interno=(
                        perfil_logado
                    )
                )
            )
            .distinct()
        )

    status_filtro = request.GET.get('status')

    status_validos = {
        valor
        for valor, nome
        in SolicitacaoAgendamento.STATUS_SOLICITACAO
    }

    if status_filtro in status_validos:

        solicitacoes = solicitacoes.filter(
            status=status_filtro
        )

    else:

        # Impede valores inexistentes passados manualmente
        # pela URL.
        status_filtro = None

    contexto = {
        'solicitacoes': solicitacoes,
        'status_atual': status_filtro,
    }

    return render(
        request,
        'visualizar_bancas.html',
        contexto
    )

# 3. Tela do formulário para o professor pedir a banca
@docente_required
def solicitar_banca(request):

    expirar_solicitacoes_vencidas()

    perfil_logado = pUsuario.objects.get(
        usuario=request.user,
        perfil='DOCENTE'
    )

    if request.method == 'POST':

        form = SolicitacaoBancaForm(
            request.POST,
            request.FILES
        )

        if form.is_valid():

            with transaction.atomic():

                solicitacao = form.save(
                    commit=False
                )

                solicitacao.status = 'EM_ANÁLISE'

                solicitacao.usuario_solicitante = (
                    perfil_logado
                )

                solicitacao.save()

                # Cada solicitação recebe sua própria composição.
                # Assim uma nova tentativa não altera o histórico
                # de uma solicitação anterior.
                ComposicaoBanca.objects.create(
                    solicitacao=solicitacao,
                    projeto_tcc=solicitacao.projeto_tcc,

                    orientador=(
                        form.cleaned_data['orientador']
                    ),

                    coorientador=(
                        form.cleaned_data[
                            'coorientador'
                        ]
                    ),

                    avaliador_interno=(
                        form.cleaned_data[
                            'avaliador_interno'
                        ]
                    ),

                    segundo_avaliador_interno=(
                        form.cleaned_data[
                            'segundo_avaliador_interno'
                        ]
                    ),

                    nome_avaliador_externo=(
                        form.cleaned_data[
                            'nome_avaliador_externo'
                        ]
                    ),

                    instituicao_avaliador_externo=(
                        form.cleaned_data[
                            'instituicao_avaliador_externo'
                        ]
                    ),
                )

            messages.success(
                request,
                'Solicitação de banca enviada com sucesso.'
            )

            return redirect('dashboard')

        else:

            # Mantém as mensagens dos bloqueios de horário,
            # sala, orientador e avaliador.
            for campo, erros in form.errors.items():

                for erro in erros:

                    messages.error(
                        request,
                        erro
                    )

    else:

        form = SolicitacaoBancaForm()

    contexto = {
        'form': form,
    }

    disponibilidades = (
        DisponibilidadeEspaco.objects
        .select_related('espaco')
        .filter(
            ativo=True,
            espaco__ativo=True,
            data_hora_fim__gt=timezone.now(),
        )
        .order_by(
            'data_hora_inicio',
            'espaco__nome',
        )
    )

    return render(
        request,
        'solicitar_banca.html',
        {
            'form': form,
            'disponibilidades': disponibilidades,
        }
    )

@usuario_interno_required
def baixar_tcc_solicitacao(
    request,
    solicitacao_id
):

    solicitacao = get_object_or_404(
        SolicitacaoAgendamento.objects.select_related(
            'usuario_solicitante',
            'projeto_tcc',
        ),
        pk=solicitacao_id
    )

    composicao = (
        ComposicaoBanca.objects
        .filter(
            solicitacao=solicitacao
        )
        .first()
    )

    # A Coordenação pode acessar qualquer TCC.
    acesso_permitido = usuario_e_coordenacao(
        request.user
    )

    # Para docentes, verificamos se o usuário participa
    # ou se foi responsável pela solicitação.
    if not acesso_permitido:

        perfil_logado = (
            pUsuario.objects
            .filter(
                usuario=request.user,
                perfil='DOCENTE'
            )
            .first()
        )

        participantes_ids = {
            solicitacao.usuario_solicitante_id
        }

        if composicao:

            participantes_ids.update(
                {
                    composicao.orientador_id,
                    composicao.coorientador_id,
                    composicao.avaliador_interno_id,
                    (
                        composicao
                        .segundo_avaliador_interno_id
                    ),
                }
            )

        participantes_ids.discard(
            None
        )

        acesso_permitido = (
            perfil_logado is not None
            and perfil_logado.id in participantes_ids
        )

    if not acesso_permitido:

        messages.error(
            request,
            'Você não possui permissão para acessar '
            'o arquivo deste TCC.'
        )

        return redirect(
            'dashboard'
        )

    if not solicitacao.arquivo_tcc:

        messages.warning(
            request,
            'Esta solicitação não possui um arquivo '
            'de TCC anexado.'
        )

        return redirect(
            'dashboard'
        )

    nome_arquivo = Path(
        solicitacao.arquivo_tcc.name
    ).name

    try:

        arquivo = solicitacao.arquivo_tcc.open(
            'rb'
        )

    except (FileNotFoundError, OSError):

        messages.error(
            request,
            'O arquivo do TCC não foi encontrado '
            'no armazenamento do sistema.'
        )

        return redirect(
            'dashboard'
        )

    return FileResponse(
        arquivo,
        as_attachment=True,
        filename=nome_arquivo,
        content_type='application/pdf'
    )

@login_required(login_url='login')
def cadastrar_aluno(request):
    if request.method == 'POST':
        form = DiscenteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('dashboard') # Salva e volta pro início
    else:
        form = DiscenteForm()
    
    # Enviamos o form e um título dinâmico para reaproveitarmos o HTML
    contexto = {'form': form, 'titulo': 'Cadastrar Novo Aluno'}
    return render(request, 'cadastrar_dados.html', contexto)

@login_required(login_url='login')
def cadastrar_projeto(request):
    if request.method == 'POST':
        form = ProjetoTCCForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = ProjetoTCCForm()
    
    contexto = {'form': form, 'titulo': 'Cadastrar Projeto de TCC'}
    return render(request, 'cadastrar_dados.html', contexto)

def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email")
        senha = request.POST.get("senha")
        
        usuario = authenticate(username=email, password=senha)
        
        if usuario is not None:
            login(request, usuario)
            # AVISO DE SUCESSO NO LOGIN
            messages.success(request, f'Bem-vindo(a) ao sistema!')
            return redirect("dashboard")
        else:
            # AVISO DE ERRO
            messages.error(request, 'Login ou senha incorretos.')
            return render(request, "login.html") # Tiramos aquele dicionário de erro daqui
            
    return render(request, 'login.html')

def criar_formulario_revalidacao(
    solicitacao,
    composicao
):

    inicio_local = timezone.localtime(
        solicitacao.opcao_data_inicio
    )

    fim_local = timezone.localtime(
        solicitacao.opcao_data_fim
    )

    dados_atuais = {
        'espaco': (
            solicitacao.espaco_id
        ),

        'opcao_data_inicio': (
            inicio_local.strftime(
                '%Y-%m-%dT%H:%M'
            )
        ),

        'opcao_data_fim': (
            fim_local.strftime(
                '%Y-%m-%dT%H:%M'
            )
        ),

        'orientador': (
            composicao.orientador_id
        ),

        'coorientador': (
            composicao.coorientador_id
            or ''
        ),

        'avaliador_interno': (
            composicao.avaliador_interno_id
        ),

        'segundo_avaliador_interno': (
            composicao.segundo_avaliador_interno_id
            or ''
        ),

        'nome_avaliador_externo': (
            composicao.nome_avaliador_externo
            or ''
        ),

        'instituicao_avaliador_externo': (
            composicao.instituicao_avaliador_externo
            or ''
        ),
    }

    return EdicaoSolicitacaoCoordenacaoForm(
        data=dados_atuais,
        instance=solicitacao
    )


@coordenacao_required
def avaliar_solicitacao(
    request,
    solicitacao_id
):

    expirar_solicitacoes_vencidas()

    # Carrega a solicitação e seus dados relacionados.
    solicitacao = get_object_or_404(
        SolicitacaoAgendamento.objects.select_related(
            'projeto_tcc',
            'projeto_tcc__discente',
            'espaco',
            'usuario_solicitante',
            'usuario_solicitante__usuario',
        ),
        pk=solicitacao_id
    )

    # Busca a composição vinculada especificamente
    # a esta solicitação.
    composicao = (
        ComposicaoBanca.objects
        .select_related(
            'orientador__usuario',
            'coorientador__usuario',
            'avaliador_interno__usuario',
            'segundo_avaliador_interno__usuario',
        )
        .filter(
            solicitacao=solicitacao
        )
        .first()
    )

    # Uma solicitação que passou do horário
    # não pode mais ser avaliada.
    if solicitacao.status == 'EXPIRADA':

        messages.warning(
            request,
            'O horário desta solicitação passou '
            'antes que ela fosse avaliada.'
        )

        return redirect(
            'solicitacoes_coordenacao'
        )

    # Uma solicitação já decidida também não
    # pode receber outra decisão.
    if solicitacao.status != 'EM_ANÁLISE':

        messages.warning(
            request,
            'Esta solicitação já foi avaliada '
            'pela Coordenação.'
        )

        return redirect(
            'solicitacoes_coordenacao'
        )

    if request.method == 'POST':

        form = AvaliacaoSolicitacaoForm(
            request.POST
        )

        acao = request.POST.get(
            'acao'
        )

        # Protege contra valores enviados
        # manualmente pelo navegador.
        if acao not in [
            'aprovar',
            'recusar',
        ]:

            messages.error(
                request,
                'Ação de avaliação inválida.'
            )

        # Uma solicitação sem composição pode ser
        # recusada, mas não pode ser aprovada.
        elif (
            acao == 'aprovar'
            and composicao is None
        ):

            messages.error(
                request,
                'Não é possível aprovar: '
                'a composição da banca '
                'não foi encontrada.'
            )

        elif form.is_valid():

            # A revalidação é necessária apenas
            # para a aprovação.
            #
            # A recusa não precisa de sala,
            # disponibilidade ou professores livres.
            if acao == 'aprovar':

                formulario_revalidacao = (
                    criar_formulario_revalidacao(
                        solicitacao,
                        composicao
                    )
                )

                if (
                    not formulario_revalidacao.is_valid()
                ):

                    messages.error(
                        request,
                        'A solicitação não pode mais '
                        'ser aprovada com os dados atuais. '
                        'Corrija-a antes de continuar.'
                    )

                    # Mostra os motivos encontrados,
                    # como sala indisponível, choque de
                    # docente ou horário inválido.
                    for erros in (
                        formulario_revalidacao
                        .errors
                        .values()
                    ):

                        for erro in erros:

                            messages.error(
                                request,
                                erro
                            )

                    return redirect(
                        'editar_solicitacao_coordenacao',
                        solicitacao_id=solicitacao.id
                    )

            # Só chega à transação quando:
            #
            # 1. A recusa está válida; ou
            # 2. A aprovação passou por toda
            #    a revalidação.
            with transaction.atomic():

                solicitacao_bloqueada = (
                    get_object_or_404(
                        SolicitacaoAgendamento.objects
                        .select_for_update()
                        .select_related(
                            'projeto_tcc'
                        ),
                        pk=solicitacao_id
                    )
                )

                # Proteção contra clique duplo ou
                # duas decisões simultâneas.
                if (
                    solicitacao_bloqueada.status
                    != 'EM_ANÁLISE'
                ):

                    messages.warning(
                        request,
                        'Esta solicitação já foi '
                        'avaliada ou expirou.'
                    )

                    return redirect(
                        'solicitacoes_coordenacao'
                    )

                motivo = form.cleaned_data[
                    'motivo_decisao'
                ]

                solicitacao_bloqueada.motivo_decisao = (
                    motivo
                )

                solicitacao_bloqueada.data_decisao = (
                    timezone.now()
                )

                solicitacao_bloqueada.decidida_por = (
                    request.user
                )

                projeto = (
                    solicitacao_bloqueada.projeto_tcc
                )

                if acao == 'aprovar':

                    solicitacao_bloqueada.status = (
                        'APROVADA'
                    )

                    projeto.status = 'APROVADO'

                    # A BancaTCC oficial só é criada
                    # depois de todas as validações.
                    BancaTCC.objects.create(
                        projeto_tcc=projeto,
                        espaco=(
                            solicitacao_bloqueada.espaco
                        ),
                        data_horario_inicio=(
                            solicitacao_bloqueada
                            .opcao_data_inicio
                        ),
                        data_horario_fim=(
                            solicitacao_bloqueada
                            .opcao_data_fim
                        ),
                    )

                    mensagem_final = (
                        f'A banca "{projeto.titulo}" '
                        'foi aprovada com sucesso.'
                    )

                else:

                    solicitacao_bloqueada.status = (
                        'RECUSADA'
                    )

                    projeto.status = 'RECUSADA'

                    mensagem_final = (
                        f'A banca "{projeto.titulo}" '
                        'foi recusada.'
                    )

                projeto.save(
                    update_fields=[
                        'status',
                    ]
                )

                solicitacao_bloqueada.save(
                    update_fields=[
                        'status',
                        'motivo_decisao',
                        'data_decisao',
                        'decidida_por',
                    ]
                )

            if acao == 'aprovar':

                messages.success(
                    request,
                    mensagem_final
                )

            else:

                messages.warning(
                    request,
                    mensagem_final
                )

            return redirect(
                'dashboard'
            )

    else:

        form = AvaliacaoSolicitacaoForm()

    contexto = {
        'solicitacao': solicitacao,
        'composicao': composicao,
        'form': form,
    }

    return render(
        request,
        'avaliar_solicitacao.html',
        contexto
    )

@login_required(login_url='login')
def meus_tccs(request):
    projetos = ProjetoTCC.objects.select_related('discente').all()
    contexto = {
        'projetos': projetos
    }
    return render(request, 'meus_tccs.html', contexto)

@login_required(login_url='login')
def pesquisar(request):

    expirar_solicitacoes_vencidas()

    termo = request.GET.get('q', '').strip()
    resultados = SolicitacaoAgendamento.objects.none()

    if termo:
        resultados = SolicitacaoAgendamento.objects.select_related(
            'projeto_tcc',
            'projeto_tcc__discente',
            'espaco'
        ).filter(
            Q(projeto_tcc__titulo__icontains=termo) |
            Q(projeto_tcc__discente__nome__icontains=termo)
        ).order_by('-id')

    contexto = {
        'termo': termo,
        'resultados': resultados,
    }

    return render(request, 'pesquisa.html', contexto)

@login_required(login_url='login')
def documentos(request):

    eh_coordenacao = (
        request.user.is_superuser or
        pUsuario.objects.filter(
            usuario=request.user,
            perfil='COORDENACAO'
        ).exists()
    )

    if request.method == 'POST':

        if not eh_coordenacao:
            messages.error(
                request,
                'Apenas a coordenação pode enviar documentos.'
            )
            return redirect('documentos')

        form = ModeloDocumentoForm(
            request.POST,
            request.FILES
        )

        if form.is_valid():
            modelo = form.save(commit=False)
            modelo.enviado_por = request.user
            modelo.save()

            messages.success(
                request,
                'Modelo de documento enviado com sucesso.'
            )

            return redirect('documentos')

    else:
        form = ModeloDocumentoForm()

    modelos = ModeloDocumento.objects.all().order_by('-data_upload')

    # Bancas aprovadas que podem ser usadas na geração de documentos
    consulta_solicitacoes = (
    SolicitacaoAgendamento.objects
    .select_related(
        'projeto_tcc',
        'projeto_tcc__discente',
        'espaco',
        'usuario_solicitante',
        'usuario_solicitante__usuario',
    )
    .filter(
        status='APROVADA'
    )
)

    if not eh_coordenacao:

        perfil_logado = (
            pUsuario.objects
            .filter(
                usuario=request.user,
                perfil='DOCENTE'
            )
            .first()
        )

        if perfil_logado is None:

            consulta_solicitacoes = (
                SolicitacaoAgendamento.objects.none()
            )

        else:

            consulta_solicitacoes = (
                consulta_solicitacoes
                .filter(
                    Q(
                        usuario_solicitante=(
                            perfil_logado
                        )
                    )
                    | Q(
                        composicao_banca__orientador=(
                            perfil_logado
                        )
                    )
                    | Q(
                        composicao_banca__coorientador=(
                            perfil_logado
                        )
                    )
                    | Q(
                        composicao_banca__avaliador_interno=(
                            perfil_logado
                        )
                    )
                    | Q(
                        composicao_banca__segundo_avaliador_interno=(
                            perfil_logado
                        )
                    )
                )
                .distinct()
            )

    solicitacoes_aprovadas = (
        consulta_solicitacoes.order_by(
            '-opcao_data_inicio'
        )
    )

    contexto = {
        'form': form,
        'modelos': modelos,
        'eh_coordenacao': eh_coordenacao,
        'solicitacoes_aprovadas': solicitacoes_aprovadas,
    }

    return render(
        request,
        'documentos.html',
        contexto
    )

@login_required(login_url='login')
def baixar_documento(request, modelo_id):

    # Procura o documento pelo ID ou retorna erro 404
    modelo = get_object_or_404(ModeloDocumento, id=modelo_id)

    # Somente usuários internos do sistema podem baixar
    usuario_permitido = (
        request.user.is_superuser or
        pUsuario.objects.filter(
            usuario=request.user,
            perfil__in=['DOCENTE', 'COORDENACAO']
        ).exists()
    )

    if not usuario_permitido:
        messages.error(
            request,
            'Você não possui permissão para baixar este documento.'
        )
        return redirect('dashboard')

    # Nome original do arquivo, sem o caminho media/documentos/modelos/
    nome_arquivo = Path(modelo.arquivo.name).name

    return FileResponse(
        modelo.arquivo.open('rb'),
        as_attachment=True,
        filename=nome_arquivo
    )

@login_required(login_url='login')
def _nome_docente_documento(perfil):

    if perfil is None:
        return ''

    nome_completo = (
        perfil.usuario.get_full_name().strip()
    )

    return (
        nome_completo
        or perfil.usuario.username
    )


@usuario_interno_required
def gerar_pdf_banca(
    request,
    solicitacao_id
):

    solicitacao = get_object_or_404(
        SolicitacaoAgendamento.objects
        .select_related(
            'projeto_tcc',
            'projeto_tcc__discente',
            'espaco',
            'usuario_solicitante',
            'usuario_solicitante__usuario',
        ),
        id=solicitacao_id,
        status='APROVADA'
    )

    composicao = (
        ComposicaoBanca.objects
        .select_related(
            'orientador__usuario',
            'coorientador__usuario',
            'avaliador_interno__usuario',
            'segundo_avaliador_interno__usuario',
        )
        .filter(
            solicitacao=solicitacao
        )
        .first()
    )

    if composicao is None:

        messages.error(
            request,
            'Não foi encontrada uma composição '
            'para esta solicitação.'
        )

        return redirect('documentos')

    # A Coordenação pode gerar qualquer minuta.
    usuario_permitido = (
        usuario_e_coordenacao(
            request.user
        )
    )

    # Docentes só podem gerar documentos de bancas
    # das quais participam ou que solicitaram.
    if not usuario_permitido:

        perfil_logado = (
            pUsuario.objects
            .filter(
                usuario=request.user,
                perfil='DOCENTE'
            )
            .first()
        )

        membros_internos = {
            membro_id
            for membro_id in [
                composicao.orientador_id,
                composicao.coorientador_id,
                composicao.avaliador_interno_id,
                (
                    composicao
                    .segundo_avaliador_interno_id
                ),
            ]
            if membro_id is not None
        }

        usuario_permitido = (
            perfil_logado is not None
            and (
                solicitacao.usuario_solicitante_id
                == perfil_logado.id
                or perfil_logado.id
                in membros_internos
            )
        )

    if not usuario_permitido:

        messages.error(
            request,
            'Você não possui permissão para '
            'gerar este documento.'
        )

        return redirect('documentos')

    contexto = {
        'discente': (
            solicitacao.projeto_tcc.discente.nome
        ),

        'titulo_tcc': (
            solicitacao.projeto_tcc.titulo
        ),

        'data_defesa': (
            solicitacao.opcao_data_inicio
        ),

        'orientador': (
            _nome_docente_documento(
                composicao.orientador
            )
        ),

        'coorientador': (
            _nome_docente_documento(
                composicao.coorientador
            )
        ),

        'avaliador_interno': (
            _nome_docente_documento(
                composicao.avaliador_interno
            )
        ),

        'segundo_avaliador_interno': (
            _nome_docente_documento(
                composicao
                .segundo_avaliador_interno
            )
        ),

        'avaliador_externo': (
            composicao.nome_avaliador_externo
            or ''
        ),

        'instituicao_externa': (
            composicao
            .instituicao_avaliador_externo
            or ''
        ),
    }

    template = get_template(
        'pdf/dados_banca_aprovada.html'
    )

    html = template.render(
        contexto
    )

    response = HttpResponse(
        content_type='application/pdf'
    )

    nome_arquivo = (
        f'minuta_declaracao_banca_'
        f'{solicitacao.id}.pdf'
    )

    response['Content-Disposition'] = (
        f'attachment; filename="{nome_arquivo}"'
    )

    resultado = pisa.CreatePDF(
        html,
        dest=response,
        encoding='UTF-8'
    )

    if resultado.err:

        return HttpResponse(
            'Erro ao gerar a minuta em PDF.',
            status=500
        )

    return response

@usuario_interno_required
def gerar_pdf_banca(request, solicitacao_id):

    # A minuta somente pode ser gerada para uma
    # solicitação que já tenha sido aprovada.
    solicitacao = get_object_or_404(
        SolicitacaoAgendamento.objects.select_related(
            'projeto_tcc',
            'projeto_tcc__discente',
            'espaco',
        ),
        id=solicitacao_id,
        status='APROVADA',
    )

    # Cada composição pertence à sua solicitação específica.
    # Não buscamos somente pelo projeto porque o mesmo projeto
    # pode possuir registros históricos diferentes.
    composicao = (
        ComposicaoBanca.objects
        .select_related(
            'orientador__usuario',
            'coorientador__usuario',
            'avaliador_interno__usuario',
            'segundo_avaliador_interno__usuario',
        )
        .filter(
            solicitacao=solicitacao
        )
        .first()
    )

    # Impede a geração de uma minuta incompleta.
    if not composicao:

        messages.error(
            request,
            (
                'Não foi encontrada uma composição de banca '
                'vinculada a esta solicitação.'
            )
        )

        return redirect('documentos')

    # A Coordenação pode gerar qualquer minuta.
    # Docentes só podem gerar minutas das bancas
    # das quais participam oficialmente.
    if not usuario_e_coordenacao(request.user):

        perfil_logado = pUsuario.objects.filter(
            usuario=request.user,
            perfil='DOCENTE',
        ).first()

        participantes_ids = {
            composicao.orientador_id,
            composicao.coorientador_id,
            composicao.avaliador_interno_id,
            composicao.segundo_avaliador_interno_id,
        }

        # Coorientador e segundo avaliador são opcionais,
        # portanto seus valores podem ser None.
        participantes_ids.discard(None)

        if (
            perfil_logado is None
            or perfil_logado.id not in participantes_ids
        ):

            messages.error(
                request,
                (
                    'Você não participa desta banca e não '
                    'pode gerar a minuta.'
                )
            )

            return redirect('documentos')

    # Retorna o nome completo do docente.
    # Caso ele não tenha nome completo cadastrado,
    # utiliza seu username.
    def nome_docente(perfil):

        if perfil is None:
            return ''

        return (
            perfil.usuario.get_full_name()
            or perfil.usuario.username
        )

    nome_orientador = nome_docente(
        composicao.orientador
    )

    nome_coorientador = nome_docente(
        composicao.coorientador
    )

    nome_avaliador_interno = nome_docente(
        composicao.avaliador_interno
    )

    nome_segundo_avaliador = nome_docente(
        composicao.segundo_avaliador_interno
    )

    contexto = {
        # Objetos completos, caso o template precise
        # acessar algum atributo diretamente.
        'solicitacao': solicitacao,
        'composicao': composicao,

        # Dados principais da declaração.
        'discente': (
            solicitacao.projeto_tcc.discente.nome
        ),
        'titulo_tcc': (
            solicitacao.projeto_tcc.titulo
        ),

        # Composição da banca.
        'orientador': nome_orientador,
        'coorientador': nome_coorientador,
        'avaliador_interno': (
            nome_avaliador_interno
        ),
        'segundo_avaliador_interno': (
            nome_segundo_avaliador
        ),
        'avaliador_externo': (
            composicao.nome_avaliador_externo
        ),
        'instituicao_externa': (
            composicao.instituicao_avaliador_externo
        ),

        # Dados do agendamento.
        'espaco': solicitacao.espaco.nome,
        'data_inicio': (
            solicitacao.opcao_data_inicio
        ),
        'data_fim': solicitacao.opcao_data_fim,
        'data_defesa': (
            solicitacao.opcao_data_inicio
        ),
    }

    # Este é o template institucional que substituiu
    # o antigo PDF técnico de teste.
    template = get_template(
        'pdf/dados_banca_aprovada.html'
    )

    html = template.render(
        contexto
    )

    response = HttpResponse(
        content_type='application/pdf'
    )

    response['Content-Disposition'] = (
        'attachment; '
        f'filename="minuta_declaracao_banca_'
        f'{solicitacao.id}.pdf"'
    )

    resultado = pisa.CreatePDF(
        html,
        dest=response,
        encoding='UTF-8',
    )

    if resultado.err:

        return HttpResponse(
            'Erro ao gerar a minuta em PDF.',
            status=500,
        )

    return response

@coordenacao_required
def gerenciar_espacos(request):

    # Prefixos impedem conflito entre os dois formulários.
    form_espaco = EspacoFisicoForm(
        prefix='espaco'
    )

    form_disponibilidade = DisponibilidadeEspacoForm(
        prefix='disponibilidade'
    )

    if request.method == 'POST':

        tipo_formulario = request.POST.get(
            'tipo_formulario'
        )

        # Cadastro de uma nova sala
        if tipo_formulario == 'espaco':

            form_espaco = EspacoFisicoForm(
                request.POST,
                prefix='espaco'
            )

            if form_espaco.is_valid():

                form_espaco.save()

                messages.success(
                    request,
                    'Sala ou laboratório cadastrado com sucesso.'
                )

                return redirect(
                    'gerenciar_espacos'
                )

            for erros in form_espaco.errors.values():
                for erro in erros:
                    messages.error(
                        request,
                        erro
                    )

        # Cadastro de uma disponibilidade
        elif tipo_formulario == 'disponibilidade':

            form_disponibilidade = (
                DisponibilidadeEspacoForm(
                    request.POST,
                    prefix='disponibilidade'
                )
            )

            if form_disponibilidade.is_valid():

                disponibilidade = (
                    form_disponibilidade.save(
                        commit=False
                    )
                )

                disponibilidade.criada_por = (
                    request.user
                )

                disponibilidade.save()

                messages.success(
                    request,
                    'Disponibilidade cadastrada com sucesso.'
                )

                return redirect(
                    'gerenciar_espacos'
                )

            for erros in (
                form_disponibilidade.errors.values()
            ):
                for erro in erros:
                    messages.error(
                        request,
                        erro
                    )

        elif tipo_formulario == 'excluir_disponibilidade':

            disponibilidade_id = request.POST.get(
                'disponibilidade_id'
            )

            if not disponibilidade_id:

                messages.error(
                    request,
                    'A disponibilidade não foi informada.'
                )

                return redirect(
                    'gerenciar_espacos'
                )

            disponibilidade = get_object_or_404(
                DisponibilidadeEspaco.objects
                .select_related('espaco'),
                pk=disponibilidade_id
            )

            if _disponibilidade_possui_registro_vinculado(
                disponibilidade
            ):

                messages.error(
                    request,
                    'Esta disponibilidade possui uma solicitação '
                    'ou banca vinculada e não pode ser excluída. '
                    'Utilize a opção de desativar para preservar '
                    'o histórico.'
                )

                return redirect(
                    'gerenciar_espacos'
                )

            nome_espaco = disponibilidade.espaco.nome

            disponibilidade.delete()

            messages.success(
                request,
                f'A disponibilidade de "{nome_espaco}" foi '
                'excluída permanentemente.'
            )

            return redirect(
                'gerenciar_espacos'
            )

        else:
            messages.error(
                request,
                'Formulário enviado de maneira inválida.'
            )

    espacos = EspacoFisico.objects.all()

    disponibilidades_queryset = (
        DisponibilidadeEspaco.objects
        .select_related(
            'espaco',
            'criada_por'
        )
        .order_by(
            '-ativo',
            'data_hora_inicio'
        )
    )

    paginador = Paginator(
        disponibilidades_queryset,
        10
    )

    disponibilidades = paginador.get_page(
        request.GET.get('pagina')
    )

    contexto = {
        'form_espaco': form_espaco,
        'form_disponibilidade': form_disponibilidade,
        'espacos': espacos,
        'disponibilidades': disponibilidades,
    }

    return render(
        request,
        'gerenciar_espacos.html',
        contexto
    )

def _disponibilidade_possui_compromisso(disponibilidade):
    """
    Verifica se existem solicitações ou bancas futuras
    que utilizam o período da disponibilidade.
    """

    agora = timezone.now()

    solicitacao_existente = (
        SolicitacaoAgendamento.objects
        .filter(
            espaco=disponibilidade.espaco,
            status__in=[
                'EM_ANÁLISE',
                'APROVADA',
            ],
            opcao_data_inicio__lt=(
                disponibilidade.data_hora_fim
            ),
            opcao_data_fim__gt=(
                disponibilidade.data_hora_inicio
            ),
            opcao_data_fim__gte=agora,
        )
        .exists()
    )

    banca_existente = (
        BancaTCC.objects
        .filter(
            espaco=disponibilidade.espaco,
            data_horario_inicio__lt=(
                disponibilidade.data_hora_fim
            ),
            data_horario_fim__gt=(
                disponibilidade.data_hora_inicio
            ),
            data_horario_fim__gte=agora,
        )
        .exists()
    )

    return (
        solicitacao_existente
        or banca_existente
    )

def _disponibilidade_possui_registro_vinculado(disponibilidade):
    """
    Verifica se a disponibilidade possui qualquer
    solicitação ou banca no mesmo espaço e período.

    Diferentemente da verificação de compromisso futuro,
    esta função também considera registros antigos e
    solicitações recusadas, protegendo o histórico.
    """

    possui_solicitacao = (
        SolicitacaoAgendamento.objects
        .filter(
            espaco=disponibilidade.espaco,
            opcao_data_inicio__lt=(
                disponibilidade.data_hora_fim
            ),
            opcao_data_fim__gt=(
                disponibilidade.data_hora_inicio
            ),
        )
        .exists()
    )

    possui_banca = (
        BancaTCC.objects
        .filter(
            espaco=disponibilidade.espaco,
            data_horario_inicio__lt=(
                disponibilidade.data_hora_fim
            ),
            data_horario_fim__gt=(
                disponibilidade.data_hora_inicio
            ),
        )
        .exists()
    )

    return (
        possui_solicitacao
        or possui_banca
    )

@coordenacao_required
def editar_espaco(request, espaco_id):

    espaco = get_object_or_404(
        EspacoFisico,
        pk=espaco_id
    )

    if request.method == 'POST':

        form = EspacoFisicoForm(
            request.POST,
            instance=espaco
        )

        if form.is_valid():

            form.save()

            messages.success(
                request,
                'Espaço atualizado com sucesso.'
            )

            return redirect(
                'gerenciar_espacos'
            )

        for erros in form.errors.values():
            for erro in erros:
                messages.error(
                    request,
                    erro
                )

    else:
        form = EspacoFisicoForm(
            instance=espaco
        )

    contexto = {
        'titulo': 'Editar sala ou laboratório',
        'descricao': (
            'Altere o nome do espaço físico selecionado.'
        ),
        'form': form,
        'texto_botao': 'SALVAR ALTERAÇÕES',
    }

    return render(
        request,
        'editar_gerenciamento.html',
        contexto
    )


@coordenacao_required
@require_POST
def alternar_status_espaco(
    request,
    espaco_id
):

    espaco = get_object_or_404(
        EspacoFisico,
        pk=espaco_id
    )

    # Se estiver ativo, a operação tentará desativá-lo.
    if espaco.ativo:

        agora = timezone.now()

        possui_solicitacao = (
            SolicitacaoAgendamento.objects
            .filter(
                espaco=espaco,
                status__in=[
                    'EM_ANÁLISE',
                    'APROVADA',
                ],
                opcao_data_fim__gte=agora,
            )
            .exists()
        )

        possui_banca = (
            BancaTCC.objects
            .filter(
                espaco=espaco,
                data_horario_fim__gte=agora,
            )
            .exists()
        )

        if possui_solicitacao or possui_banca:

            messages.error(
                request,
                'Este espaço possui solicitações ou bancas futuras '
                'e não pode ser desativado.'
            )

            return redirect(
                'gerenciar_espacos'
            )

        espaco.ativo = False

        messages.warning(
            request,
            f'O espaço "{espaco.nome}" foi desativado.'
        )

    else:

        espaco.ativo = True

        messages.success(
            request,
            f'O espaço "{espaco.nome}" foi ativado.'
        )

    espaco.save(
        update_fields=['ativo']
    )

    return redirect(
        'gerenciar_espacos'
    )


@coordenacao_required
def editar_disponibilidade(
    request,
    disponibilidade_id
):

    disponibilidade = get_object_or_404(
        DisponibilidadeEspaco.objects
        .select_related('espaco'),
        pk=disponibilidade_id
    )

    if request.method == 'POST':

        # Não permite modificar um período já utilizado.
        if _disponibilidade_possui_compromisso(
            disponibilidade
        ):

            messages.error(
                request,
                'Esta disponibilidade possui uma solicitação '
                'ou banca futura vinculada ao período e não '
                'pode ser editada.'
            )

            return redirect(
                'gerenciar_espacos'
            )

        form = DisponibilidadeEspacoForm(
            request.POST,
            instance=disponibilidade
        )

        if form.is_valid():

            form.save()

            messages.success(
                request,
                'Disponibilidade atualizada com sucesso.'
            )

            return redirect(
                'gerenciar_espacos'
            )

        for erros in form.errors.values():
            for erro in erros:
                messages.error(
                    request,
                    erro
                )

    else:
        form = DisponibilidadeEspacoForm(
            instance=disponibilidade
        )

    contexto = {
        'titulo': 'Editar disponibilidade',
        'descricao': (
            'Altere o espaço, o período ou a observação.'
        ),
        'form': form,
        'texto_botao': 'SALVAR ALTERAÇÕES',
    }

    return render(
        request,
        'editar_gerenciamento.html',
        contexto
    )


@coordenacao_required
@require_POST
def alternar_status_disponibilidade(
    request,
    disponibilidade_id
):

    disponibilidade = get_object_or_404(
        DisponibilidadeEspaco.objects
        .select_related('espaco'),
        pk=disponibilidade_id
    )

    # Desativação
    if disponibilidade.ativo:

        if _disponibilidade_possui_compromisso(
            disponibilidade
        ):

            messages.error(
                request,
                'Esta disponibilidade possui uma solicitação '
                'ou banca futura e não pode ser desativada.'
            )

            return redirect(
                'gerenciar_espacos'
            )

        disponibilidade.ativo = False

        disponibilidade.save(
            update_fields=['ativo']
        )

        messages.warning(
            request,
            'A disponibilidade foi desativada.'
        )

    # Ativação
    else:

        if not disponibilidade.espaco.ativo:

            messages.error(
                request,
                'Não é possível ativar a disponibilidade '
                'porque o espaço está inativo.'
            )

            return redirect(
                'gerenciar_espacos'
            )

        disponibilidade.ativo = True

        # Verifica novamente possíveis choques antes de ativar.
        try:
            disponibilidade.full_clean()

        except ValidationError as erro:

            for mensagem in erro.messages:
                messages.error(
                    request,
                    mensagem
                )

            return redirect(
                'gerenciar_espacos'
            )

        disponibilidade.save(
            update_fields=['ativo']
        )

        messages.success(
            request,
            'A disponibilidade foi ativada.'
        )

    return redirect(
        'gerenciar_espacos'
    )