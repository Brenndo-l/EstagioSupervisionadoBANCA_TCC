from django.db import models
from django.contrib.auth.models import User
from datetime import timedelta
from decimal import Decimal
from django.core.validators import (
    FileExtensionValidator,
    MaxValueValidator,
    MinValueValidator,
)
from django.utils import timezone
from django.core.exceptions import ValidationError

#Quem e o usuario logado - coordenação ou docente
#conectado ao sistema de login
class pUsuario(models.Model):

    Tipos_Perfil = (
        ('COORDENACAO', 'Coordenação'),
        ('DOCENTE', 'Docente'),
    )

    TITULACOES_ACADEMICAS = (
        ('PROF', 'Prof.'),
        ('PROFA', 'Profa.'),
        ('PROF_ESP', 'Prof. Esp.'),
        ('PROFA_ESP', 'Profa. Esp.'),
        ('PROF_ME', 'Prof. Me.'),
        ('PROFA_MA', 'Profa. Ma.'),
        ('PROF_DR', 'Prof. Dr.'),
        ('PROFA_DRA', 'Profa. Dra.'),
    )

    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE
    )

    perfil = models.CharField(
        max_length=15,
        choices=Tipos_Perfil
    )

    titulacao = models.CharField(
        max_length=12,
        choices=TITULACOES_ACADEMICAS,
        blank=True,
        default='',
        verbose_name='Titulação acadêmica'
    )

    data_cadastro = models.DateTimeField(
        default=timezone.now,
        editable=False
    )

    data_confirmacao_email = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        verbose_name='Data de confirmação do e-mail'
    )

    @property
    def nome_para_documento(self):

        nome = (
            self.usuario.get_full_name().strip()
            or self.usuario.username
        )

        if not self.titulacao:
            return nome

        return (
            f'{self.get_titulacao_display()} '
            f'{nome}'
        )

    def __str__(self):

        nome_exibicao = (
            self.usuario.get_full_name().strip()
            or self.usuario.username
        )

        return (
            f'{nome_exibicao} '
            f'({self.get_perfil_display()})'
        )

# Salas e laboratórios que podem receber bancas
class EspacoFisico(models.Model):

    nome = models.CharField(
        max_length=255
    )

    ativo = models.BooleanField(
        default=True
    )

    class Meta:
        ordering = ['nome']
        verbose_name = 'Espaço físico'
        verbose_name_plural = 'Espaços físicos'

    def __str__(self):
        return self.nome

# Períodos em que uma sala ou laboratório está disponível
class DisponibilidadeEspaco(models.Model):

    espaco = models.ForeignKey(
        EspacoFisico,
        on_delete=models.CASCADE,
        related_name='disponibilidades'
    )

    data_hora_inicio = models.DateTimeField(
        verbose_name='Data e hora de início'
    )

    data_hora_fim = models.DateTimeField(
        verbose_name='Data e hora de término'
    )

    ativo = models.BooleanField(
        default=True
    )

    observacao = models.CharField(
        max_length=255,
        blank=True
    )

    criada_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='disponibilidades_criadas',
        editable=False
    )

    data_cadastro = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = [
            'data_hora_inicio',
            'espaco__nome',
        ]

        verbose_name = 'Disponibilidade de espaço'
        verbose_name_plural = 'Disponibilidades de espaços'

        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    data_hora_fim__gt=models.F(
                        'data_hora_inicio'
                    )
                ),
                name='disponibilidade_fim_apos_inicio'
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    'espaco',
                    'data_hora_inicio',
                    'data_hora_fim',
                ],
                name='disp_espaco_periodo_idx'
            ),
        ]

    def clean(self):

        super().clean()

        erros = {}

        if (
            self.data_hora_inicio
            and self.data_hora_fim
            and self.data_hora_fim <= self.data_hora_inicio
        ):
            erros['data_hora_fim'] = (
                'O término deve ser posterior ao início.'
            )

        # Uma sala não pode possuir duas disponibilidades
        # ativas que se cruzem.
        if (
            self.ativo
            and self.espaco_id
            and self.data_hora_inicio
            and self.data_hora_fim
            and self.data_hora_fim > self.data_hora_inicio
        ):

            conflitos = (
                DisponibilidadeEspaco.objects
                .filter(
                    espaco_id=self.espaco_id,
                    ativo=True,
                    data_hora_inicio__lt=self.data_hora_fim,
                    data_hora_fim__gt=self.data_hora_inicio,
                )
                .exclude(
                    pk=self.pk
                )
            )

            if conflitos.exists():
                erros['__all__'] = (
                    'Já existe uma disponibilidade ativa para '
                    'este espaço que coincide com o período informado.'
                )

        if erros:
            raise ValidationError(erros)

    def __str__(self):
        return (
            f'{self.espaco.nome} — '
            f'{self.data_hora_inicio:%d/%m/%Y %H:%M} até '
            f'{self.data_hora_fim:%d/%m/%Y %H:%M}'
        )

#Dados dos alunos que defendem a banca
class Discente(models.Model):
    nome = models.CharField(max_length=255)
    matricula = models.CharField(max_length=11, unique=True)
    def __str__(self):
        return self.nome

#Propria banca da o status atual 
class ProjetoTCC(models.Model):
    STATUS_TIPO = (
        ('EM_ANÁLISE', 'Em Análise'),
        ('APROVADO', 'Aprovado'),
        ('RECUSADA', 'Recusada'),
    )
    titulo = models.CharField(max_length=255)
    resumo = models.TextField()
    semestre_letivo = models.CharField(max_length=6)
    discente = models.ForeignKey(Discente, on_delete=models.CASCADE)
    status = models.CharField(max_length=15, choices=STATUS_TIPO, default='EM_ANÁLISE')
    def __str__(self):
        return self.titulo

#Define a banca e decide a sala, dia e horario.
class BancaTCC(models.Model):

    NOTA_MINIMA_APROVACAO = Decimal('8.00')

    STATUS_BANCA = (
        ('AGENDADA', 'Agendada'),
        ('AGUARDANDO_NOTA', 'Aguardando nota'),
        ('FINALIZADA', 'Finalizada'),
    )

    solicitacao = models.OneToOneField(
        'SolicitacaoAgendamento',
        on_delete=models.CASCADE,
        related_name='banca_tcc',
        null=True,
        blank=True,
        verbose_name='Solicitação aprovada'
    )

    projeto_tcc = models.ForeignKey(
        ProjetoTCC,
        on_delete=models.CASCADE
    )

    espaco = models.ForeignKey(
        EspacoFisico,
        on_delete=models.RESTRICT
    )

    data_horario_inicio = models.DateTimeField()

    data_horario_fim = models.DateTimeField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_BANCA,
        default='AGENDADA'
    )

    nota = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal('0.00')),
            MaxValueValidator(Decimal('10.00')),
        ]
    )

    nota_registrada_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notas_de_bancas_registradas',
        editable=False
    )

    data_registro_nota = models.DateTimeField(
        null=True,
        blank=True,
        editable=False
    )

    @property
    def data_limite_versao_final(self):

        inicio_local = timezone.localtime(
            self.data_horario_inicio
        )

        return (
            inicio_local.date()
            + timedelta(days=30)
        )

    @property
    def resultado_final(self):

        if self.nota is None:
            return ''

        if Decimal(self.nota) >= self.NOTA_MINIMA_APROVACAO:
            return 'APROVAÇÃO'

        return 'REPROVAÇÃO'

    def __str__(self):

        return (
            f'Banca: {self.projeto_tcc.titulo}'
        )

#Diz quem esta na banca orientador ou avaliador
class MembroBanca(models.Model):
    PAPEIS = (
        ('ORIENTADOR', 'Orientador'),
        ('AVALIADOR', 'Avaliador'),
    )
    banca = models.ForeignKey(BancaTCC, on_delete=models.CASCADE)
    docente = models.ForeignKey(pUsuario, on_delete=models.CASCADE)
    papel = models.CharField(max_length=15, choices=PAPEIS)

# Solicitação enviada pelo docente e avaliada pela coordenação
class SolicitacaoAgendamento(models.Model):

    STATUS_SOLICITACAO = (
        ('EM_ANÁLISE', 'Em Análise'),
        ('APROVADA', 'Aprovada'),
        ('RECUSADA', 'Recusada'),
        ('EXPIRADA', 'Expirada'),
    )

    usuario_solicitante = models.ForeignKey(
        pUsuario,
        on_delete=models.CASCADE,
        related_name='solicitacoes_enviadas'
    )

    projeto_tcc = models.ForeignKey(
        ProjetoTCC,
        on_delete=models.CASCADE
    )

    espaco = models.ForeignKey(
        EspacoFisico,
        on_delete=models.PROTECT
    )

    opcao_data_inicio = models.DateTimeField()

    opcao_data_fim = models.DateTimeField()

    arquivo_tcc = models.FileField(
        upload_to='tcc/solicitacoes/%Y/%m/',
        validators=[
            FileExtensionValidator(
                allowed_extensions=['pdf']
            )
        ],
        blank=True,
        verbose_name='Arquivo do TCC'
    )        

    status = models.CharField(
        max_length=15,
        choices=STATUS_SOLICITACAO,
        default='EM_ANÁLISE'
    )

    # Data em que o docente enviou a solicitação
    data_solicitacao = models.DateTimeField(
        default=timezone.now,
        editable=False
    )

    # Preenchida somente quando a coordenação avaliar
    data_decisao = models.DateTimeField(
        null=True,
        blank=True,
        editable=False
    )

    # Usuário da coordenação que aprovou ou recusou
    decidida_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='solicitacoes_decididas',
        editable=False
    )

    # Justificativa informada pela coordenação
    motivo_decisao = models.TextField(
        blank=True
    )

    def __str__(self):
        return (
            f'{self.projeto_tcc.titulo} - '
            f'{self.get_status_display()}'
        )

#Documentos que a coordenação gera tanto para o docente como para o SEI
class DocumentoEmitido(models.Model):
    banca = models.ForeignKey(BancaTCC, on_delete=models.CASCADE)
    data_emissao = models.DateTimeField(auto_now_add=True)
    tipo_documento = models.CharField(max_length=50)

class ModeloDocumento(models.Model):
    TIPOS_DOCUMENTO = (
        ('ATA_DEFESA', 'Ata de Defesa'),
        ('FICHA_AVALIACAO', 'Ficha de Avaliação'),
        ('OUTRO', 'Outro'),
    )

    nome = models.CharField(max_length=150)

    tipo = models.CharField(
        max_length=30,
        choices=TIPOS_DOCUMENTO
    )

    arquivo = models.FileField(
        upload_to='documentos/modelos/',
        validators=[
            FileExtensionValidator(
                allowed_extensions=['pdf', 'doc', 'docx', 'odt']
            )
        ]
    )

    enviado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    data_upload = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome

# Relacionamento 1 para 1: Cada TCC tem apenas UMA banca
class ComposicaoBanca(models.Model):
    projeto_tcc = models.ForeignKey(ProjetoTCC, on_delete=models.CASCADE, verbose_name='Projeto de TCC')
    solicitacao = models.OneToOneField(SolicitacaoAgendamento,on_delete=models.CASCADE,related_name='composicao_banca',null=True,blank=True,verbose_name='Solicitação')
    orientador = models.ForeignKey(pUsuario, on_delete=models.PROTECT, related_name="bancas_orientador", verbose_name="Professor Orientador")
    coorientador = models.ForeignKey(pUsuario,on_delete=models.PROTECT,related_name='bancas_coorientador',verbose_name='Professor Coorientador',null=True,blank=True)
    avaliador_interno = models.ForeignKey(pUsuario, on_delete=models.PROTECT, related_name="bancas_avaliador_interno", verbose_name="Avaliador Interno (UFAC)")
    segundo_avaliador_interno = models.ForeignKey(pUsuario,on_delete=models.PROTECT,related_name='bancas_segundo_avaliador_interno',verbose_name='Segundo Avaliador Interno (UFAC)',null=True,blank=True)
    presidente = models.ForeignKey(pUsuario,on_delete=models.PROTECT,related_name='bancas_presididas',verbose_name='Presidente da banca',null=True,blank=True)
    nome_avaliador_externo = models.CharField(max_length=150, verbose_name="Nome do Avaliador Externo", blank=True, null=True)
    titulacao_avaliador_externo = models.CharField(max_length=12,choices=pUsuario.TITULACOES_ACADEMICAS,blank=True,default='',verbose_name='Titulação do Avaliador Externo')
    instituicao_avaliador_externo = models.CharField(max_length=100, verbose_name="Instituição Externa", blank=True, null=True)

    def __str__(self):
        return f"Banca: {self.projeto_tcc.titulo}"
