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