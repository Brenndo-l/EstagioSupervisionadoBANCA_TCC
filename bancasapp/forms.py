from django import forms
from .models import SolicitacaoAgendamento, Discente, ProjetoTCC, pUsuario, ModeloDocumento, EspacoFisico, DisponibilidadeEspaco
from django.db.models import Q
from django.utils import timezone

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
    arquivo_tcc = forms.FileField(
        required=True,
        label='Arquivo do TCC em PDF',
        help_text='Envie o trabalho em formato PDF, com no máximo 25 MB.',
        widget=forms.FileInput(
            attrs={
                'class': 'form-input',
                'accept': '.pdf,application/pdf',
            }
        ),
        error_messages={
            'required': (
                'Anexe o arquivo PDF do TCC antes de enviar '
                'a solicitação.'
            ),
        }
    )
    class Meta:
        # 1. de qual tabela puxa os dados
        model = SolicitacaoAgendamento
        
        # 2. campos que o professor preenche
        fields = ['projeto_tcc', 'espaco', 'opcao_data_inicio', 'opcao_data_fim', 'arquivo_tcc']
        
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

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # Todas as salas ativas aparecem no formulário,
        # mesmo que ainda não possuam disponibilidade.
        self.fields['espaco'].queryset = (
            EspacoFisico.objects
            .filter(
                ativo=True
            )
            .order_by('nome')
        )
        
    def clean_arquivo_tcc(self):

        arquivo = self.cleaned_data.get(
            'arquivo_tcc'
        )

        if not arquivo:
            return arquivo

        limite_bytes = 25 * 1024 * 1024

        if arquivo.size > limite_bytes:
            raise forms.ValidationError(
                'O arquivo do TCC não pode ultrapassar 25 MB.'
            )

        # Não confia apenas na extensão informada pelo navegador.
        arquivo.seek(0)

        cabecalho = arquivo.read(5)

        arquivo.seek(0)

        if cabecalho != b'%PDF-':
            raise forms.ValidationError(
                'O arquivo enviado não parece ser um PDF válido.'
            )

        return arquivo 

    def clean(self):

        cleaned_data = super().clean()

        espaco = cleaned_data.get('espaco')
        data_inicio = cleaned_data.get(
            'opcao_data_inicio'
        )
        data_fim = cleaned_data.get(
            'opcao_data_fim'
        )

        orientador = cleaned_data.get('orientador')

        avaliador_interno = cleaned_data.get(
            'avaliador_interno'
        )

        # O orientador não pode ocupar os dois papéis.
        if (
            orientador
            and avaliador_interno
            and orientador == avaliador_interno
        ):
            self.add_error(
                'avaliador_interno',
                'O professor orientador não pode ser também '
                'o avaliador interno desta banca.'
            )

        if espaco and data_inicio and data_fim:

            periodo_em_ordem = True

            # Término precisa ser posterior ao início.
            if data_fim <= data_inicio:

                periodo_em_ordem = False

                self.add_error(
                    'opcao_data_fim',
                    'A data e hora de término devem ser '
                    'posteriores ao horário de início.'
                )

            # Agora impede realmente horários no passado.
            if data_inicio <= timezone.now():

                self.add_error(
                    'opcao_data_inicio',
                    'A data e hora de início devem estar no futuro.'
                )

            if not espaco.ativo:

                self.add_error(
                    'espaco',
                    'Este espaço está inativo e não pode '
                    'receber novas solicitações.'
                )

            if periodo_em_ordem:

                # O intervalo solicitado precisa estar totalmente
                # contido em uma disponibilidade ativa.
                disponibilidade_valida = (
                    DisponibilidadeEspaco.objects
                    .filter(
                        espaco=espaco,
                        espaco__ativo=True,
                        ativo=True,
                        data_hora_inicio__lte=data_inicio,
                        data_hora_fim__gte=data_fim,
                    )
                    .exists()
                )

                if not disponibilidade_valida:

                    self.add_error(
                        'opcao_data_inicio',
                        'O período solicitado não está dentro '
                        'de um horário disponibilizado pela '
                        'Coordenação para este espaço.'
                    )

                # Horários se cruzam quando:
                # início novo < fim existente
                # e fim novo > início existente.
                filtro_horario = (
                    Q(opcao_data_inicio__lt=data_fim)
                    & Q(opcao_data_fim__gt=data_inicio)
                )

                agendamentos_ativos = (
                    SolicitacaoAgendamento.objects
                    .exclude(
                        status='RECUSADA'
                    )
                    .exclude(
                        pk=self.instance.pk
                    )
                )

                # Choque da sala.
                if (
                    agendamentos_ativos
                    .filter(
                        filtro_horario,
                        espaco=espaco
                    )
                    .exists()
                ):
                    self.add_error(
                        'espaco',
                        f'O espaço "{espaco.nome}" já possui '
                        'uma banca agendada ou em análise '
                        'neste horário.'
                    )

                # Choque do orientador.
                if orientador:

                    orientador_ocupado = (
                        agendamentos_ativos
                        .filter(
                            filtro_horario
                        )
                        .filter(
                            Q(
                                projeto_tcc__composicaobanca__orientador=(
                                    orientador
                                )
                            )
                            | Q(
                                projeto_tcc__composicaobanca__avaliador_interno=(
                                    orientador
                                )
                            )
                        )
                        .exists()
                    )

                    if orientador_ocupado:
                        self.add_error(
                            'orientador',
                            'Este professor já está alocado '
                            'em outra banca neste horário.'
                        )

                # Choque do avaliador interno.
                if avaliador_interno:

                    avaliador_ocupado = (
                        agendamentos_ativos
                        .filter(
                            filtro_horario
                        )
                        .filter(
                            Q(
                                projeto_tcc__composicaobanca__orientador=(
                                    avaliador_interno
                                )
                            )
                            | Q(
                                projeto_tcc__composicaobanca__avaliador_interno=(
                                    avaliador_interno
                                )
                            )
                        )
                        .exists()
                    )

                    if avaliador_ocupado:
                        self.add_error(
                            'avaliador_interno',
                            'Este professor já está alocado '
                            'em outra banca neste horário.'
                        )

        return cleaned_data
      
class AvaliacaoSolicitacaoForm(forms.Form):

    motivo_decisao = forms.CharField(
        label='Justificativa da decisão',
        required=True,
        widget=forms.Textarea(
            attrs={
                'class': 'form-input',
                'rows': 5,
                'placeholder': (
                    'Informe o motivo da aprovação ou da recusa.'
                ),
            }
        ),
        error_messages={
            'required': (
                'Informe uma justificativa antes de concluir a avaliação.'
            ),
        }
    )

class EspacoFisicoForm(forms.ModelForm):

    class Meta:
        model = EspacoFisico

        fields = [
            'nome',
        ]

        widgets = {
            'nome': forms.TextInput(
                attrs={
                    'class': 'form-input',
                    'placeholder': (
                        'Ex.: Laboratório de Informática 1'
                    ),
                }
            ),
        }

        labels = {
            'nome': 'Nome da sala ou laboratório',
        }

    def clean_nome(self):

        nome = self.cleaned_data['nome'].strip()

        # Impede nomes repetidos mesmo com diferença
        # entre letras maiúsculas e minúsculas.
        nome_duplicado = (
            EspacoFisico.objects
            .filter(
                nome__iexact=nome
            )
            .exclude(
                pk=self.instance.pk
            )
            .exists()
        )

        if nome_duplicado:
            raise forms.ValidationError(
                'Já existe uma sala ou laboratório com este nome.'
            )

        return nome


class DisponibilidadeEspacoForm(forms.ModelForm):

    class Meta:
        model = DisponibilidadeEspaco

        fields = [
            'espaco',
            'data_hora_inicio',
            'data_hora_fim',
            'observacao',
        ]

        widgets = {
            'espaco': forms.Select(
                attrs={
                    'class': 'form-input',
                }
            ),

            'data_hora_inicio': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M',
                attrs={
                    'class': 'form-input',
                    'type': 'datetime-local',
                }
            ),

            'data_hora_fim': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M',
                attrs={
                    'class': 'form-input',
                    'type': 'datetime-local',
                }
            ),

            'observacao': forms.TextInput(
                attrs={
                    'class': 'form-input',
                    'placeholder': (
                        'Informação opcional sobre o período'
                    ),
                }
            ),
        }

        labels = {
            'espaco': 'Sala ou laboratório',
            'data_hora_inicio': 'Data e hora de início',
            'data_hora_fim': 'Data e hora de término',
            'observacao': 'Observação',
        }

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # Somente espaços ativos podem receber
        # novas disponibilidades.
        queryset_espacos = EspacoFisico.objects.filter(
            ativo=True
        )

        # Quando futuramente editarmos uma disponibilidade,
        # o espaço atual continuará aparecendo no formulário.
        if (
            self.instance
            and self.instance.pk
            and self.instance.espaco_id
        ):
            queryset_espacos = EspacoFisico.objects.filter(
                Q(ativo=True)
                | Q(pk=self.instance.espaco_id)
            )

        self.fields['espaco'].queryset = (
            queryset_espacos.order_by('nome')
        )

        self.fields[
            'data_hora_inicio'
        ].input_formats = [
            '%Y-%m-%dT%H:%M'
        ]

        self.fields[
            'data_hora_fim'
        ].input_formats = [
            '%Y-%m-%dT%H:%M'
        ]     

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
