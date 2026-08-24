from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone
from .models import Discente,DisponibilidadeEspaco,EspacoFisico,ModeloDocumento,ProjetoTCC,SolicitacaoAgendamento,pUsuario

class CadastroDocenteForm(UserCreationForm):

    first_name = forms.CharField(
        label='Nome',
        max_length=150,
        widget=forms.TextInput(
            attrs={
                'class': 'form-input',
                'placeholder': 'Informe seu nome',
                'autocomplete': 'given-name',
            }
        )
    )

    last_name = forms.CharField(
        label='Sobrenome',
        max_length=150,
        widget=forms.TextInput(
            attrs={
                'class': 'form-input',
                'placeholder': 'Informe seu sobrenome',
                'autocomplete': 'family-name',
            }
        )
    )

    email = forms.EmailField(
        label='E-mail institucional',
        max_length=254,
        widget=forms.EmailInput(
            attrs={
                'class': 'form-input',
                'placeholder': 'nome.sobrenome@ufac.br',
                'autocomplete': 'email',
            }
        )
    )

    class Meta:
        model = User

        fields = [
            'first_name',
            'last_name',
            'email',
            'password1',
            'password2',
        ]

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.fields['password1'].label = 'Senha'

        self.fields[
            'password1'
        ].widget.attrs.update(
            {
                'class': 'form-input',
                'placeholder': 'Crie uma senha',
                'autocomplete': 'new-password',
            }
        )

        self.fields[
            'password2'
        ].label = 'Confirmação da senha'

        self.fields[
            'password2'
        ].widget.attrs.update(
            {
                'class': 'form-input',
                'placeholder': 'Digite novamente a senha',
                'autocomplete': 'new-password',
            }
        )

    def clean_first_name(self):

        nome = self.cleaned_data[
            'first_name'
        ].strip()

        if len(nome) < 2:
            raise forms.ValidationError(
                'Informe um nome válido.'
            )

        return nome

    def clean_last_name(self):

        sobrenome = self.cleaned_data[
            'last_name'
        ].strip()

        if len(sobrenome) < 2:
            raise forms.ValidationError(
                'Informe um sobrenome válido.'
            )

        return sobrenome

    def clean_email(self):

        email = (
            self.cleaned_data['email']
            .strip()
            .lower()
        )

        dominio = email.rsplit(
            '@',
            1
        )[-1]

        if dominio != 'ufac.br':
            raise forms.ValidationError(
                'Utilize um endereço institucional '
                'terminado em @ufac.br.'
            )

        cadastro_existente = (
            User.objects
            .filter(
                Q(username__iexact=email)
                | Q(email__iexact=email)
            )
            .exists()
        )

        if cadastro_existente:
            raise forms.ValidationError(
                'Já existe um cadastro utilizando '
                'este e-mail institucional.'
            )

        return email

    def save(self, commit=True):

        usuario = super().save(
            commit=False
        )

        email = self.cleaned_data[
            'email'
        ]

        usuario.username = email
        usuario.email = email

        usuario.first_name = self.cleaned_data[
            'first_name'
        ]

        usuario.last_name = self.cleaned_data[
            'last_name'
        ]

        # A conta somente será ativada depois da
        # aprovação realizada pela Coordenação.
        usuario.is_active = False

        if commit:

            usuario.save()

            pUsuario.objects.create(
                usuario=usuario,
                perfil='DOCENTE',
                status_cadastro='PENDENTE'
            )

        return usuario

class SolicitacaoBancaForm(forms.ModelForm):
    orientador = forms.ModelChoiceField(
    queryset=pUsuario.objects.filter(perfil='DOCENTE'),
    label="Professor Orientador",
    empty_label="Selecione o Orientador"
    )
    coorientador = forms.ModelChoiceField(
        queryset=pUsuario.objects.filter(
            perfil='DOCENTE'
        ),
        required=False,
        label='Professor Coorientador (Opcional)',
        empty_label='Sem coorientador'
    )
    avaliador_interno = forms.ModelChoiceField(
    queryset=pUsuario.objects.filter(perfil='DOCENTE'),
    label="Avaliador Interno (UFAC)",
    empty_label="Selecione o Avaliador"
    )
    segundo_avaliador_interno = forms.ModelChoiceField(
        queryset=pUsuario.objects.filter(
            perfil='DOCENTE'
        ),
        required=False,
        label='Segundo Avaliador Interno (Opcional)',
        empty_label='Sem segundo avaliador'
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

        docentes_ativos = (
            pUsuario.objects
            .select_related('usuario')
            .filter(
                perfil='DOCENTE',
                status_cadastro='APROVADO',
                usuario__is_active=True,
            )
            .order_by(
                'usuario__first_name',
                'usuario__last_name',
                'usuario__username',
            )
        )

        campos_docentes = [
            'orientador',
            'coorientador',
            'avaliador_interno',
            'segundo_avaliador_interno',
        ]

        for nome_campo in campos_docentes:

            self.fields[
                nome_campo
            ].queryset = docentes_ativos

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

        orientador = cleaned_data.get(
            'orientador'
        )

        coorientador = cleaned_data.get(
            'coorientador'
        )

        avaliador_interno = cleaned_data.get(
            'avaliador_interno'
        )

        segundo_avaliador_interno = cleaned_data.get(
            'segundo_avaliador_interno'
        )

        # Relação de todos os docentes internos escolhidos.
        participantes_internos = [
            (
                'orientador',
                'orientador',
                orientador
            ),
            (
                'coorientador',
                'coorientador',
                coorientador
            ),
            (
                'avaliador_interno',
                'avaliador interno',
                avaliador_interno
            ),
            (
                'segundo_avaliador_interno',
                'segundo avaliador interno',
                segundo_avaliador_interno
            ),
        ]

        # Um mesmo docente não pode ocupar duas funções
        # na mesma banca.
        funcoes_por_docente = {}

        for campo, funcao, docente in participantes_internos:

            if not docente:
                continue

            funcao_anterior = funcoes_por_docente.get(
                docente.pk
            )

            if funcao_anterior:

                self.add_error(
                    campo,
                    f'O docente escolhido como {funcao} já foi '
                    f'selecionado como {funcao_anterior}.'
                )

            else:

                funcoes_por_docente[
                    docente.pk
                ] = funcao

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
                    .filter(
                        opcao_data_fim__gt=timezone.now()
                    )
                    .exclude(
                        status__in=[
                            'RECUSADA',
                            'EXPIRADA',
                        ]
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

                # Verifica o choque de horário de todos os
                # participantes internos da nova banca.
                for (
                    campo,
                    funcao,
                    docente
                ) in participantes_internos:

                    if not docente:
                        continue

                    docente_ocupado = (
                        agendamentos_ativos
                        .filter(
                            filtro_horario
                        )
                        .filter(
                            Q(
                                composicao_banca__orientador=(
                                    docente
                                )
                            )
                            | Q(
                                composicao_banca__coorientador=(
                                    docente
                                )
                            )
                            | Q(
                                composicao_banca__avaliador_interno=(
                                    docente
                                )
                            )
                            | Q(
                                composicao_banca__segundo_avaliador_interno=(
                                    docente
                                )
                            )
                        )
                        .exists()
                    )

                    if docente_ocupado:

                        self.add_error(
                            campo,
                            'Este docente já está alocado em '
                            'outra banca neste horário e não '
                            f'pode atuar como {funcao}.'
                        )

        return cleaned_data

class EdicaoSolicitacaoCoordenacaoForm(
    SolicitacaoBancaForm
):

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # O projeto e o PDF fazem parte do envio
        # original e não podem ser substituídos
        # pela Coordenação.
        self.fields.pop(
            'projeto_tcc',
            None
        )

        self.fields.pop(
            'arquivo_tcc',
            None
        )

        # Garante que os valores atuais sejam
        # apresentados nos campos datetime-local.
        self.fields[
            'opcao_data_inicio'
        ].widget.format = '%Y-%m-%dT%H:%M'

        self.fields[
            'opcao_data_fim'
        ].widget.format = '%Y-%m-%dT%H:%M'
      
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
