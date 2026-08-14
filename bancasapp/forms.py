from django import forms
from .models import SolicitacaoAgendamento, Discente, ProjetoTCC, pUsuario, ModeloDocumento
from django.db.models import Q

class SolicitacaoBancaForm(forms.ModelForm):
    orientador = forms.ModelChoiceField(
    queryset=pUsuario.objects.filter(perfil='DOCENTE'),
    label="Professor Orientador",
    empty_label="Selecione o Orientador"
    )
    avaliador_interno = forms.ModelChoiceField(
    queryset=pUsuario.objects.filter(perfil='DOCENTE'),
    label="Avaliador Interno (UFAC)",
    empty_label="Selecione o Avaliador"
    )
    nome_avaliador_externo = forms.CharField(
        max_length=150, 
        required=False, 
        label="Nome do Avaliador Externo (Opcional)"
    )
    instituicao_avaliador_externo = forms.CharField(
        max_length=100, 
        required=False, 
        label="Instituição do Avaliador Externo (Opcional)"
    )
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

    def clean(self):
            # Puxa os dados que o professor digitou na tela
            cleaned_data = super().clean()
            espaco = cleaned_data.get('espaco')
            data_inicio = cleaned_data.get('opcao_data_inicio')
            data_fim = cleaned_data.get('opcao_data_fim')

            # Só faz a verificação se o professor preencheu todos os três campos
            if espaco and data_inicio and data_fim:
                
                # VALIDAÇÃO BÔNUS: Impede viagem no tempo (fim antes do início)
                if data_fim <= data_inicio:
                    self.add_error('opcao_data_fim', "A data e hora de término devem ser posteriores ao horário de início.")

                # ALGORITMO DE CHOQUE DE SALAS (Q Objects)
                # 1. Filtra pelo espaço escolhido
                # 2. Ignora bancas que a coordenação já recusou
                # 3. Cruza os horários: (Início Novo < Fim Antigo) E (Fim Novo > Início Antigo)
                conflitos = SolicitacaoAgendamento.objects.filter(
                    espaco=espaco
                ).exclude(
                    status='RECUSADA' 
                ).filter(
                    Q(opcao_data_inicio__lt=data_fim) & 
                    Q(opcao_data_fim__gt=data_inicio)
                )

                # Se a busca no banco retornar algum resultado, a sala está ocupada!
                if conflitos.exists():
                    self.add_error('espaco', f"O {espaco.nome} já possui uma banca agendada ou em análise para este mesmo horário.")

            return cleaned_data       

class DiscenteForm(forms.ModelForm):
    class Meta:
        model = Discente
        fields = '__all__'

class ProjetoTCCForm(forms.ModelForm):
    class Meta:
        model = ProjetoTCC
        fields = '__all__'

class ModeloDocumentoForm(forms.ModelForm):
    class Meta:
        model = ModeloDocumento

        fields = [
            'nome',
            'tipo',
            'arquivo',
        ]

        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Ex: Modelo de Ata de Defesa'
            }),

            'tipo': forms.Select(attrs={
                'class': 'form-input'
            }),

            'arquivo': forms.FileInput(attrs={
                'class': 'form-input'
            }),
        }

        labels = {
            'nome': 'Nome do documento',
            'tipo': 'Tipo do documento',
            'arquivo': 'Arquivo',
        }
