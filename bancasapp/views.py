from django.shortcuts import render, redirect
from .forms import SolicitacaoBancaForm, DiscenteForm, ProjetoTCCForm
from .models import pUsuario, SolicitacaoAgendamento, BancaTCC, EspacoFisico
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required


# 1. Tela inicial do sistema (Dashboard com os botões principais)
@login_required(login_url='login')
def dashboard(request):
    qtd_solicitacoes = SolicitacaoAgendamento.objects.filter(status='EM_ANÁLISE').count()
    qtd_bancas = BancaTCC.objects.count()
    qtd_salas = EspacoFisico.objects.count()
    
    # Empacota esses números para enviar para o HTML
    contexto = {
        'qtd_solicitacoes': qtd_solicitacoes,
        'qtd_bancas': qtd_bancas,
        'qtd_salas': qtd_salas,
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
    form = SolicitacaoBancaForm(request.POST)

    if form.is_valid():
        solicitacao = form.save(commit=False)
        solicitacao.status = 'EM_ANÁLISE'

        solicitacao.usuario_solicitante = pUsuario.objects.first()
        solicitacao.save()
        return redirect('dashboard')  # Redireciona para a página inicial após salvar
    else:
        form = SolicitacaoBancaForm()  # Se não for POST, cria um formulário vazio
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
    if(request.method == "POST"):
        email = request.POST.get("email")
        senha = request.POST.get("senha")
        print(email, senha)

        usuario = authenticate(
            username=email,
            password=senha
        )

        if usuario is not None:
            login(request, usuario)
            return redirect("/dashboard")
        else:
            return render(request, "login.html", {
                "erro": "Login ou senha incorretos."
            })

    return render(request=request, template_name= 'login.html')