from django.shortcuts import render

# 1. Tela inicial do sistema (Dashboard com os botões principais)
def dashboard(request):
    return render(request, 'dashboard.html')

# 2. Tela onde aparecem as bancas já marcadas
def visualizar_bancas(request):
    return render(request, 'visualizar_bancas.html')

# 3. Tela do formulário para o professor pedir a banca
def solicitar_banca(request):
    return render(request, 'solicitar_banca.html')
