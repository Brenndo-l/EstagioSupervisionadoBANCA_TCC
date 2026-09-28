from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bancasapp', '0016_alter_composicaobanca_segundo_avaliador_interno'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConfiguracaoAgendamento',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'duracao_banca_minutos',
                    models.PositiveSmallIntegerField(
                        choices=[
                            (30, '30 minutos'),
                            (45, '45 minutos'),
                            (60, '1 hora'),
                            (90, '1 hora e 30 minutos'),
                            (120, '2 horas'),
                        ],
                        default=60,
                        help_text=(
                            'O término será calculado automaticamente a '
                            'partir do horário inicial escolhido.'
                        ),
                        verbose_name='Duração padrão da banca',
                    ),
                ),
                (
                    'atualizado_em',
                    models.DateTimeField(auto_now=True),
                ),
            ],
            options={
                'verbose_name': 'Configuração de agendamento',
                'verbose_name_plural': 'Configurações de agendamento',
            },
        ),
    ]