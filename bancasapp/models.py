from django.db import models
from django.contrib.auth.models import User

class pUsuario(models.Model):
    Tipos_Perfil = (
        ('COORDENACAO', 'Coordenação'),
        ('DOCENTE', 'Docente'),
    )
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    perfil = models.CharField(max_length=15, choices=Tipos_Perfil)
    def __str__(self):
        return f"{self.usuario.primeiroNome} - {self.perfil}"

class EspacoFisico(models.Model):
    nome = models.CharField(max_length=255)
    def __str__(self):
        return self.nome

class Discente(models.Model):
    nome = models.CharField(max_length=255)
    matricula = models.CharField(max_length=11, unique=True)
    def __str__(self):
        return self.nome

class ProjetoTCC(models.Model):
    STATUS_TIPO = (
        ('EM_ANÁLISE', 'Em Análise'),
        ('APROVADO', 'Aprovado'),
        ('RECUSADA', 'Recusada'),
    )
    titulo = models.CharField(max_length=255)
    resumo = models.TextField()
    semestre_letico = models.CharField(max_length=6)
    discente = models.ForeignKey(Discente, on_delete=models.CASCADE)
    status = models.CharField(max_length=15, choices=STATUS_TIPO, default='EM_ANÁLISE')
    def __str__(self):
        return self.titulo

class BancaTCC(models.Model):
    projeto_tcc = models.ForeignKey(ProjetoTCC, on_delete=models.CASCADE)
    espaco = models.ForeignKey(EspacoFisico, on_delete=models.RESTRICT)
    data_horario_inicio = models.DateTimeField()
    data_horario_fim = models.DateTimeField()
    def __str__(self):
        return f"Banca: {self.projeto_tcc.titulo}"

class MembroBanca(models.Model):
    PAPEIS = (
        ('ORIENTADOR', 'Orientador'),
        ('AVALIADOR', 'Avaliador'),
    )
    banca = models.ForeignKey(BancaTCC, on_delete=models.CASCADE)
    docente = models.ForeignKey(pUsuario, on_delete=models.CASCADE)
    papel = models.CharField(max_length=15, choices=PAPEIS)

class SolicitacaoAgendamento(models.Model):
    STATUS_SOLICITACAO = (
        ('EM_ANÁLISE', 'Em Análise'),
        ('APROVADA', 'Aprovada'),
        ('RECUSADA', 'Recusada'),
    )
    usuario_solicitante = models.ForeignKey(pUsuario, on_delete=models.CASCADE)
    projeto_tcc = models.ForeignKey(ProjetoTCC, on_delete=models.CASCADE)
    espaco = models.ForeignKey(EspacoFisico, on_delete=models.CASCADE)
    opcao_data_inicio = models.DateTimeField()
    opcao_data_fim = models.DateTimeField()
    status = models.CharField(max_length=15, choices=STATUS_SOLICITACAO, default='EM_ANÁLISE')

class DocumentoEmitido(models.Model):
    banca = models.ForeignKey(BancaTCC, on_delete=models.CASCADE)
    data_emissao = models.DateTimeField(auto_now_add=True)
    tipo_documento = models.CharField(max_length=50)