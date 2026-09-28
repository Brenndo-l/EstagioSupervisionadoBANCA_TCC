from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import (
    BancaTCC,
    ComposicaoBanca,
    ConfiguracaoAgendamento,
    Discente,
    DisponibilidadeEspaco,
    EspacoFisico,
    ProjetoTCC,
    SolicitacaoAgendamento,
    pUsuario,
)


@dataclass(frozen=True)
class BloqueioTCCDiscente:
    """Motivo que impede uma nova solicitação para uma matrícula."""

    codigo: str
    mensagem: str


class SolicitacaoBancaInvalida(Exception):
    """Falha de regra de negócio detectada na gravação da solicitação."""

    def __init__(self, mensagem, campo='matricula_discente'):
        self.mensagem = mensagem
        self.campo = campo
        super().__init__(mensagem)


def obter_bloqueio_tcc_discente(
    *,
    matricula=None,
    discente=None,
):
    """
    Informa se o discente já possui um fluxo de TCC que impede outro.

    A restrição pertence à matrícula, nunca ao docente. Solicitações recusadas
    ou expiradas e bancas finalizadas com reprovação liberam uma nova
    tentativa. Uma aprovação acadêmica (nota final maior ou igual a 8,00)
    bloqueia definitivamente outro TCC para a mesma matrícula.

    Projetos legados sem solicitação não são tratados como fluxo ativo, pois
    não possuem estado operacional suficiente para determinar se continuam em
    andamento. Eles permanecem disponíveis para a auditoria de integridade.
    """

    if discente is None:
        matricula = (matricula or '').strip()

        if not matricula:
            return None

        discente = (
            Discente.objects
            .filter(matricula=matricula)
            .first()
        )

    if discente is None:
        return None

    nota_minima = BancaTCC.NOTA_MINIMA_APROVACAO

    aprovado = (
        BancaTCC.objects
        .filter(
            projeto_tcc__discente=discente,
            status='FINALIZADA',
            nota__gte=nota_minima,
        )
        .exists()
    )

    if aprovado:
        return BloqueioTCCDiscente(
            codigo='APROVADO_DEFINITIVAMENTE',
            mensagem=(
                'Esta matrícula já possui um TCC finalizado com '
                'aprovação e não pode receber uma nova solicitação.'
            ),
        )

    solicitacoes = (
        SolicitacaoAgendamento.objects
        .filter(
            projeto_tcc__discente=discente,
            status__in=[
                'EM_ANÁLISE',
                'APROVADA',
            ],
        )
        .select_related('banca_tcc')
        .order_by('id')
    )

    for solicitacao in solicitacoes:
        if solicitacao.status == 'EM_ANÁLISE':
            return BloqueioTCCDiscente(
                codigo='SOLICITACAO_EM_ANALISE',
                mensagem=(
                    'Esta matrícula já possui uma solicitação de TCC '
                    'em análise. Aguarde a conclusão desse fluxo antes '
                    'de cadastrar outro projeto.'
                ),
            )

        try:
            banca = solicitacao.banca_tcc
        except BancaTCC.DoesNotExist:
            banca = None

        if banca is None:
            return BloqueioTCCDiscente(
                codigo='SOLICITACAO_APROVADA',
                mensagem=(
                    'Esta matrícula já possui uma solicitação de TCC '
                    'aprovada e ainda não finalizada.'
                ),
            )

        if banca.status != 'FINALIZADA' or banca.nota is None:
            return BloqueioTCCDiscente(
                codigo='BANCA_EM_ANDAMENTO',
                mensagem=(
                    'Esta matrícula já possui uma banca agendada, em '
                    'andamento ou aguardando nota.'
                ),
            )

        # A aprovação definitiva foi tratada antes da consulta. Portanto,
        # uma banca finalizada com nota abaixo de 8,00 libera nova tentativa.
        if Decimal(banca.nota) < nota_minima:
            continue

    return None


@transaction.atomic
def criar_solicitacao_banca_segura(*, form, orientador):
    """
    Cria todo o fluxo inicial sob uma trava da matrícula do discente.

    O formulário oferece a primeira resposta amigável, mas esta nova
    verificação dentro da transação é a proteção definitiva contra duas
    requisições concorrentes para a mesma matrícula.
    """

    segundo_avaliador = form.cleaned_data.get(
        'segundo_avaliador_interno'
    )

    if segundo_avaliador is None:
        raise SolicitacaoBancaInvalida(
            'A banca deve ter dois avaliadores internos. '
            'Informe o segundo avaliador antes de enviar '
            'a solicitação.'
        )

    matricula = form.cleaned_data['matricula_discente']
    nome_discente = form.cleaned_data['nome_discente']

    discente, _ = Discente.objects.get_or_create(
        matricula=matricula,
        defaults={
            'nome': nome_discente,
        },
    )

    # No PostgreSQL usado em produção, serializa submissões concorrentes da
    # mesma matrícula. No SQLite de desenvolvimento, as escritas já são
    # serializadas pelo próprio banco.
    discente = (
        Discente.objects
        .select_for_update()
        .get(pk=discente.pk)
    )

    if discente.nome.casefold() != nome_discente.casefold():
        raise SolicitacaoBancaInvalida(
            'Esta matrícula já pertence ao discente '
            f'"{discente.nome}".'
        )

    bloqueio = obter_bloqueio_tcc_discente(
        discente=discente
    )

    if bloqueio:
        raise SolicitacaoBancaInvalida(
            bloqueio.mensagem
        )

    # A validação inicial do formulário pode ficar obsoleta entre o GET,
    # o POST e a gravação. Trave a sala e confira novamente disponibilidade
    # e conflitos antes de criar qualquer projeto/solicitação.
    sala = EspacoFisico.objects.select_for_update().get(
        pk=form.cleaned_data['espaco'].pk
    )
    inicio = form.cleaned_data['opcao_data_inicio']
    fim = form.cleaned_data['opcao_data_fim']
    periodos_validos = DisponibilidadeEspaco.objects.filter(
        espaco=sala, ativo=True,
        data_hora_inicio__lte=inicio,
        data_hora_fim__gte=fim,
    )
    if not sala.ativo or not periodos_validos.exists():
        raise SolicitacaoBancaInvalida(
            'O horário deixou de estar disponível para esta sala. '
            'Atualize a página e selecione outro horário.',
            campo='espaco',
        )
    duracao = timedelta(
        minutes=ConfiguracaoAgendamento.carregar().duracao_banca_minutos
    )
    if fim - inicio != duracao or not any(
        (inicio - periodo.data_hora_inicio) % duracao == timedelta(0)
        for periodo in periodos_validos
    ):
        raise SolicitacaoBancaInvalida(
            'A regra de duração ou a grade de horários foi alterada. '
            'Atualize a página e escolha um dos horários publicados.',
            campo='opcao_data_inicio',
        )
    if SolicitacaoAgendamento.objects.filter(
        espaco=sala,
        opcao_data_inicio__lt=fim,
        opcao_data_fim__gt=inicio,
    ).exclude(status__in=['RECUSADA', 'EXPIRADA']).exists():
        raise SolicitacaoBancaInvalida(
            'Outra banca ocupou este horário. Atualize a página e '
            'selecione outro horário.',
            campo='espaco',
        )

    participantes = [
        orientador,
        form.cleaned_data.get('coorientador'),
        form.cleaned_data.get('avaliador_interno'),
        segundo_avaliador,
    ]
    participantes_ids = sorted({
        docente.pk for docente in participantes if docente is not None
    })
    # A sala sozinha não protege um docente que apareça simultaneamente
    # em duas bancas de laboratórios distintos. Bloqueie todos os perfis
    # em ordem estável e consulte novamente sob a mesma transação.
    list(
        pUsuario.objects.select_for_update()
        .filter(pk__in=participantes_ids).order_by('pk')
    )
    filtro_participantes = (
        Q(composicao_banca__orientador_id__in=participantes_ids)
        | Q(composicao_banca__coorientador_id__in=participantes_ids)
        | Q(composicao_banca__avaliador_interno_id__in=participantes_ids)
        | Q(composicao_banca__segundo_avaliador_interno_id__in=participantes_ids)
        | Q(composicao_banca__presidente_id__in=participantes_ids)
    )
    if (
        SolicitacaoAgendamento.objects.filter(
            opcao_data_inicio__lt=fim,
            opcao_data_fim__gt=inicio,
        )
        .exclude(status__in=['RECUSADA', 'EXPIRADA'])
        .filter(filtro_participantes)
        .exists()
    ):
        raise SolicitacaoBancaInvalida(
            'Um dos docentes indicados já participa de outra banca neste '
            'horário, inclusive se ela ocorrer em outra sala. Atualize a '
            'página e escolha outro horário ou outra composição.',
            campo=None,
        )

    projeto = ProjetoTCC.objects.create(
        titulo=form.cleaned_data['titulo_tcc'],
        resumo=form.cleaned_data['resumo_tcc'],
        semestre_letivo=form.cleaned_data['semestre_letivo'],
        discente=discente,
        status='EM_ANÁLISE',
    )

    solicitacao = form.save(commit=False)
    solicitacao.projeto_tcc = projeto
    solicitacao.status = 'EM_ANÁLISE'
    solicitacao.usuario_solicitante = orientador
    solicitacao.save()

    ComposicaoBanca.objects.create(
        solicitacao=solicitacao,
        projeto_tcc=projeto,
        orientador=orientador,
        coorientador=form.cleaned_data['coorientador'],
        avaliador_interno=form.cleaned_data['avaliador_interno'],
        segundo_avaliador_interno=segundo_avaliador,
        presidente=form.cleaned_data['presidente'],
        nome_avaliador_externo=(
            form.cleaned_data['nome_avaliador_externo']
        ),
        titulacao_avaliador_externo=(
            form.cleaned_data['titulacao_avaliador_externo']
        ),
        instituicao_avaliador_externo=(
            form.cleaned_data['instituicao_avaliador_externo']
        ),
    )

    return solicitacao


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
    excluir_solicitacao_id=None,
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

    if excluir_solicitacao_id:
        solicitacoes = solicitacoes.exclude(
            pk=excluir_solicitacao_id
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
        reservas = []

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

                reservas.append({
                    'inicio': inicio_ocupado,
                    'fim': fim_ocupado,
                    'status': solicitacao.status,
                })

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
        disponibilidade.reservas = reservas
        disponibilidade.intervalos_livres = intervalos_livres
        disponibilidade.possui_horario_livre = bool(
            intervalos_livres
        )

    return disponibilidades


def montar_opcoes_agendamento(
    disponibilidades,
    *,
    agora=None,
    excluir_solicitacao_id=None,
):
    """
    Gera opções serializáveis para o seletor de sala, data e horário.

    A grade é ancorada no início ORIGINAL de cada disponibilidade e
    avança exatamente uma duração de banca por vez. Uma reserva nunca
    desloca a grade: os blocos reservados continuam visíveis, sem permitir
    seleção. ``datas`` contém somente opções livres e ``grade`` contém
    todos os blocos futuros, incluindo os estados das reservas.
    A mesma lista é exibida a todos os docentes, sem filtro pessoal.
    """

    configuracao = ConfiguracaoAgendamento.carregar()
    duracao = timedelta(
        minutes=configuracao.duracao_banca_minutos
    )
    agora = agora or timezone.now()

    agenda = montar_agenda_disponibilidades(
        disponibilidades,
        agora=agora,
        excluir_solicitacao_id=excluir_solicitacao_id,
    )

    espacos = {}
    periodos_aceitos = defaultdict(list)

    for disponibilidade in sorted(
        agenda, key=lambda item: (item.data_hora_inicio, item.pk or 0)
    ):
        if (
            not disponibilidade.ativo
            or not disponibilidade.espaco.ativo
            or disponibilidade.data_hora_fim <= agora
        ):
            continue

        # Dados legados podem conter duas disponibilidades ativas para a
        # mesma sala. Nunca publique a grade deslocada do segundo registro:
        # mantenha apenas o primeiro até que a Coordenação revise a auditoria.
        periodos_sala = periodos_aceitos[disponibilidade.espaco_id]
        if any(
            disponibilidade.data_hora_inicio < fim_aceito
            and disponibilidade.data_hora_fim > inicio_aceito
            for inicio_aceito, fim_aceito in periodos_sala
        ):
            continue
        periodos_sala.append((
            disponibilidade.data_hora_inicio,
            disponibilidade.data_hora_fim,
        ))

        espaco_id = str(disponibilidade.espaco_id)
        dados_espaco = espacos.setdefault(
            espaco_id,
            {
                'nome': disponibilidade.espaco.nome,
                'datas': {},
                'grade': {},
            },
        )

        inicio = disponibilidade.data_hora_inicio
        limite = disponibilidade.data_hora_fim

        while inicio + duracao <= limite:
            fim = inicio + duracao
            if inicio > agora:
                inicio_local = timezone.localtime(inicio)
                fim_local = timezone.localtime(fim)
                data_iso = inicio_local.date().isoformat()
                if fim_local.date() == inicio_local.date():
                    opcao = {
                        'inicio': inicio_local.strftime('%H:%M'),
                        'fim': fim_local.strftime('%H:%M'),
                        'inicio_iso': inicio_local.strftime('%Y-%m-%dT%H:%M'),
                        'fim_iso': fim_local.strftime('%Y-%m-%dT%H:%M'),
                    }
                    reservas = [
                        reserva for reserva in disponibilidade.reservas
                        if inicio < reserva['fim']
                        and fim > reserva['inicio']
                    ]
                    if any(
                        reserva['status'] == 'APROVADA'
                        for reserva in reservas
                    ):
                        opcao['situacao'] = 'agendado'
                    elif reservas:
                        opcao['situacao'] = 'em_analise'
                    else:
                        opcao['situacao'] = 'disponivel'

                    grade_data = dados_espaco['grade'].setdefault(
                        data_iso, []
                    )
                    # Protege a tela também de dados legados com períodos
                    # duplicados/sobrepostos na mesma sala.
                    if not any(
                        opcao['inicio_iso'] < existente['fim_iso']
                        and opcao['fim_iso'] > existente['inicio_iso']
                        for existente in grade_data
                    ):
                        grade_data.append(opcao)
                        if opcao['situacao'] == 'disponivel':
                            dados_espaco['datas'].setdefault(
                                data_iso, []
                            ).append(opcao)

            inicio += duracao

    for dados_espaco in espacos.values():
        for chave in ('datas', 'grade'):
            for opcoes in dados_espaco[chave].values():
                opcoes.sort(key=lambda item: item['inicio_iso'])

    return {
        'duracao_minutos': configuracao.duracao_banca_minutos,
        'duracao_rotulo': (
            configuracao.get_duracao_banca_minutos_display()
        ),
        'espacos': espacos,
    }