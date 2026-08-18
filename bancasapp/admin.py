from django.contrib import admin
from .models import EspacoFisico, Discente, ProjetoTCC, pUsuario, SolicitacaoAgendamento, BancaTCC, MembroBanca, ComposicaoBanca, DisponibilidadeEspaco

#config tabela espaços fisicos
@admin.register(EspacoFisico)
class EspacoFisicoAdmin(admin.ModelAdmin):

    list_display = (
        'nome',
        'ativo',
    )

    search_fields = (
        'nome',
    )

    list_filter = (
        'ativo',
    )

@admin.register(DisponibilidadeEspaco)
class DisponibilidadeEspacoAdmin(admin.ModelAdmin):

    list_display = (
        'espaco',
        'data_hora_inicio',
        'data_hora_fim',
        'ativo',
        'criada_por',
    )

    search_fields = (
        'espaco__nome',
        'observacao',
    )

    list_filter = (
        'ativo',
        'espaco',
    )

    autocomplete_fields = (
        'espaco',
    )

    readonly_fields = (
        'criada_por',
        'data_cadastro',
    )

    date_hierarchy = 'data_hora_inicio'

    def save_model(
        self,
        request,
        obj,
        form,
        change
    ):
        if not obj.criada_por_id:
            obj.criada_por = request.user

        super().save_model(
            request,
            obj,
            form,
            change
        )

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
