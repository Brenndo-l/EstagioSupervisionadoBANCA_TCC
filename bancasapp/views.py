from django.shortcuts import render, redirect, get_object_or_404
from .forms import SolicitacaoBancaForm, DiscenteForm, ProjetoTCCForm, ModeloDocumentoForm
from .models import ProjetoTCC, pUsuario, SolicitacaoAgendamento, BancaTCC, EspacoFisico, ComposicaoBanca, ModeloDocumento
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import FileResponse, HttpResponse
from pathlib import Path
from django.template.loader import get_template
from xhtml2pdf import pisa


# 1. Tela inicial do sistema (Dashboard com os botões principais)
@login_required(login_url='login')
def dashboard(request):
    # Verifica se quem está logado é a Coordenação
    is_coordenacao = request.user.is_superuser

    if is_coordenacao:
        # Visão da Coordenação: vê os dados de todo o sistema
        total_bancas = BancaTCC.objects.count()

        total_pendentes = SolicitacaoAgendamento.objects.filter(
            status='EM_ANÁLISE'
        ).count()

        # Últimas 5 solicitações pendentes mostradas no Dashboard
        # select_related carrega os dados relacionados junto com a consulta
        ultimos_pedidos = SolicitacaoAgendamento.objects.select_related(
            'projeto_tcc',
            'projeto_tcc__discente',
            'espaco',
            'usuario_solicitante',
            'usuario_solicitante__usuario'
        ).filter(
            status='EM_ANÁLISE'
        ).order_by('-id')[:5]

    else:
        # Visão do Professor: vê apenas os próprios números
        try:
            perfil_logado = request.user.pusuario

            total_bancas = SolicitacaoAgendamento.objects.filter(
                usuario_solicitante=perfil_logado,
                status='APROVADA'
            ).count()

            total_pendentes = SolicitacaoAgendamento.objects.filter(
                usuario_solicitante=perfil_logado,
                status='EM_ANÁLISE'
            ).count()

        except:
            total_bancas = 0
            total_pendentes = 0

        # Professor não recebe a lista de solicitações pendentes da Coordenação
        ultimos_pedidos = None

    # Quantidade de salas é igual para todos
    total_salas = EspacoFisico.objects.count()

    contexto = {
        'total_bancas': total_bancas,
        'total_pendentes': total_pendentes,
        'total_salas': total_salas,
        'is_coordenacao': is_coordenacao,
        'ultimos_pedidos': ultimos_pedidos,
    }

    return render(request, 'dashboard.html', contexto)

# 2. Tela onde aparecem as bancas já marcadas
@login_required(login_url='login')
def visualizar_bancas(request):
    try:
        perfil_logado = request.user.pusuario

        minhas_solicitacoes = SolicitacaoAgendamento.objects.select_related(
            'projeto_tcc',
            'projeto_tcc__discente',
            'espaco',
            'usuario_solicitante',
            'usuario_solicitante__usuario'
        ).filter(
            usuario_solicitante=perfil_logado
        )

    except:
        minhas_solicitacoes = SolicitacaoAgendamento.objects.select_related(
            'projeto_tcc',
            'projeto_tcc__discente',
            'espaco',
            'usuario_solicitante',
            'usuario_solicitante__usuario'
        ).all()

    # Pega o status selecionado no filtro
    status_filtro = request.GET.get('status')

    # Filtra as solicitações pelo status
    if status_filtro:
        minhas_solicitacoes = minhas_solicitacoes.filter(
            status=status_filtro
        )

    contexto = {
        'solicitacoes': minhas_solicitacoes,
        'status_atual': status_filtro
    }

    return render(
        request,
        'visualizar_bancas.html',
        contexto
    )

# 3. Tela do formulário para o professor pedir a banca
@login_required(login_url='login')
def solicitar_banca(request):

    # Só docentes cadastrados podem solicitar uma banca
    perfil_logado = pUsuario.objects.filter(
        usuario=request.user,
        perfil='DOCENTE'
    ).first()

    if not perfil_logado:
        messages.error(
            request,
            'Apenas docentes cadastrados podem solicitar uma banca.'
        )
        return redirect('dashboard')

    if request.method == 'POST':
        form = SolicitacaoBancaForm(request.POST)

        if form.is_valid():

            # Salva a solicitação
            solicitacao = form.save(commit=False)

            solicitacao.status = 'EM_ANÁLISE'

            # Usa o perfil docente realmente ligado ao usuário logado
            solicitacao.usuario_solicitante = perfil_logado

            solicitacao.save()

            # Salva quem fará parte da banca
            ComposicaoBanca.objects.update_or_create(
                projeto_tcc=solicitacao.projeto_tcc,
                defaults={
                    'orientador': form.cleaned_data['orientador'],
                    'avaliador_interno': form.cleaned_data['avaliador_interno'],
                    'nome_avaliador_externo': form.cleaned_data[
                        'nome_avaliador_externo'
                    ],
                    'instituicao_avaliador_externo': form.cleaned_data[
                        'instituicao_avaliador_externo'
                    ],
                }
            )

            messages.success(
                request,
                'Solicitação de banca enviada com sucesso.'
            )

            return redirect('dashboard')
            
        else:
            # Transforma os erros de validação (como o choque de salas) em notificações no topo
            for campo, erros in form.errors.items():
                for erro in erros:
                    messages.error(request, erro)

    else:
        form = SolicitacaoBancaForm()

    return render(
        request,
        'solicitar_banca.html',
        {
            'form': form
        }
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

@login_required(login_url='login')
def avaliar_solicitacao(request, solicitacao_id, acao):
    # Trava de segurança: Se não for a coordenação tentando acessar esse link, devolve pro painel
    if not request.user.is_superuser:
        return redirect('dashboard')
    
    # Busca o pedido específico no banco de dados
    solicitacao = get_object_or_404(SolicitacaoAgendamento, id=solicitacao_id)
    if acao == 'aprovar':
        solicitacao.status = 'APROVADA'
        messages.success(request, f'Banca "{solicitacao.projeto_tcc.titulo}" APROVADA com sucesso!')
    elif acao == 'recusar':
        solicitacao.status = 'RECUSADA'
        messages.warning(request, f'Banca "{solicitacao.projeto_tcc.titulo}" RECUSADA.')
        
    solicitacao.save()
    return redirect('dashboard')

@login_required(login_url='login')
def meus_tccs(request):
    projetos = ProjetoTCC.objects.select_related('discente').all()
    contexto = {
        'projetos': projetos
    }
    return render(request, 'meus_tccs.html', contexto)

@login_required(login_url='login')
def pesquisar(request):
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
    solicitacoes_aprovadas = SolicitacaoAgendamento.objects.select_related(
        'projeto_tcc',
        'projeto_tcc__discente',
        'espaco',
        'usuario_solicitante',
        'usuario_solicitante__usuario'
    ).filter(
        status='APROVADA'
    ).order_by('-opcao_data_inicio')

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
def gerar_pdf_teste(request):
    # Carrega o HTML usado para montar o PDF
    template = get_template('pdf/pdf_teste.html')

    nome_usuario = (
        request.user.get_full_name()
        or request.user.username
    )

    contexto = {
        'usuario': nome_usuario,
    }

    html = template.render(contexto)

    # Cria a resposta que será enviada como PDF
    response = HttpResponse(
        content_type='application/pdf'
    )

    response['Content-Disposition'] = (
        'attachment; filename="sgtcc_teste_pdf.pdf"'
    )

    # Converte o HTML em PDF
    resultado = pisa.CreatePDF(
        html,
        dest=response,
        encoding='UTF-8'
    )

    if resultado.err:
        return HttpResponse(
            'Erro ao gerar o arquivo PDF.',
            status=500
        )

    return response

@login_required(login_url='login')
def gerar_pdf_banca(request, solicitacao_id):

    # Só aceita uma solicitação que esteja aprovada
    solicitacao = get_object_or_404(
        SolicitacaoAgendamento.objects.select_related(
            'projeto_tcc',
            'projeto_tcc__discente',
            'espaco'
        ),
        id=solicitacao_id,
        status='APROVADA'
    )

    # Busca a composição cadastrada para esse TCC
    composicao = ComposicaoBanca.objects.select_related(
        'orientador__usuario',
        'avaliador_interno__usuario'
    ).filter(
        projeto_tcc=solicitacao.projeto_tcc
    ).first()

    # Se a composição não existir, não gera um documento incompleto
    if not composicao:
        messages.error(
            request,
            'Não foi encontrada uma composição de banca para este TCC.'
        )
        return redirect('documentos')

    # Nome do orientador
    nome_orientador = (
        composicao.orientador.usuario.get_full_name()
        or composicao.orientador.usuario.username
    )

    # Nome do avaliador interno
    nome_avaliador_interno = (
        composicao.avaliador_interno.usuario.get_full_name()
        or composicao.avaliador_interno.usuario.username
    )

    contexto = {
        'titulo_tcc': solicitacao.projeto_tcc.titulo,
        'discente': solicitacao.projeto_tcc.discente.nome,
        'orientador': nome_orientador,
        'avaliador_interno': nome_avaliador_interno,
        'avaliador_externo': composicao.nome_avaliador_externo,
        'instituicao_externa': composicao.instituicao_avaliador_externo,
        'espaco': solicitacao.espaco.nome,
        'data_inicio': solicitacao.opcao_data_inicio,
        'data_fim': solicitacao.opcao_data_fim,
    }

    template = get_template(
        'pdf/dados_banca_aprovada.html'
    )

    html = template.render(contexto)

    response = HttpResponse(
        content_type='application/pdf'
    )

    response['Content-Disposition'] = (
        'attachment; filename="dados_banca_aprovada.pdf"'
    )

    resultado = pisa.CreatePDF(
        html,
        dest=response,
        encoding='UTF-8'
    )

    if resultado.err:
        return HttpResponse(
            'Erro ao gerar o arquivo PDF.',
            status=500
        )

    return response