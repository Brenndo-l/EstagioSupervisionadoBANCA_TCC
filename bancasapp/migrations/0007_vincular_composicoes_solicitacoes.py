from django.db import migrations


def vincular_composicoes(apps, schema_editor):

    ComposicaoBanca = apps.get_model(
        'bancasapp',
        'ComposicaoBanca'
    )

    SolicitacaoAgendamento = apps.get_model(
        'bancasapp',
        'SolicitacaoAgendamento'
    )

    composicoes_sem_solicitacao = (
        ComposicaoBanca.objects.filter(
            solicitacao__isnull=True
        )
    )

    for composicao in composicoes_sem_solicitacao.iterator():

        # Na estrutura antiga existia apenas uma composição
        # por projeto. Ela representava a solicitação mais recente.
        solicitacao = (
            SolicitacaoAgendamento.objects
            .filter(
                projeto_tcc_id=composicao.projeto_tcc_id
            )
            .order_by(
                '-data_solicitacao',
                '-id'
            )
            .first()
        )

        if solicitacao:

            composicao.solicitacao_id = solicitacao.id

            composicao.save(
                update_fields=['solicitacao']
            )


def desfazer_vinculos(apps, schema_editor):

    ComposicaoBanca = apps.get_model(
        'bancasapp',
        'ComposicaoBanca'
    )

    ComposicaoBanca.objects.update(
        solicitacao=None
    )


class Migration(migrations.Migration):

    dependencies = [
        (
            'bancasapp',
            '0006_composicaobanca_coorientador_and_more'
        ),
    ]

    operations = [
        migrations.RunPython(
            vincular_composicoes,
            desfazer_vinculos
        ),
    ]