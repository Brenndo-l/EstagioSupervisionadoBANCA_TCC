from django.contrib import admin
from .models import EspacoFisico, Discente, ProjetoTCC, pUsuario, SolicitacaoAgendamento, BancaTCC, MembroBanca, ComposicaoBanca

#config tabela espaços fisicos
@admin.register(EspacoFisico)
class EspacoFisicoAdmin(admin.ModelAdmin):
    list_display = ('nome',)
    search_fields = ('nome',)

#config tablea de discentes(alunos)
@admin.register(Discente)
class DiscenteAdmin(admin.ModelAdmin):
    list_display = ('nome', 'matricula',)
    search_fields = ('nome', 'matricula',)

#Config tabela projetosTCC
@admin.register(ProjetoTCC)
class ProjetoTCCAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'discente', 'status', 'semestre_letivo')
    search_fields = ('titulo', 'discente__nome')
    list_filter = ('status', 'semestre_letivo',)

admin.site.register(pUsuario)
admin.site.register(SolicitacaoAgendamento)
admin.site.register(ComposicaoBanca)
