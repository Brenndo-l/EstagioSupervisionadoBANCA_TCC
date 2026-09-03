from django.core.management.base import BaseCommand, CommandError
from django.db.models import F, Q

from bancasapp.models import (
    BancaTCC,
    ComposicaoBanca,
    SolicitacaoAgendamento,
)


class Command(BaseCommand):
    help = (
        'Audita relações e regras essenciais do SGTCC sem alterar dados.'
    )

    def add_arguments(self, parser):

        parser.add_argument(
            '--falhar-em-inconsistencia',
            action='store_true',
            help=(
                'Retorna erro quando alguma inconsistência for encontrada. '
                'Útil para conferências antes da apresentação ou deploy.'
            ),
        )

    def handle(self, *args, **options):

        verificacoes = self._verificacoes()
        total_inconsistencias = 0

        self.stdout.write(
            'Auditoria de integridade do SGTCC:'
        )

        for codigo, descricao, queryset in verificacoes:

            ids = list(
                queryset.values_list(
                    'pk',
                    flat=True
                )
            )

            quantidade = len(ids)
            total_inconsistencias += quantidade

            if quantidade == 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  [OK] {codigo}: {descricao}'
                    )
                )
                continue

            ids_exibidos = ', '.join(
                str(item)
                for item in ids[:20]
            )

            if quantidade > 20:
                ids_exibidos += ', ...'

            self.stdout.write(
                self.style.WARNING(
                    f'  [ATENÇÃO] {codigo}: {quantidade} registro(s)'
                )
            )
            self.stdout.write(
                f'    {descricao}'
            )
            self.stdout.write(
                f'    IDs: {ids_exibidos}'
            )

        self.stdout.write('')

        if total_inconsistencias == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    'Nenhuma inconsistência foi encontrada.'
                )
            )
            return

        mensagem = (
            f'A auditoria encontrou {total_inconsistencias} '
            'inconsistência(s). Nenhum dado foi alterado.'
        )

        if options['falhar_em_inconsistencia']:
            raise CommandError(mensagem)

        self.stdout.write(
            self.style.WARNING(mensagem)
        )

    def _verificacoes(self):

        solicitacoes_sem_composicao = (
            SolicitacaoAgendamento.objects
            .filter(composicao_banca__isnull=True)
        )

        orientadores_divergentes = (
            ComposicaoBanca.objects
            .filter(solicitacao__isnull=False)
            .exclude(
                orientador_id=F(
                    'solicitacao__usuario_solicitante_id'
                )
            )
        )

        presidentes_fora_da_composicao = (
            ComposicaoBanca.objects
            .filter(presidente__isnull=False)
            .exclude(
                Q(presidente_id=F('orientador_id'))
                | Q(presidente_id=F('coorientador_id'))
                | Q(presidente_id=F('avaliador_interno_id'))
                | Q(
                    presidente_id=F(
                        'segundo_avaliador_interno_id'
                    )
                )
            )
        )

        aprovadas_sem_presidente = (
            SolicitacaoAgendamento.objects
            .filter(
                status='APROVADA',
                composicao_banca__presidente__isnull=True,
            )
        )

        aprovadas_sem_banca = (
            SolicitacaoAgendamento.objects
            .filter(
                status='APROVADA',
                banca_tcc__isnull=True,
            )
        )

        bancas_sem_solicitacao = (
            BancaTCC.objects
            .filter(solicitacao__isnull=True)
        )

        bancas_divergentes = (
            BancaTCC.objects
            .filter(solicitacao__isnull=False)
            .exclude(
                Q(
                    projeto_tcc_id=F(
                        'solicitacao__projeto_tcc_id'
                    )
                )
                & Q(
                    espaco_id=F(
                        'solicitacao__espaco_id'
                    )
                )
                & Q(
                    data_horario_inicio=F(
                        'solicitacao__opcao_data_inicio'
                    )
                )
                & Q(
                    data_horario_fim=F(
                        'solicitacao__opcao_data_fim'
                    )
                )
            )
        )

        finalizadas_sem_nota = (
            BancaTCC.objects
            .filter(
                status='FINALIZADA',
                nota__isnull=True,
            )
        )

        notas_fora_de_finalizada = (
            BancaTCC.objects
            .filter(nota__isnull=False)
            .exclude(status='FINALIZADA')
        )

        return (
            (
                'SOLICITACAO_SEM_COMPOSICAO',
                'Solicitação sem composição de banca vinculada.',
                solicitacoes_sem_composicao,
            ),
            (
                'ORIENTADOR_DIFERENTE_DO_SOLICITANTE',
                (
                    'O orientador não corresponde ao docente que enviou '
                    'a solicitação. Pode ser um registro legado.'
                ),
                orientadores_divergentes,
            ),
            (
                'PRESIDENTE_FORA_DA_COMPOSICAO',
                'Presidente não pertence aos integrantes internos.',
                presidentes_fora_da_composicao,
            ),
            (
                'APROVADA_SEM_PRESIDENTE',
                'Solicitação aprovada sem presidente definido.',
                aprovadas_sem_presidente,
            ),
            (
                'APROVADA_SEM_BANCA',
                'Solicitação aprovada sem registro oficial de banca.',
                aprovadas_sem_banca,
            ),
            (
                'BANCA_SEM_SOLICITACAO',
                'Banca antiga sem solicitação vinculada.',
                bancas_sem_solicitacao,
            ),
            (
                'BANCA_DIVERGENTE_DA_SOLICITACAO',
                (
                    'Projeto, espaço ou horários da banca não correspondem '
                    'à solicitação aprovada.'
                ),
                bancas_divergentes,
            ),
            (
                'FINALIZADA_SEM_NOTA',
                'Banca finalizada sem nota registrada.',
                finalizadas_sem_nota,
            ),
            (
                'NOTA_FORA_DE_FINALIZADA',
                'Banca possui nota, mas não está finalizada.',
                notas_fora_de_finalizada,
            ),
        )
