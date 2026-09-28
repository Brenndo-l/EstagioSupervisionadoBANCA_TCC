(function () {
    'use strict';

    const corpo = document.body;
    const menu = document.querySelector('.sidebar');
    const botaoMenu = document.querySelector('[data-sidebar-toggle]');
    const fundoMenu = document.querySelector('[data-sidebar-overlay]');

    function menuEstaAberto() {
        return corpo.classList.contains('menu-aberto');
    }

    function definirEstadoMenu(aberto) {
        corpo.classList.toggle('menu-aberto', aberto);

        if (botaoMenu) {
            botaoMenu.setAttribute(
                'aria-expanded',
                aberto ? 'true' : 'false'
            );

            botaoMenu.setAttribute(
                'aria-label',
                aberto
                    ? 'Fechar menu principal'
                    : 'Abrir menu principal'
            );
        }
    }

    if (botaoMenu && menu) {
        botaoMenu.addEventListener('click', function () {
            definirEstadoMenu(!menuEstaAberto());
        });
    }

    if (fundoMenu) {
        fundoMenu.addEventListener('click', function () {
            definirEstadoMenu(false);
        });
    }

    document.addEventListener('keydown', function (evento) {
        if (evento.key === 'Escape' && menuEstaAberto()) {
            definirEstadoMenu(false);

            if (botaoMenu) {
                botaoMenu.focus();
            }
        }
    });

    document.querySelectorAll('.nav-link').forEach(function (link) {
        link.addEventListener('click', function () {
            if (window.matchMedia('(max-width: 980px)').matches) {
                definirEstadoMenu(false);
            }
        });
    });

    window.addEventListener('resize', function () {
        if (!window.matchMedia('(max-width: 980px)').matches) {
            definirEstadoMenu(false);
        }
    });

    document.querySelectorAll('[data-alert-close]').forEach(
        function (botao) {
            botao.addEventListener('click', function () {
                const alerta = botao.closest('.alerta');

                if (alerta) {
                    alerta.classList.add('alerta-saindo');

                    window.setTimeout(function () {
                        alerta.remove();
                    }, 180);
                }
            });
        }
    );

    document.querySelectorAll('.page-content table').forEach(
        function (tabela) {
            if (tabela.parentElement.classList.contains('table-scroll')) {
                return;
            }

            const envoltorio = document.createElement('div');
            envoltorio.className = 'table-scroll';
            envoltorio.setAttribute('tabindex', '0');
            envoltorio.setAttribute(
                'aria-label',
                'Tabela com rolagem horizontal quando necessária'
            );

            tabela.parentNode.insertBefore(envoltorio, tabela);
            envoltorio.appendChild(tabela);
        }
    );

    document.querySelectorAll('form[data-confirm]').forEach(
        function (formulario) {
            formulario.addEventListener('submit', function (evento) {
                const mensagem = formulario.dataset.confirm;

                if (mensagem && !window.confirm(mensagem)) {
                    evento.preventDefault();
                }
            });
        }
    );

    // A Vercel rejeita corpos maiores antes de a requisição chegar ao
    // Django. Esta validação dá uma mensagem clara no próprio navegador;
    // o formulário também repete a validação no servidor.
    document.querySelectorAll(
        'input[type="file"][data-max-file-size]'
    ).forEach(function (campo) {
        function removerErroTamanho() {
            campo.setCustomValidity('');

            const erroAtual = campo.parentElement.querySelector(
                '.arquivo-tamanho-erro'
            );

            if (erroAtual) {
                erroAtual.remove();
            }
        }

        campo.addEventListener('change', function () {
            removerErroTamanho();

            const arquivo = campo.files && campo.files[0];
            const limite = Number(campo.dataset.maxFileSize);

            if (!arquivo || !Number.isFinite(limite)) {
                return;
            }

            if (arquivo.size > limite) {
                const rotulo = campo.dataset.maxFileLabel || 'permitido';
                const mensagem = (
                    'O arquivo selecionado ultrapassa o limite de '
                    + rotulo
                    + '.'
                );

                campo.value = '';
                campo.setCustomValidity(mensagem);

                const aviso = document.createElement('p');
                aviso.className = (
                    'shared-field-error arquivo-tamanho-erro'
                );
                aviso.setAttribute('role', 'alert');
                aviso.textContent = mensagem;
                campo.insertAdjacentElement('afterend', aviso);
                campo.reportValidity();
            }
        });
    });

    function campoDoGrupo(grupo, seletor) {
        return grupo ? grupo.querySelector(seletor) : null;
    }

    function lerDataHora(grupo) {
        const campoData = campoDoGrupo(grupo, '[data-date-part]');
        const campoHora = campoDoGrupo(grupo, '[data-time-part]');

        if (!campoData || !campoHora || !campoData.value || !campoHora.value) {
            return null;
        }

        const valor = new Date(
            campoData.value + 'T' + campoHora.value + ':00'
        );

        return Number.isNaN(valor.getTime()) ? null : valor;
    }

    function doisDigitos(valor) {
        return String(valor).padStart(2, '0');
    }

    function escreverDataHora(grupo, valor) {
        const campoData = campoDoGrupo(grupo, '[data-date-part]');
        const campoHora = campoDoGrupo(grupo, '[data-time-part]');

        if (!campoData || !campoHora || !valor) {
            return;
        }

        campoData.value = [
            valor.getFullYear(),
            doisDigitos(valor.getMonth() + 1),
            doisDigitos(valor.getDate())
        ].join('-');

        campoHora.value = (
            doisDigitos(valor.getHours())
            + ':'
            + doisDigitos(valor.getMinutes())
        );
    }

    function mostrarRetorno(formulario, mensagem, tipo) {
        const retorno = formulario.querySelector(
            '[data-schedule-feedback]'
        );

        if (!retorno) {
            return;
        }

        retorno.hidden = false;
        retorno.textContent = mensagem;
        retorno.dataset.feedbackType = tipo || 'info';
    }

    function limparSelecaoAgenda(formulario) {
        delete formulario.dataset.slotEnd;

        document.querySelectorAll('[data-agenda-slot]').forEach(
            function (botao) {
                botao.classList.remove('is-selected');
                botao.removeAttribute('aria-pressed');
            }
        );
    }

    function atualizarLimites(formulario) {
        const grupoInicio = formulario.querySelector(
            '[data-date-time-role="inicio"]'
        );
        const grupoFim = formulario.querySelector(
            '[data-date-time-role="fim"]'
        );
        const dataInicio = campoDoGrupo(grupoInicio, '[data-date-part]');
        const horaInicio = campoDoGrupo(grupoInicio, '[data-time-part]');
        const dataFim = campoDoGrupo(grupoFim, '[data-date-part]');
        const horaFim = campoDoGrupo(grupoFim, '[data-time-part]');

        if (!dataInicio || !horaInicio || !dataFim || !horaFim) {
            return;
        }

        if (dataInicio.value) {
            dataFim.min = dataInicio.value;

            if (!dataFim.value) {
                dataFim.value = dataInicio.value;
            }
        }

        if (
            dataInicio.value
            && dataFim.value === dataInicio.value
            && horaInicio.value
        ) {
            horaFim.min = horaInicio.value;
        } else {
            horaFim.removeAttribute('min');
        }
    }

    function definirFimPadrao(formulario) {
        const grupoInicio = formulario.querySelector(
            '[data-date-time-role="inicio"]'
        );
        const grupoFim = formulario.querySelector(
            '[data-date-time-role="fim"]'
        );
        const inicio = lerDataHora(grupoInicio);
        const fimAtual = lerDataHora(grupoFim);

        if (!inicio || (fimAtual && fimAtual > inicio)) {
            atualizarLimites(formulario);
            return;
        }

        escreverDataHora(
            grupoFim,
            new Date(inicio.getTime() + (60 * 60 * 1000))
        );
        atualizarLimites(formulario);
    }

    document.querySelectorAll('[data-scheduling-form]').forEach(
        function (formulario) {
            const grupoInicio = formulario.querySelector(
                '[data-date-time-role="inicio"]'
            );

            if (!grupoInicio) {
                return;
            }

            grupoInicio.querySelectorAll('input').forEach(
                function (campo) {
                    campo.addEventListener('change', function () {
                        limparSelecaoAgenda(formulario);
                        definirFimPadrao(formulario);
                    });
                }
            );

            formulario.querySelectorAll(
                '[data-date-time-role="fim"] input'
            ).forEach(function (campo) {
                campo.addEventListener('change', function () {
                    limparSelecaoAgenda(formulario);
                    atualizarLimites(formulario);
                });
            });

            const campoEspaco = formulario.querySelector(
                'select[name="espaco"]'
            );

            if (campoEspaco) {
                campoEspaco.addEventListener('change', function () {
                    limparSelecaoAgenda(formulario);
                });
            }

            formulario.querySelectorAll('[data-duration-minutes]').forEach(
                function (botao) {
                    botao.addEventListener('click', function () {
                        const inicio = lerDataHora(grupoInicio);

                        if (!inicio) {
                            mostrarRetorno(
                                formulario,
                                'Informe primeiro a data e a hora de início.',
                                'warning'
                            );
                            campoDoGrupo(
                                grupoInicio,
                                '[data-date-part]'
                            ).focus();
                            return;
                        }

                        const minutos = Number(
                            botao.dataset.durationMinutes
                        );
                        let fim = new Date(
                            inicio.getTime() + (minutos * 60 * 1000)
                        );

                        if (formulario.dataset.slotEnd) {
                            const limite = new Date(
                                formulario.dataset.slotEnd
                            );

                            if (fim > limite) {
                                fim = limite;
                            }
                        }

                        escreverDataHora(
                            formulario.querySelector(
                                '[data-date-time-role="fim"]'
                            ),
                            fim
                        );
                        atualizarLimites(formulario);

                        mostrarRetorno(
                            formulario,
                            'Término calculado. Revise o período antes de enviar.',
                            'success'
                        );
                    });
                }
            );

            atualizarLimites(formulario);
        }
    );

    document.querySelectorAll('[data-appointment-picker]').forEach(
        function (seletor) {
            const formulario = seletor.closest('form');
            const campoEspaco = seletor.querySelector('select[name="espaco"]');
            const calendario = seletor.querySelector('[data-calendar]');
            const diasCalendario = seletor.querySelector('[data-calendar-days]');
            const tituloCalendario = seletor.querySelector('[data-calendar-title]');
            const botaoAnterior = seletor.querySelector('[data-calendar-previous]');
            const botaoProximo = seletor.querySelector('[data-calendar-next]');
            const instrucaoCalendario = seletor.querySelector(
                '[data-calendar-instruction]'
            );
            const rotuloDia = seletor.querySelector('[data-selected-day-label]');
            const grupoHorarios = seletor.querySelector('[data-schedule-slots]');
            const opcoesHorarios = seletor.querySelector(
                '[data-schedule-slot-options]'
            );
            const confirmacaoInicio = seletor.querySelector(
                '[data-confirmation-start]'
            );
            const confirmacaoFim = seletor.querySelector(
                '[data-confirmation-end]'
            );
            const grupoInicio = seletor.querySelector(
                '[data-date-time-role="inicio"]'
            );
            const grupoFim = seletor.querySelector(
                '[data-date-time-role="fim"]'
            );
            const dadosElemento = document.getElementById(
                seletor.dataset.scheduleJsonId
            );

            if (
                !formulario
                || !campoEspaco
                || !dadosElemento
                || !grupoInicio
                || !grupoFim
            ) {
                return;
            }

            let dados;

            try {
                dados = JSON.parse(dadosElemento.textContent);
            } catch (erro) {
                mostrarRetorno(
                    formulario,
                    'Não foi possível carregar os horários. Atualize a página.',
                    'warning'
                );
                return;
            }

            let dataSelecionada = null;
            let indiceMes = 0;
            let mesesDisponiveis = [];

            grupoInicio.querySelectorAll('input').forEach(function (campo) {
                campo.required = false;
                campo.tabIndex = -1;
            });
            grupoFim.querySelectorAll('input').forEach(function (campo) {
                campo.required = false;
                campo.tabIndex = -1;
            });

            function dadosDoEspaco() {
                return dados.espacos[String(campoEspaco.value)] || null;
            }

            function dataLocal(dataIso) {
                const partes = dataIso.split('-').map(Number);
                return new Date(partes[0], partes[1] - 1, partes[2]);
            }

            function dataHoraLocal(dataHoraIso) {
                return new Date(dataHoraIso + ':00');
            }

            function formatarData(dataIso) {
                return new Intl.DateTimeFormat('pt-BR', {
                    weekday: 'long',
                    day: '2-digit',
                    month: 'long',
                    year: 'numeric'
                }).format(dataLocal(dataIso));
            }

            function formatarConfirmacao(dataHoraIso) {
                return new Intl.DateTimeFormat('pt-BR', {
                    day: '2-digit',
                    month: '2-digit',
                    year: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                }).format(dataHoraLocal(dataHoraIso));
            }

            function limparCamposHorario() {
                grupoInicio.querySelectorAll('input').forEach(function (campo) {
                    campo.value = '';
                });
                grupoFim.querySelectorAll('input').forEach(function (campo) {
                    campo.value = '';
                });
                confirmacaoInicio.textContent = 'Nenhum horário escolhido';
                confirmacaoFim.textContent = '—';
            }

            function selecionarHorario(opcao) {
                escreverDataHora(grupoInicio, dataHoraLocal(opcao.inicio_iso));
                escreverDataHora(grupoFim, dataHoraLocal(opcao.fim_iso));
                confirmacaoInicio.textContent = formatarConfirmacao(
                    opcao.inicio_iso
                );
                confirmacaoFim.textContent = formatarConfirmacao(opcao.fim_iso);
                mostrarRetorno(
                    formulario,
                    'Horário selecionado: '
                    + opcao.inicio
                    + '–'
                    + opcao.fim
                    + '. O próximo horário pode começar exatamente às '
                    + opcao.fim
                    + '.',
                    'success'
                );
            }

            function renderizarHorarios() {
                const espaco = dadosDoEspaco();
                const horarios = (
                    espaco && dataSelecionada
                    ? espaco.datas[dataSelecionada] || []
                    : []
                );

                opcoesHorarios.replaceChildren();
                grupoHorarios.disabled = horarios.length === 0;

                if (!horarios.length) {
                    const vazio = document.createElement('p');
                    vazio.className = 'schedule-slots__empty';
                    vazio.textContent = (
                        dataSelecionada
                        ? 'Não há horários completos disponíveis neste dia.'
                        : 'Os horários aparecerão após a escolha do dia.'
                    );
                    opcoesHorarios.appendChild(vazio);
                    return;
                }

                rotuloDia.textContent = formatarData(dataSelecionada);

                horarios.forEach(function (opcao, indice) {
                    const identificador = (
                        seletor.dataset.scheduleJsonId
                        + '-horario-'
                        + indice
                    );
                    const radio = document.createElement('input');
                    const label = document.createElement('label');

                    radio.type = 'radio';
                    radio.name = seletor.dataset.scheduleJsonId + '-horario';
                    radio.id = identificador;
                    radio.value = opcao.inicio_iso;
                    radio.className = 'schedule-slot-input';

                    label.htmlFor = identificador;
                    label.className = 'schedule-slot-option';
                    label.innerHTML = (
                        '<strong>' + opcao.inicio + '</strong>'
                        + '<span>até ' + opcao.fim + '</span>'
                    );

                    radio.addEventListener('change', function () {
                        selecionarHorario(opcao);
                    });

                    opcoesHorarios.appendChild(radio);
                    opcoesHorarios.appendChild(label);
                });
            }

            function renderizarCalendario() {
                const espaco = dadosDoEspaco();

                diasCalendario.replaceChildren();

                if (!espaco || !mesesDisponiveis.length) {
                    calendario.hidden = true;
                    return;
                }

                calendario.hidden = false;

                const partesMes = mesesDisponiveis[indiceMes]
                    .split('-')
                    .map(Number);
                const ano = partesMes[0];
                const mes = partesMes[1] - 1;
                const primeiroDia = new Date(ano, mes, 1);
                const ultimoDia = new Date(ano, mes + 1, 0).getDate();

                tituloCalendario.textContent = new Intl.DateTimeFormat(
                    'pt-BR',
                    {month: 'long', year: 'numeric'}
                ).format(primeiroDia);

                botaoAnterior.disabled = indiceMes === 0;
                botaoProximo.disabled = indiceMes === mesesDisponiveis.length - 1;

                for (let vazio = 0; vazio < primeiroDia.getDay(); vazio += 1) {
                    const espacoVazio = document.createElement('span');
                    espacoVazio.className = 'schedule-calendar__blank';
                    diasCalendario.appendChild(espacoVazio);
                }

                for (let dia = 1; dia <= ultimoDia; dia += 1) {
                    const dataIso = [
                        ano,
                        doisDigitos(mes + 1),
                        doisDigitos(dia)
                    ].join('-');
                    const disponivel = Boolean(espaco.datas[dataIso]);
                    const botao = document.createElement('button');

                    botao.type = 'button';
                    botao.textContent = dia;
                    botao.className = 'schedule-calendar__day';
                    botao.disabled = !disponivel;

                    if (dataSelecionada === dataIso) {
                        botao.classList.add('is-selected');
                        botao.setAttribute('aria-current', 'date');
                    }

                    if (disponivel) {
                        botao.setAttribute(
                            'aria-label',
                            'Selecionar ' + formatarData(dataIso)
                        );
                        botao.addEventListener('click', function () {
                            dataSelecionada = dataIso;
                            limparCamposHorario();
                            renderizarCalendario();
                            renderizarHorarios();
                        });
                    }

                    diasCalendario.appendChild(botao);
                }
            }

            function carregarEspaco(preservarSelecao) {
                const espaco = dadosDoEspaco();

                dataSelecionada = preservarSelecao ? dataSelecionada : null;
                if (!preservarSelecao) {
                    limparCamposHorario();
                }
                opcoesHorarios.replaceChildren();
                grupoHorarios.disabled = true;

                if (!espaco) {
                    mesesDisponiveis = [];
                    calendario.hidden = true;
                    instrucaoCalendario.textContent = (
                        campoEspaco.value
                        ? 'Esta sala não possui horários completos disponíveis.'
                        : 'Primeiro, escolha uma sala.'
                    );
                    rotuloDia.textContent = 'Escolha um dia disponível.';
                    renderizarHorarios();
                    return;
                }

                const datas = Object.keys(espaco.datas).sort();
                mesesDisponiveis = Array.from(
                    new Set(datas.map(function (data) {
                        return data.slice(0, 7);
                    }))
                );

                if (
                    dataSelecionada
                    && !espaco.datas[dataSelecionada]
                ) {
                    dataSelecionada = null;
                }

                const mesSelecionado = dataSelecionada
                    ? dataSelecionada.slice(0, 7)
                    : mesesDisponiveis[0];
                indiceMes = Math.max(
                    0,
                    mesesDisponiveis.indexOf(mesSelecionado)
                );

                instrucaoCalendario.textContent = (
                    datas.length
                    ? 'Dias destacados possuem horários disponíveis.'
                    : 'Esta sala não possui horários completos disponíveis.'
                );

                renderizarCalendario();
                renderizarHorarios();
            }

            botaoAnterior.addEventListener('click', function () {
                if (indiceMes > 0) {
                    indiceMes -= 1;
                    renderizarCalendario();
                }
            });

            botaoProximo.addEventListener('click', function () {
                if (indiceMes < mesesDisponiveis.length - 1) {
                    indiceMes += 1;
                    renderizarCalendario();
                }
            });

            campoEspaco.addEventListener('change', function () {
                carregarEspaco(false);
            });

            formulario.addEventListener('submit', function (evento) {
                if (!lerDataHora(grupoInicio) || !lerDataHora(grupoFim)) {
                    evento.preventDefault();
                    mostrarRetorno(
                        formulario,
                        'Selecione a sala, o dia e um horário disponível.',
                        'warning'
                    );
                    seletor.scrollIntoView({behavior: 'smooth', block: 'start'});
                }
            });

            const inicioInicial = lerDataHora(grupoInicio);
            const fimInicial = lerDataHora(grupoFim);

            if (inicioInicial && fimInicial) {
                dataSelecionada = [
                    inicioInicial.getFullYear(),
                    doisDigitos(inicioInicial.getMonth() + 1),
                    doisDigitos(inicioInicial.getDate())
                ].join('-');
            }

            carregarEspaco(true);

            if (inicioInicial && fimInicial) {
                confirmacaoInicio.textContent = new Intl.DateTimeFormat(
                    'pt-BR',
                    {
                        day: '2-digit', month: '2-digit', year: 'numeric',
                        hour: '2-digit', minute: '2-digit'
                    }
                ).format(inicioInicial);
                confirmacaoFim.textContent = new Intl.DateTimeFormat(
                    'pt-BR',
                    {
                        day: '2-digit', month: '2-digit', year: 'numeric',
                        hour: '2-digit', minute: '2-digit'
                    }
                ).format(fimInicial);
            }
        }
    );

}());
