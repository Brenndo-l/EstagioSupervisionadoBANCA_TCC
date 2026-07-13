from django.shortcuts import render, redirect
from .forms import SolicitacaoBancaForm
from .models import pUsuario, SolicitacaoAgendamento, BancaTCC, EspacoFisico

# 1. Tela inicial do sistema (Dashboard com os botões principais)
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
def visualizar_bancas(request):
    return render(request, 'visualizar_bancas.html')

# 3. Tela do formulário para o professor pedir a banca
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
