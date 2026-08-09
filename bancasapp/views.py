from django.shortcuts import render, redirect, get_object_or_404
from .forms import SolicitacaoBancaForm, DiscenteForm, ProjetoTCCForm, ModeloDocumentoForm
from .models import ProjetoTCC, pUsuario, SolicitacaoAgendamento, BancaTCC, EspacoFisico, ComposicaoBanca, ModeloDocumento
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q


# 1. Tela inicial do sistema (Dashboard com os botões principais)
@login_required(login_url='login')
def dashboard(request):
    # O Django verifica se quem está logado é o administrador (Coordenação)
    is_coordenacao = request.user.is_superuser
    
    if is_coordenacao:
        # Visão da Coordenação: Vê o total de TODOS
        total_bancas = BancaTCC.objects.count()
        total_pendentes = SolicitacaoAgendamento.objects.filter(status='EM_ANÁLISE').count()
        
        # Pega as últimas 5 solicitações para mostrar na tela inicial da coordenação
        ultimos_pedidos = SolicitacaoAgendamento.objects.filter(status='EM_ANÁLISE').order_by('-id')[:5]
    else:
        # Visão do Professor: Vê apenas os SEUS números
        try:
            perfil_logado = request.user.pusuario
            total_bancas = SolicitacaoAgendamento.objects.filter(usuario_solicitante=perfil_logado, status='APROVADA').count()
            total_pendentes = SolicitacaoAgendamento.objects.filter(usuario_solicitante=perfil_logado, status='EM_ANÁLISE').count()
        except:
            total_bancas = 0
            total_pendentes = 0
            
        ultimos_pedidos = None # Professor não precisa dessa lista no painel inicial

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
        minhas_solicitacoes = SolicitacaoAgendamento.objects.filter(usuario_solicitante=perfil_logado)
    except:
        minhas_solicitacoes = SolicitacaoAgendamento.objects.all()

    # 1. Pega o status que o usuário clicou lá na URL
    status_filtro = request.GET.get('status')
    
    # 2. Se tiver um status, filtra a tabela
    if status_filtro:
        minhas_solicitacoes = minhas_solicitacoes.filter(status=status_filtro)

    # 3. O SEGREDO: Enviar o status_filtro com o nome 'status_atual' para o HTML
    contexto = {
        'solicitacoes': minhas_solicitacoes,
        'status_atual': status_filtro 
    }
    
    return render(request, 'visualizar_bancas.html', contexto)

# 3. Tela do formulário para o professor pedir a banca
@login_required(login_url='login')
def solicitar_banca(request):
    if request.method == 'POST':
        form = SolicitacaoBancaForm(request.POST)
        if form.is_valid():
            solicitacao = form.save(commit=False)
            solicitacao.status = 'EM_ANÁLISE'
            solicitacao.usuario_solicitante = request.user.pusuario 
            solicitacao.save()
            
            ComposicaoBanca.objects.update_or_create(
                projeto_tcc=solicitacao.projeto_tcc,
                defaults={
                    'orientador': form.cleaned_data['orientador'],
                    'avaliador_interno': form.cleaned_data['avaliador_interno'],
                    'nome_avaliador_externo': form.cleaned_data['nome_avaliador_externo'],
                    'instituicao_avaliador_externo': form.cleaned_data['instituicao_avaliador_externo']
                }
            )
            messages.success(request, 'Sua solicitação e a composição da banca foram enviadas com sucesso!')
            return redirect('dashboard')
    else:
        form = SolicitacaoBancaForm()
        
    return render(request, 'solicitar_banca.html', {'form': form})

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
    projetos = ProjetoTCC.objects.all()
    
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

    # Verifica se o usuário é da coordenação
    eh_coordenacao = (
        request.user.is_superuser or
        pUsuario.objects.filter(
            usuario=request.user,
            perfil='COORDENACAO'
        ).exists()
    )

    # Upload permitido apenas para a coordenação
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

    contexto = {
        'form': form,
        'modelos': modelos,
        'eh_coordenacao': eh_coordenacao,
    }

    return render(
        request,
        'documentos.html',
        contexto
    )