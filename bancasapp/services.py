from collections import defaultdict
from datetime import timedelta

from django.utils import timezone

from .models import (
    BancaTCC,
    SolicitacaoAgendamento,
)


def expirar_solicitacoes_vencidas():
    """
    Expira solicitações que ainda estavam em análise
    quando chegou o horário previsto para a defesa.
    """

    return (
        SolicitacaoAgendamento.objects
        .filter(
            status='EM_ANÁLISE',
            opcao_data_inicio__lte=timezone.now(),
        )
        .update(
            status='EXPIRADA'
        )
    )


def atualizar_status_bancas():
    """
    Move bancas cujo horário terminou para
    o estado Aguardando nota.

    A banca somente será finalizada quando
    o orientador registrar a nota.
    """

    return (
        BancaTCC.objects
        .filter(
            status='AGENDADA',
            data_horario_fim__lte=timezone.now(),
            nota__isnull=True,
        )
        .update(
            status='AGUARDANDO_NOTA'
        )
    )


def _proximo_minuto(instante):
    """Evita oferecer ao docente um minuto que já começou."""

    minuto = instante.replace(
        second=0,
        microsecond=0,
    )

    if minuto < instante:
        minuto += timedelta(minutes=1)

    return minuto


def montar_agenda_disponibilidades(
    disponibilidades,
    agora=None,
):
    """
    Anexa a cada disponibilidade os períodos livres e ocupados.

    A regra é a mesma usada pelo formulário: solicitações em análise
    ou aprovadas reservam o espaço; recusadas e expiradas não entram
    no cálculo. Intervalos sobrepostos são unidos antes de calcular
    as lacunas livres.
    """

    disponibilidades = list(disponibilidades)

    if not disponibilidades:
        return []

    agora = agora or timezone.now()
    inicio_util_global = _proximo_minuto(agora)

    ids_espacos = {
        disponibilidade.espaco_id
        for disponibilidade in disponibilidades
    }

    inicio_consulta = min(
        disponibilidade.data_hora_inicio
        for disponibilidade in disponibilidades
    )
    fim_consulta = max(
        disponibilidade.data_hora_fim
        for disponibilidade in disponibilidades
    )

    solicitacoes = (
        SolicitacaoAgendamento.objects
        .filter(
            espaco_id__in=ids_espacos,
            opcao_data_inicio__lt=fim_consulta,
            opcao_data_fim__gt=max(
                inicio_consulta,
                agora,
            ),
        )
        .exclude(
            status__in=[
                'RECUSADA',
                'EXPIRADA',
            ]
        )
        .order_by(
            'espaco_id',
            'opcao_data_inicio',
            'opcao_data_fim',
        )
    )

    solicitacoes_por_espaco = defaultdict(list)

    for solicitacao in solicitacoes:
        solicitacoes_por_espaco[
            solicitacao.espaco_id
        ].append(solicitacao)

    for disponibilidade in disponibilidades:

        inicio_util = max(
            disponibilidade.data_hora_inicio,
            inicio_util_global,
        )
        fim_disponibilidade = disponibilidade.data_hora_fim
        intervalos_ocupados = []

        if inicio_util < fim_disponibilidade:

            for solicitacao in solicitacoes_por_espaco.get(
                disponibilidade.espaco_id,
                [],
            ):

                inicio_ocupado = max(
                    solicitacao.opcao_data_inicio,
                    inicio_util,
                )
                fim_ocupado = min(
                    solicitacao.opcao_data_fim,
                    fim_disponibilidade,
                )

                if inicio_ocupado >= fim_ocupado:
                    continue

                if (
                    intervalos_ocupados
                    and inicio_ocupado
                    <= intervalos_ocupados[-1]['fim']
                ):
                    intervalos_ocupados[-1]['fim'] = max(
                        intervalos_ocupados[-1]['fim'],
                        fim_ocupado,
                    )
                else:
                    intervalos_ocupados.append(
                        {
                            'inicio': inicio_ocupado,
                            'fim': fim_ocupado,
                        }
                    )

        intervalos_livres = []
        cursor = inicio_util

        for intervalo in intervalos_ocupados:

            if cursor < intervalo['inicio']:
                intervalos_livres.append(
                    {
                        'inicio': cursor,
                        'fim': intervalo['inicio'],
                    }
                )

            cursor = max(
                cursor,
                intervalo['fim'],
            )

        if cursor < fim_disponibilidade:
            intervalos_livres.append(
                {
                    'inicio': cursor,
                    'fim': fim_disponibilidade,
                }
            )

        disponibilidade.intervalos_ocupados = intervalos_ocupados
        disponibilidade.intervalos_livres = intervalos_livres
        disponibilidade.possui_horario_livre = bool(
            intervalos_livres
        )

    return disponibilidades
