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
        # Puxa todos os dados preenchidos
        cleaned_data = super().clean()
        espaco = cleaned_data.get('espaco')
        data_inicio = cleaned_data.get('opcao_data_inicio')
        data_fim = cleaned_data.get('opcao_data_fim')
        
        # Puxa os professores escolhidos no form
        orientador = cleaned_data.get('orientador')
        avaliador_interno = cleaned_data.get('avaliador_interno')

        if espaco and data_inicio and data_fim:
            
            # VALIDAÇÃO 1: Impede viagem no tempo
            if data_fim <= data_inicio:
                self.add_error('opcao_data_fim', "A data e hora de término devem ser posteriores ao horário de início.")

            # Filtro base para verificar se os horários se cruzam (Início < Fim Antigo E Fim > Início Antigo)
            filtro_horario = Q(opcao_data_inicio__lt=data_fim) & Q(opcao_data_fim__gt=data_inicio)
            
            # Filtro base de bancas (ignora recusadas e ignora a própria banca se estiver sendo editada futuramente)
            agendamentos_ativos = SolicitacaoAgendamento.objects.exclude(status='RECUSADA').exclude(pk=self.instance.pk)

            # --- TRAVA 1: CHOQUE DE SALAS ---
            if agendamentos_ativos.filter(filtro_horario, espaco=espaco).exists():
                self.add_error('espaco', f"O {espaco.nome} já possui uma banca agendada ou em análise para este mesmo horário.")

            # --- TRAVA 2: CLONAGEM DE PROFESSOR ---
            if orientador and avaliador_interno and orientador == avaliador_interno:
                self.add_error('avaliador_interno', "O professor orientador não pode ser também o avaliador interno desta banca.")

            # --- TRAVA 3: CHOQUE DO ORIENTADOR ---
            if orientador:
                # Verifica se ele já está como orientador OU como avaliador em outra banca no mesmo horário
                orientador_ocupado = agendamentos_ativos.filter(filtro_horario).filter(
                    Q(projeto_tcc__composicaobanca__orientador=orientador) |
                    Q(projeto_tcc__composicaobanca__avaliador_interno=orientador)
                ).exists()
                
                if orientador_ocupado:
                    self.add_error('orientador', "Este professor já está alocado em outra banca (como orientador ou avaliador) neste mesmo horário.")

            # --- TRAVA 4: CHOQUE DO AVALIADOR INTERNO ---
            if avaliador_interno:
                # Verifica se ele já está como orientador OU como avaliador em outra banca no mesmo horário
                avaliador_ocupado = agendamentos_ativos.filter(filtro_horario).filter(
                    Q(projeto_tcc__composicaobanca__orientador=avaliador_interno) |
                    Q(projeto_tcc__composicaobanca__avaliador_interno=avaliador_interno)
                ).exists()

                if avaliador_ocupado:
                    self.add_error('avaliador_interno', "Este professor já está alocado em outra banca (como orientador ou avaliador) neste mesmo horário.")

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
