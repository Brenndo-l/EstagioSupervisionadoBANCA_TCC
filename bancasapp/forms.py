from django import forms
from .models import SolicitacaoAgendamento

class SolicitacaoBancaForm(forms.ModelForm):
    class Meta:
        # 1. de qual tabela puxa os dados
        model = SolicitacaoAgendamento
        
        # 2. campos que o professor preenche
        fields = ['projeto_tcc', 'espaco', 'opcao_data_inicio', 'opcao_data_fim']
        
        # 3. fica mais bonito pro caba ler
        labels = {
            'projeto_tcc': 'Projeto de TCC (Aluno)',
            'espaco': 'Laboratório / Sala Desejada',
            'opcao_data_inicio': 'Data e Hora de Início',
            'opcao_data_fim': 'Data e Hora de Término',
        }
        
        # 4. Colocando classes CSS (dps deixo bonito) e o calendário nativo
        widgets = {
            'projeto_tcc': forms.Select(attrs={'class': 'form-input'}),
            'espaco': forms.Select(attrs={'class': 'form-input'}),
            # O type='datetime-local' calendario seboso
            'opcao_data_inicio': forms.DateTimeInput(attrs={'class': 'form-input', 'type': 'datetime-local'}),
            'opcao_data_fim': forms.DateTimeInput(attrs={'class': 'form-input', 'type': 'datetime-local'}),
        }