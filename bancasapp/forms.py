from django import forms
from django.conf import settings
from django.contrib.auth.forms import (
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)
from django.contrib.auth.models import User
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from .models import (
    BancaTCC,
    Discente,
    DisponibilidadeEspaco,
    EspacoFisico,
    ModeloDocumento,
    ProjetoTCC,
    SolicitacaoAgendamento,
    pUsuario,
)

def autocomplete_docente_widget(
    placeholder,
    grupo_exclusivo=False
):

    attrs = {
        'class': 'form-input js-docente-autocomplete',
        'data-placeholder': placeholder,
        'data-min-length': '2',
    }

    if grupo_exclusivo:
        attrs['data-exclusive-group'] = 'composicao-interna'

    return forms.Select(
        attrs=attrs
    )


class DocenteModelChoiceField(forms.ModelChoiceField):

    def label_from_instance(self, docente):

        nome = (
            docente.usuario.get_full_name().strip()
            or docente.usuario.username
        )

        email = (
            docente.usuario.email.strip()
            or docente.usuario.username
        )

        if nome.casefold() == email.casefold():
            return nome

        return f'{nome} — {email}'

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

        # A conta será ativada automaticamente
        # após a confirmação do e-mail.
        usuario.is_active = False

        if commit:

            usuario.save()

            pUsuario.objects.create(
                usuario=usuario,
                perfil='DOCENTE'
            )

        return usuario

class PerfilDocenteForm(forms.ModelForm):

    first_name = forms.CharField(
        label='Nome',
        max_length=150,
        widget=forms.TextInput(
            attrs={
                'class': 'form-input',
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
                'autocomplete': 'family-name',
            }
        )
    )

    class Meta:

        model = pUsuario

        fields = [
            'first_name',
            'last_name',
            'titulacao',
        ]

        labels = {
            'titulacao': 'Titulação acadêmica',
        }

        help_texts = {
            'titulacao': (
                'Campo opcional utilizado somente nos '
                'documentos institucionais da banca.'
            ),
        }

        widgets = {
            'titulacao': forms.Select(
                attrs={
                    'class': 'form-input',
                }
            ),
        }

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        if self.instance and self.instance.usuario_id:

            self.fields['first_name'].initial = (
                self.instance.usuario.first_name
            )

            self.fields['last_name'].initial = (
                self.instance.usuario.last_name
            )

    def clean_first_name(self):

        nome = ' '.join(
            self.cleaned_data['first_name'].split()
        )

        if len(nome) < 2:
            raise forms.ValidationError(
                'Informe um nome válido.'
            )

        return nome

    def clean_last_name(self):

        sobrenome = ' '.join(
            self.cleaned_data['last_name'].split()
        )

        if len(sobrenome) < 2:
            raise forms.ValidationError(
                'Informe um sobrenome válido.'
            )

        return sobrenome

    def save(self, commit=True):

        perfil = super().save(
            commit=False
        )

        perfil.usuario.first_name = (
            self.cleaned_data['first_name']
        )

        perfil.usuario.last_name = (
            self.cleaned_data['last_name']
        )

        if commit:

            perfil.usuario.save(
                update_fields=[
                    'first_name',
                    'last_name',
                ]
            )

            perfil.save(
                update_fields=[
                    'titulacao',
                ]
            )

        return perfil

class ReenvioConfirmacaoForm(forms.Form):

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

        return email

class RecuperacaoSenhaForm(PasswordResetForm):

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

    def clean_email(self):

        return (
            self.cleaned_data['email']
            .strip()
            .lower()
        )

    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None
    ):

        super().send_mail(
            subject_template_name,
            email_template_name,
            context,
            from_email,
            to_email,
            html_email_template_name
        )

        # Durante o desenvolvimento, apresenta uma cópia
        # sem quebras do link para facilitar o teste local.
        if settings.DEBUG:

            caminho_redefinicao = reverse(
                'redefinir_senha',
                kwargs={
                    'uidb64': context['uid'],
                    'token': context['token'],
                }
            )

            link_redefinicao = (
                f"{context['protocol']}://"
                f"{context['domain']}"
                f'{caminho_redefinicao}'
            )

            print()
            print('=' * 70)
            print('LINK DE RECUPERAÇÃO DE SENHA:')
            print(link_redefinicao)
            print('=' * 70)
            print()


class DefinirNovaSenhaForm(SetPasswordForm):

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.fields[
            'new_password1'
        ].label = 'Nova senha'

        self.fields[
            'new_password1'
        ].widget.attrs.update(
            {
                'class': 'form-input',
                'placeholder': 'Digite a nova senha',
                'autocomplete': 'new-password',
            }
        )

        self.fields[
            'new_password2'
        ].label = 'Confirmação da nova senha'

        self.fields[
            'new_password2'
        ].widget.attrs.update(
            {
                'class': 'form-input',
                'placeholder': 'Digite novamente a nova senha',
                'autocomplete': 'new-password',
            }
        )

class SolicitacaoBancaForm(forms.ModelForm):

    nome_discente = forms.CharField(
        label='Nome completo do discente',
        max_length=255,
        widget=forms.TextInput(
            attrs={
                'class': 'form-input',
                'placeholder': 'Informe o nome completo do discente',
                'autocomplete': 'off',
            }
        )
    )

    matricula_discente = forms.CharField(
        label='Matrícula do discente',
        max_length=11,
        widget=forms.TextInput(
            attrs={
                'class': 'form-input',
                'placeholder': 'Informe a matrícula',
                'inputmode': 'numeric',
                'autocomplete': 'off',
            }
        )
    )

    titulo_tcc = forms.CharField(
        label='Título do TCC',
        max_length=255,
        widget=forms.TextInput(
            attrs={
                'class': 'form-input',
                'placeholder': 'Informe o título completo do trabalho',
            }
        )
    )

    resumo_tcc = forms.CharField(
        label='Resumo do TCC',
        widget=forms.Textarea(
            attrs={
                'class': 'form-input',
                'rows': 6,
                'placeholder': 'Informe o resumo do trabalho',
            }
        )
    )

    semestre_letivo = forms.CharField(
        label='Semestre letivo',
        max_length=6,
        help_text='Utilize o formato ano.semestre. Exemplo: 2026.2.',
        widget=forms.TextInput(
            attrs={
                'class': 'form-input',
                'placeholder': '2026.2',
            }
        )
    )

    coorientador = DocenteModelChoiceField(
        queryset=pUsuario.objects.none(),
        required=False,
        label='Professor Coorientador (Opcional)',
        empty_label='Sem coorientador',
        widget=autocomplete_docente_widget(
            'Digite nome ou e-mail',
            grupo_exclusivo=True
        ),
        error_messages={
            'invalid_choice': (
                'Selecione um coorientador válido nas sugestões.'
            ),
        }
    )

    avaliador_interno = DocenteModelChoiceField(
        queryset=pUsuario.objects.none(),
        label='Avaliador Interno (UFAC)',
        empty_label='Selecione o avaliador',
        widget=autocomplete_docente_widget(
            'Digite nome ou e-mail',
            grupo_exclusivo=True
        ),
        error_messages={
            'required': 'Selecione o avaliador interno.',
            'invalid_choice': (
                'Selecione um avaliador interno válido nas sugestões.'
            ),
        }
    )

    segundo_avaliador_interno = DocenteModelChoiceField(
        queryset=pUsuario.objects.none(),
        required=False,
        label='Segundo Avaliador Interno (Opcional)',
        empty_label='Sem segundo avaliador',
        widget=autocomplete_docente_widget(
            'Digite nome ou e-mail',
            grupo_exclusivo=True
        ),
        error_messages={
            'invalid_choice': (
                'Selecione um segundo avaliador válido nas sugestões.'
            ),
        }
    )

    presidente = DocenteModelChoiceField(
        queryset=pUsuario.objects.none(),
        required=False,
        label='Presidente indicado (Opcional)',
        empty_label='A Coordenação selecionará',
        widget=autocomplete_docente_widget(
            'Digite nome ou e-mail'
        ),
        error_messages={
            'invalid_choice': (
                'Selecione um presidente válido nas sugestões.'
            ),
        }
    )

    nome_avaliador_externo = forms.CharField(
        max_length=150,
        required=False,
        label='Nome do Avaliador Externo (Opcional)'
    )

    titulacao_avaliador_externo = forms.ChoiceField(
        choices=(
            ('', 'Selecione a titulação'),
        ) + pUsuario.TITULACOES_ACADEMICAS,
        required=False,
        label='Titulação do Avaliador Externo (Opcional)',
        widget=forms.Select(
            attrs={
                'class': 'form-input',
            }
        )
    )

    instituicao_avaliador_externo = forms.CharField(
        max_length=100,
        required=False,
        label='Instituição do Avaliador Externo (Opcional)'
    )

    arquivo_tcc = forms.FileField(
        required=True,
        label='Arquivo do TCC em PDF',
        help_text=(
            'Envie o trabalho em formato PDF, '
            'com no máximo 25 MB.'
        ),
        widget=forms.FileInput(
            attrs={
                'class': 'form-input',
                'accept': '.pdf,application/pdf',
            }
        ),
        error_messages={
            'required': (
                'Anexe o arquivo PDF do TCC antes de '
                'enviar a solicitação.'
            ),
        }
    )

    class Meta:

        model = SolicitacaoAgendamento

        fields = [
            'espaco',
            'opcao_data_inicio',
            'opcao_data_fim',
            'arquivo_tcc',
        ]

        labels = {
            'espaco': 'Laboratório / Sala Desejada',
            'opcao_data_inicio': 'Data e Hora de Início',
            'opcao_data_fim': 'Data e Hora de Término',
        }

        widgets = {
            'espaco': forms.Select(
                attrs={
                    'class': 'form-input',
                }
            ),
            'opcao_data_inicio': forms.DateTimeInput(
                attrs={
                    'class': 'form-input',
                    'type': 'datetime-local',
                }
            ),
            'opcao_data_fim': forms.DateTimeInput(
                attrs={
                    'class': 'form-input',
                    'type': 'datetime-local',
                }
            ),
        }

    def __init__(self, *args, **kwargs):

        self.orientador = kwargs.pop(
            'orientador',
            None
        )

        super().__init__(*args, **kwargs)

        # Somente docentes com conta ativa aparecem
        # nas pesquisas da composição e da presidência.
        docentes_ativos = (
            pUsuario.objects
            .select_related('usuario')
            .filter(
                perfil='DOCENTE',
                usuario__is_active=True,
            )
            .order_by(
                'usuario__first_name',
                'usuario__last_name',
                'usuario__username',
            )
        )

        campos_docentes = [
            'coorientador',
            'avaliador_interno',
            'segundo_avaliador_interno',
            'presidente',
        ]

        for nome_campo in campos_docentes:

            self.fields[
                nome_campo
            ].queryset = docentes_ativos

        # O orientador é sempre o solicitante.
        # Ele não aparece como coorientador ou avaliador,
        # mas pode ser indicado como presidente porque
        # a presidência é apenas uma informação documental.
        if self.orientador:

            for nome_campo in [
                'coorientador',
                'avaliador_interno',
                'segundo_avaliador_interno',
            ]:

                self.fields[
                    nome_campo
                ].widget.attrs[
                    'data-excluded-values'
                ] = str(self.orientador.pk)

        # Todas as salas ativas aparecem no formulário,
        # mesmo que ainda não possuam disponibilidade.
        self.fields['espaco'].queryset = (
            EspacoFisico.objects
            .filter(
                ativo=True
            )
            .order_by('nome')
        )

    def clean_nome_discente(self):

        nome = ' '.join(
            self.cleaned_data[
                'nome_discente'
            ].split()
        )

        if len(nome) < 3:
            raise forms.ValidationError(
                'Informe o nome completo do discente.'
            )

        return nome

    def clean_matricula_discente(self):

        matricula = (
            self.cleaned_data[
                'matricula_discente'
            ].strip()
        )

        if not matricula.isdigit():
            raise forms.ValidationError(
                'A matrícula deve conter somente números.'
            )

        return matricula

    def clean_titulo_tcc(self):

        titulo = ' '.join(
            self.cleaned_data[
                'titulo_tcc'
            ].split()
        )

        if len(titulo) < 3:
            raise forms.ValidationError(
                'Informe um título válido para o TCC.'
            )

        return titulo

    def clean_resumo_tcc(self):

        resumo = (
            self.cleaned_data[
                'resumo_tcc'
            ].strip()
        )

        if len(resumo) < 10:
            raise forms.ValidationError(
                'O resumo deve possuir pelo menos 10 caracteres.'
            )

        return resumo

    def clean_semestre_letivo(self):

        semestre = (
            self.cleaned_data[
                'semestre_letivo'
            ].strip()
        )

        partes = semestre.split('.')

        formato_valido = (
            len(partes) == 2
            and len(partes[0]) == 4
            and partes[0].isdigit()
            and partes[1] in ['1', '2']
        )

        if not formato_valido:
            raise forms.ValidationError(
                'Informe o semestre no formato 2026.1 ou 2026.2.'
            )

        return semestre

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

        orientador = self.orientador

        coorientador = cleaned_data.get(
            'coorientador'
        )

        avaliador_interno = cleaned_data.get(
            'avaliador_interno'
        )

        segundo_avaliador_interno = cleaned_data.get(
            'segundo_avaliador_interno'
        )

        presidente = cleaned_data.get(
            'presidente'
        )

        matricula_discente = cleaned_data.get(
            'matricula_discente'
        )

        nome_discente = cleaned_data.get(
            'nome_discente'
        )

        if matricula_discente and nome_discente:

            discente_existente = (
                Discente.objects
                .filter(
                    matricula=matricula_discente
                )
                .first()
            )

            if (
                discente_existente
                and discente_existente.nome.casefold()
                != nome_discente.casefold()
            ):

                self.add_error(
                    'matricula_discente',
                    'Esta matrícula já pertence ao discente '
                    f'"{discente_existente.nome}".'
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

        # O presidente pode ser qualquer docente ativo.
        # Esta indicação é apenas documental: ela não torna
        # o docente integrante da banca e não participa das
        # validações de duplicidade ou choque de horário.

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

            inicio_local = (
                timezone.localtime(data_inicio)
                if timezone.is_aware(data_inicio)
                else data_inicio
            )

            fim_local = (
                timezone.localtime(data_fim)
                if timezone.is_aware(data_fim)
                else data_fim
            )

            if inicio_local.date() != fim_local.date():

                periodo_em_ordem = False

                self.add_error(
                    'opcao_data_fim',
                    'A banca deve começar e terminar no mesmo dia.'
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

        # Mantido por compatibilidade com registros antigos.
        self.fields.pop(
            'projeto_tcc',
            None
        )

        # Os dados acadêmicos pertencem ao envio original
        # e não podem ser alterados pela Coordenação.
        for nome_campo in [
            'nome_discente',
            'matricula_discente',
            'titulo_tcc',
            'resumo_tcc',
            'semestre_letivo',
        ]:

            self.fields.pop(
                nome_campo,
                None
            )

        self.fields.pop(
            'arquivo_tcc',
            None
        )

        self.fields[
            'opcao_data_inicio'
        ].widget.format = '%Y-%m-%dT%H:%M'

        self.fields[
            'opcao_data_fim'
        ].widget.format = '%Y-%m-%dT%H:%M'
      
class AvaliacaoSolicitacaoForm(forms.Form):

    presidente = DocenteModelChoiceField(
        queryset=pUsuario.objects.none(),
        required=False,
        label='Presidente da banca',
        empty_label='Selecione o presidente',
        help_text=(
            'Obrigatório para aprovação. Pode ser qualquer '
            'docente ativo; esta indicação é apenas documental.'
        ),
        widget=autocomplete_docente_widget(
            'Digite nome ou e-mail'
        ),
        error_messages={
            'invalid_choice': (
                'Selecione um presidente válido nas sugestões.'
            ),
        }
    )

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
                'Informe uma justificativa antes de '
                'concluir a avaliação.'
            ),
        }
    )

    def __init__(
        self,
        *args,
        composicao=None,
        acao=None,
        **kwargs
    ):

        self.composicao = composicao
        self.acao = acao

        super().__init__(
            *args,
            **kwargs
        )

        if (
            composicao
            and composicao.presidente_id
        ):

            self.fields[
                'presidente'
            ].initial = (
                composicao.presidente_id
            )

        self.fields['presidente'].queryset = (
            pUsuario.objects
            .select_related('usuario')
            .filter(
                perfil='DOCENTE',
                usuario__is_active=True,
            )
            .order_by(
                'usuario__first_name',
                'usuario__last_name',
                'usuario__username',
            )
        )

    def clean(self):

        cleaned_data = super().clean()

        presidente = cleaned_data.get(
            'presidente'
        )

        # Preserva a indicação feita anteriormente
        # pelo docente solicitante.
        if (
            presidente is None
            and self.composicao
            and self.composicao.presidente_id
        ):

            presidente = (
                self.composicao.presidente
            )

            cleaned_data['presidente'] = (
                presidente
            )

        if (
            self.acao == 'aprovar'
            and presidente is None
        ):

            self.add_error(
                'presidente',
                'Selecione o presidente da banca antes '
                'de aprovar a solicitação.'
            )

        return cleaned_data

class RegistroNotaBancaForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.fields['nota'].required = True

    class Meta:

        model = BancaTCC

        fields = [
            'nota',
        ]

        labels = {
            'nota': 'Nota final da banca',
        }

        help_texts = {
            'nota': (
                'Informe um valor de 0,00 a 10,00, '
                'com no máximo duas casas decimais.'
            ),
        }

        widgets = {
            'nota': forms.NumberInput(
                attrs={
                    'class': 'form-input',
                    'min': '0',
                    'max': '10',
                    'step': '0.01',
                    'placeholder': 'Ex.: 9,75',
                }
            ),
        }

        error_messages = {
            'nota': {
                'required': (
                    'Informe a nota final da banca.'
                ),
                'invalid': (
                    'Informe uma nota válida.'
                ),
                'max_digits': (
                    'A nota deve estar entre '
                    '0,00 e 10,00.'
                ),
                'max_decimal_places': (
                    'Utilize no máximo duas '
                    'casas decimais.'
                ),
            },
        }

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
