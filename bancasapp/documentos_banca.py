import os
from datetime import timedelta
from decimal import Decimal
from html import escape
from io import BytesIO

from django.utils import timezone
from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Mm, Pt
import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import (
    TA_CENTER,
    TA_JUSTIFY,
    TA_LEFT,
    TA_RIGHT,
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


MESES = (
    '',
    'janeiro',
    'fevereiro',
    'março',
    'abril',
    'maio',
    'junho',
    'julho',
    'agosto',
    'setembro',
    'outubro',
    'novembro',
    'dezembro',
)


UNIDADES = {
    0: 'zero',
    1: 'um',
    2: 'dois',
    3: 'três',
    4: 'quatro',
    5: 'cinco',
    6: 'seis',
    7: 'sete',
    8: 'oito',
    9: 'nove',
    10: 'dez',
    11: 'onze',
    12: 'doze',
    13: 'treze',
    14: 'quatorze',
    15: 'quinze',
    16: 'dezesseis',
    17: 'dezessete',
    18: 'dezoito',
    19: 'dezenove',
}


DEZENAS = {
    20: 'vinte',
    30: 'trinta',
    40: 'quarenta',
    50: 'cinquenta',
    60: 'sessenta',
    70: 'setenta',
    80: 'oitenta',
    90: 'noventa',
}


def numero_ate_99_por_extenso(valor):

    if valor < 20:
        return UNIDADES[valor]

    dezena = (valor // 10) * 10
    unidade = valor % 10

    if unidade == 0:
        return DEZENAS[dezena]

    return (
        f'{DEZENAS[dezena]} e '
        f'{UNIDADES[unidade]}'
    )


def formatar_nota(nota):

    if nota is None:
        return '________________'

    nota_decimal = Decimal(nota).quantize(
        Decimal('0.01')
    )

    parte_inteira = int(nota_decimal)
    parte_decimal = int(
        (nota_decimal - parte_inteira) * 100
    )

    valor_formatado = (
        f'{nota_decimal:.2f}'
        .replace('.', ',')
    )

    valor_extenso = numero_ate_99_por_extenso(
        parte_inteira
    )

    if parte_decimal:
        valor_extenso = (
            f'{valor_extenso} vírgula '
            f'{numero_ate_99_por_extenso(parte_decimal)}'
        )

    return (
        f'{valor_formatado} '
        f'({valor_extenso})'
    )


def nome_docente(perfil):

    if perfil is None:
        return ''

    return perfil.nome_para_documento


def _funcao_com_presidencia(
    composicao,
    perfil,
    funcao
):

    presidente_id = (
        composicao.presidente_id
        or composicao.orientador_id
    )

    if (
        perfil
        and presidente_id == perfil.id
    ):
        return f'{funcao} e presidente'

    return funcao


def montar_integrantes(composicao):

    integrantes = []

    integrantes_internos = (
        (
            composicao.orientador,
            'Orientador(a)',
        ),
        (
            composicao.coorientador,
            'Coorientador(a)',
        ),
        (
            composicao.avaliador_interno,
            'Avaliador(a) interno(a)',
        ),
        (
            composicao.segundo_avaliador_interno,
            'Segundo(a) avaliador(a) interno(a)',
        ),
    )

    for perfil, funcao in integrantes_internos:

        if perfil is None:
            continue

        integrantes.append(
            {
                'nome': nome_docente(perfil),
                'funcao': _funcao_com_presidencia(
                    composicao,
                    perfil,
                    funcao
                ),
            }
        )

    if composicao.nome_avaliador_externo:

        nome_externo = (
            composicao.nome_avaliador_externo
        )

        if composicao.titulacao_avaliador_externo:
            nome_externo = (
                f'{composicao.get_titulacao_avaliador_externo_display()} '
                f'{nome_externo}'
            )

        funcao_externo = 'Avaliador(a) externo(a)'

        if composicao.instituicao_avaliador_externo:
            funcao_externo = (
                f'{funcao_externo} - '
                f'{composicao.instituicao_avaliador_externo}'
            )

        integrantes.append(
            {
                'nome': nome_externo,
                'funcao': funcao_externo,
            }
        )

    return integrantes


def montar_dados_ata(
    solicitacao,
    composicao,
    banca
):

    data_defesa = timezone.localtime(
        solicitacao.opcao_data_inicio
    )

    finalizada = bool(
        banca
        and banca.status == 'FINALIZADA'
        and banca.nota is not None
    )

    nota = (
        banca.nota
        if finalizada
        else None
    )

    data_limite = (
        banca.data_limite_versao_final
        if banca is not None
        else (
            data_defesa.date()
            + timedelta(days=30)
        )
    )

    return {
        'discente': solicitacao.projeto_tcc.discente.nome,
        'titulo_tcc': solicitacao.projeto_tcc.titulo,
        'espaco': solicitacao.espaco.nome,
        'presidente': nome_docente(
            composicao.presidente
            or composicao.orientador
        ),
        'integrantes': montar_integrantes(
            composicao
        ),
        'data_defesa': data_defesa,
        'data_defesa_extenso': (
            f'{data_defesa.day} de '
            f'{MESES[data_defesa.month]} de '
            f'{data_defesa.year}'
        ),
        'hora_defesa': (
            data_defesa.strftime('%Hh%M')
            if data_defesa.minute
            else data_defesa.strftime('%Hh')
        ),
        'finalizada': finalizada,
        'nota': nota,
        'nota_formatada': formatar_nota(nota),
        'data_limite_versao_final': data_limite,
        'data_limite_extenso': (
            f'{data_limite.day} de '
            f'{MESES[data_limite.month]} de '
            f'{data_limite.year}'
        ),
    }


def _registrar_fontes_pdf():

    if 'AtaSans' in pdfmetrics.getRegisteredFontNames():
        return

    diretorio_fontes = os.path.join(
        os.path.dirname(reportlab.__file__),
        'fonts'
    )

    pdfmetrics.registerFont(
        TTFont(
            'AtaSans',
            os.path.join(diretorio_fontes, 'Vera.ttf')
        )
    )

    pdfmetrics.registerFont(
        TTFont(
            'AtaSans-Bold',
            os.path.join(diretorio_fontes, 'VeraBd.ttf')
        )
    )

    pdfmetrics.registerFontFamily(
        'AtaSans',
        normal='AtaSans',
        bold='AtaSans-Bold',
    )


def gerar_pdf_ata(dados):

    _registrar_fontes_pdf()

    saida = BytesIO()

    documento = SimpleDocTemplate(
        saida,
        pagesize=A4,
        rightMargin=1.8 * cm,
        leftMargin=1.8 * cm,
        topMargin=1.7 * cm,
        bottomMargin=1.7 * cm,
        title=(
            'Ata de Apresentação do Trabalho '
            'de Conclusão de Curso'
        ),
        author='Universidade Federal do Acre',
    )

    estilo_cabecalho = ParagraphStyle(
        'CabecalhoAta',
        fontName='AtaSans-Bold',
        fontSize=10.5,
        leading=13,
        alignment=TA_CENTER,
        spaceAfter=0,
    )

    estilo_titulo = ParagraphStyle(
        'TituloAta',
        fontName='AtaSans-Bold',
        fontSize=13,
        leading=16,
        alignment=TA_CENTER,
        spaceAfter=18,
    )

    estilo_subtitulo = ParagraphStyle(
        'SubtituloAta',
        fontName='AtaSans-Bold',
        fontSize=10.5,
        leading=13,
        alignment=TA_CENTER,
        spaceBefore=12,
        spaceAfter=6,
    )

    estilo_corpo = ParagraphStyle(
        'CorpoAta',
        fontName='AtaSans',
        fontSize=10.5,
        leading=15,
        alignment=TA_JUSTIFY,
        firstLineIndent=1.25 * cm,
        spaceAfter=10,
    )

    estilo_campos = ParagraphStyle(
        'CamposAta',
        parent=estilo_corpo,
        fontName='AtaSans-Bold',
        alignment=TA_LEFT,
        firstLineIndent=0,
        leftIndent=1.25 * cm,
    )

    estilo_data = ParagraphStyle(
        'DataAta',
        parent=estilo_corpo,
        alignment=TA_RIGHT,
        firstLineIndent=0,
        spaceBefore=8,
    )

    estilo_tabela = ParagraphStyle(
        'TabelaAta',
        fontName='AtaSans',
        fontSize=9.5,
        leading=12,
        alignment=TA_LEFT,
    )

    estilo_tabela_cabecalho = ParagraphStyle(
        'TabelaCabecalhoAta',
        parent=estilo_tabela,
        fontName='AtaSans-Bold',
        alignment=TA_CENTER,
    )

    elementos = [
        Paragraph(
            'UNIVERSIDADE FEDERAL DO ACRE',
            estilo_cabecalho
        ),
        Paragraph(
            'CENTRO DE CIÊNCIAS EXATAS E TECNOLÓGICAS',
            estilo_cabecalho
        ),
        Paragraph(
            (
                'COORDENAÇÃO DO CURSO DE BACHARELADO '
                'EM SISTEMAS DE INFORMAÇÃO'
            ),
            estilo_cabecalho
        ),
        Spacer(1, 18),
        Paragraph(
            (
                'ATA DE APRESENTAÇÃO DO TRABALHO '
                'DE CONCLUSÃO DE CURSO'
            ),
            estilo_titulo
        ),
    ]

    texto_corpo = (
        f'Em {escape(dados["data_defesa_extenso"])}, às '
        f'{escape(dados["hora_defesa"])}, no espaço '
        f'{escape(dados["espaco"])}, da Universidade Federal '
        f'do Acre, na presença da Banca Examinadora presidida '
        f'por {escape(dados["presidente"])} e composta conforme '
        f'a relação abaixo, o(a) discente '
        f'{escape(dados["discente"])} apresentou o Trabalho de '
        f'Conclusão de Curso intitulado “'
        f'{escape(dados["titulo_tcc"])}”, como requisito '
        f'curricular para a integralização do Curso de '
        f'Bacharelado em Sistemas de Informação.'
    )

    elementos.append(
        Paragraph(texto_corpo, estilo_corpo)
    )

    elementos.append(
        Paragraph(
            'BANCA EXAMINADORA',
            estilo_subtitulo
        )
    )

    dados_tabela = [
        [
            Paragraph(
                'Integrante',
                estilo_tabela_cabecalho
            ),
            Paragraph(
                'Função',
                estilo_tabela_cabecalho
            ),
        ]
    ]

    for integrante in dados['integrantes']:
        dados_tabela.append(
            [
                Paragraph(
                    escape(integrante['nome']),
                    estilo_tabela
                ),
                Paragraph(
                    escape(integrante['funcao']),
                    estilo_tabela
                ),
            ]
        )

    tabela = Table(
        dados_tabela,
        colWidths=[10.5 * cm, 6.0 * cm],
        repeatRows=1,
        hAlign='CENTER',
    )

    tabela.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EEEEEE')),
                ('GRID', (0, 0), (-1, -1), 0.75, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]
        )
    )

    elementos.append(tabela)
    elementos.append(Spacer(1, 14))

    if dados['finalizada']:
        texto_resultado = (
            'A Banca Examinadora, após reunião em sessão '
            'reservada, deliberou e atribuiu ao referido '
            'Trabalho de Conclusão de Curso a nota '
            f'{escape(dados["nota_formatada"])}.'
        )
    else:
        texto_resultado = (
            'A Banca Examinadora, após reunião em sessão '
            'reservada, registrará o resultado da avaliação '
            'e a nota final nos campos abaixo.'
        )

    elementos.append(
        Paragraph(texto_resultado, estilo_corpo)
    )

    if not dados['finalizada']:
        elementos.append(
            Paragraph(
                (
                    'Resultado: ______________________________'
                    '&nbsp;&nbsp;&nbsp;&nbsp;'
                    'Nota: __________________'
                ),
                estilo_campos
            )
        )

    if dados['finalizada']:
        texto_prazo = (
            'Ao final, o(a) discente foi informado(a) da '
            'obrigatoriedade da apresentação da versão final '
            'do Trabalho de Conclusão de Curso no prazo máximo '
            'de 30 (trinta) dias corridos, até '
            f'{escape(dados["data_limite_extenso"])}, contendo '
            'os ajustes sugeridos pela Banca Examinadora, sob '
            'consentimento do(a) orientador(a).'
        )
    else:
        texto_prazo = (
            'Após a defesa, o(a) discente deverá ser '
            'informado(a) da obrigatoriedade da apresentação '
            'da versão final do Trabalho de Conclusão de Curso '
            'no prazo máximo de 30 (trinta) dias corridos, até '
            f'{escape(dados["data_limite_extenso"])}, contendo '
            'os ajustes sugeridos pela Banca Examinadora, sob '
            'consentimento do(a) orientador(a).'
        )

    elementos.extend(
        [
            Paragraph(texto_prazo, estilo_corpo),
            Paragraph(
                'Por ser verdade, registra-se a presente ata.',
                estilo_corpo
            ),
            Paragraph(
                (
                    'Rio Branco - AC, '
                    f'{escape(dados["data_defesa_extenso"])}.'
                ),
                estilo_data
            ),
        ]
    )

    documento.build(elementos)
    saida.seek(0)

    return saida


def _configurar_fonte_run(run, tamanho=11, negrito=False):

    run.font.name = 'Arial'
    run.font.size = Pt(tamanho)
    run.font.bold = negrito

    run._element.rPr.rFonts.set(
        qn('w:eastAsia'),
        'Arial'
    )


def _definir_margens_celula(
    celula,
    superior=100,
    inferior=100,
    esquerda=120,
    direita=120
):

    propriedades = celula._tc.get_or_add_tcPr()
    margens = propriedades.first_child_found_in(
        'w:tcMar'
    )

    if margens is None:
        margens = OxmlElement('w:tcMar')
        propriedades.append(margens)

    valores = {
        'top': superior,
        'bottom': inferior,
        'start': esquerda,
        'end': direita,
    }

    for lado, valor in valores.items():
        elemento = margens.find(
            qn(f'w:{lado}')
        )

        if elemento is None:
            elemento = OxmlElement(
                f'w:{lado}'
            )
            margens.append(elemento)

        elemento.set(qn('w:w'), str(valor))
        elemento.set(qn('w:type'), 'dxa')


def _adicionar_paragrafo_centralizado(
    documento,
    texto,
    tamanho=11,
    negrito=False,
    espaco_depois=0
):

    paragrafo = documento.add_paragraph()
    paragrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragrafo.paragraph_format.space_after = Pt(
        espaco_depois
    )

    run = paragrafo.add_run(texto)
    _configurar_fonte_run(
        run,
        tamanho=tamanho,
        negrito=negrito
    )

    return paragrafo


def gerar_docx_ata(dados):

    documento = Document()

    secao = documento.sections[0]
    secao.page_width = Mm(210)
    secao.page_height = Mm(297)
    secao.top_margin = Cm(1.8)
    secao.bottom_margin = Cm(1.8)
    secao.left_margin = Cm(2.0)
    secao.right_margin = Cm(2.0)

    estilo_normal = documento.styles['Normal']
    estilo_normal.font.name = 'Arial'
    estilo_normal.font.size = Pt(11)
    estilo_normal._element.rPr.rFonts.set(
        qn('w:eastAsia'),
        'Arial'
    )

    _adicionar_paragrafo_centralizado(
        documento,
        'UNIVERSIDADE FEDERAL DO ACRE',
        tamanho=11,
        negrito=True
    )

    _adicionar_paragrafo_centralizado(
        documento,
        'CENTRO DE CIÊNCIAS EXATAS E TECNOLÓGICAS',
        tamanho=11,
        negrito=True
    )

    _adicionar_paragrafo_centralizado(
        documento,
        'COORDENAÇÃO DO CURSO DE BACHARELADO EM SISTEMAS DE INFORMAÇÃO',
        tamanho=11,
        negrito=True,
        espaco_depois=18
    )

    _adicionar_paragrafo_centralizado(
        documento,
        'ATA DE APRESENTAÇÃO DO TRABALHO DE CONCLUSÃO DE CURSO',
        tamanho=13,
        negrito=True,
        espaco_depois=18
    )

    corpo = documento.add_paragraph()
    corpo.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    corpo.paragraph_format.first_line_indent = Cm(1.25)
    corpo.paragraph_format.line_spacing = 1.15
    corpo.paragraph_format.space_after = Pt(12)

    texto_corpo = (
        f'Em {dados["data_defesa_extenso"]}, às '
        f'{dados["hora_defesa"]}, no espaço '
        f'{dados["espaco"]}, da Universidade Federal do '
        f'Acre, na presença da Banca Examinadora presidida '
        f'por {dados["presidente"]} e composta conforme a '
        f'relação abaixo, o(a) discente {dados["discente"]} '
        f'apresentou o Trabalho de Conclusão de Curso '
        f'intitulado "{dados["titulo_tcc"]}", como requisito '
        f'curricular para a integralização do Curso de '
        f'Bacharelado em Sistemas de Informação.'
    )

    run_corpo = corpo.add_run(texto_corpo)
    _configurar_fonte_run(run_corpo)

    _adicionar_paragrafo_centralizado(
        documento,
        'BANCA EXAMINADORA',
        tamanho=11,
        negrito=True,
        espaco_depois=6
    )

    tabela = documento.add_table(
        rows=1,
        cols=2
    )

    tabela.style = 'Table Grid'
    tabela.alignment = WD_TABLE_ALIGNMENT.CENTER
    tabela.autofit = False

    cabecalho = tabela.rows[0].cells
    cabecalho[0].width = Cm(10.5)
    cabecalho[1].width = Cm(6.0)

    for celula, texto in zip(
        cabecalho,
        ('Integrante', 'Função')
    ):
        celula.vertical_alignment = (
            WD_CELL_VERTICAL_ALIGNMENT.CENTER
        )
        _definir_margens_celula(celula)
        paragrafo = celula.paragraphs[0]
        paragrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = paragrafo.add_run(texto)
        _configurar_fonte_run(
            run,
            tamanho=10,
            negrito=True
        )

    for integrante in dados['integrantes']:
        celulas = tabela.add_row().cells
        celulas[0].width = Cm(10.5)
        celulas[1].width = Cm(6.0)

        for celula, texto in zip(
            celulas,
            (
                integrante['nome'],
                integrante['funcao'],
            )
        ):
            celula.vertical_alignment = (
                WD_CELL_VERTICAL_ALIGNMENT.CENTER
            )
            _definir_margens_celula(celula)
            paragrafo = celula.paragraphs[0]
            paragrafo.alignment = (
                WD_ALIGN_PARAGRAPH.LEFT
            )
            run = paragrafo.add_run(texto)
            _configurar_fonte_run(
                run,
                tamanho=10
            )

    resultado = documento.add_paragraph()
    resultado.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    resultado.paragraph_format.first_line_indent = Cm(1.25)
    resultado.paragraph_format.line_spacing = 1.15
    resultado.paragraph_format.space_before = Pt(14)
    resultado.paragraph_format.space_after = Pt(10)

    if dados['finalizada']:
        texto_resultado = (
            'A Banca Examinadora, após reunião em sessão '
            'reservada, deliberou e atribuiu ao referido '
            'Trabalho de Conclusão de Curso a nota '
            f'{dados["nota_formatada"]}.'
        )
    else:
        texto_resultado = (
            'A Banca Examinadora, após reunião em sessão '
            'reservada, registrará o resultado da avaliação '
            'e a nota final nos campos abaixo.'
        )

    run_resultado = resultado.add_run(
        texto_resultado
    )
    _configurar_fonte_run(run_resultado)

    if not dados['finalizada']:
        campos = documento.add_paragraph()
        campos.alignment = WD_ALIGN_PARAGRAPH.LEFT
        campos.paragraph_format.left_indent = Cm(1.25)
        campos.paragraph_format.space_after = Pt(10)
        run_campos = campos.add_run(
            'Resultado: ______________________________    '
            'Nota: __________________'
        )
        _configurar_fonte_run(
            run_campos,
            negrito=True
        )

    prazo = documento.add_paragraph()
    prazo.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    prazo.paragraph_format.first_line_indent = Cm(1.25)
    prazo.paragraph_format.line_spacing = 1.15
    prazo.paragraph_format.space_after = Pt(10)

    if dados['finalizada']:
        texto_prazo = (
            'Ao final, o(a) discente foi informado(a) da '
            'obrigatoriedade da apresentação da versão final '
            'do Trabalho de Conclusão de Curso no prazo máximo '
            'de 30 (trinta) dias corridos, até '
            f'{dados["data_limite_extenso"]}, contendo os '
            'ajustes sugeridos pela Banca Examinadora, sob '
            'consentimento do(a) orientador(a).'
        )
    else:
        texto_prazo = (
            'Após a defesa, o(a) discente deverá ser '
            'informado(a) da obrigatoriedade da apresentação '
            'da versão final do Trabalho de Conclusão de Curso '
            'no prazo máximo de 30 (trinta) dias corridos, até '
            f'{dados["data_limite_extenso"]}, contendo os '
            'ajustes sugeridos pela Banca Examinadora, sob '
            'consentimento do(a) orientador(a).'
        )

    run_prazo = prazo.add_run(texto_prazo)
    _configurar_fonte_run(run_prazo)

    encerramento = documento.add_paragraph()
    encerramento.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    encerramento.paragraph_format.first_line_indent = Cm(1.25)
    encerramento.paragraph_format.space_after = Pt(18)
    run_encerramento = encerramento.add_run(
        'Por ser verdade, registra-se a presente ata.'
    )
    _configurar_fonte_run(run_encerramento)

    data = documento.add_paragraph()
    data.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run_data = data.add_run(
        f'Rio Branco - AC, {dados["data_defesa_extenso"]}.'
    )
    _configurar_fonte_run(run_data)

    saida = BytesIO()
    documento.save(saida)
    saida.seek(0)

    return saida
