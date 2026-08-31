(function () {
    'use strict';

    function normalizar(texto) {
        return texto
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .toLocaleLowerCase('pt-BR')
            .trim();
    }

    function iniciarAutocomplete(select, indice) {
        const opcoes = Array.from(select.options)
            .filter((opcao) => opcao.value)
            .map((opcao) => ({
                value: opcao.value,
                label: opcao.textContent.trim(),
                busca: normalizar(opcao.textContent),
            }));

        const minimo = Number(
            select.dataset.minLength || 2
        );

        const grupoCandidatos = (
            select.dataset.memberSourceGroup || ''
        );

        const valoresFixosMembro = new Set(
            (select.dataset.memberFixedValues || '')
                .split(',')
                .map((valor) => valor.trim())
                .filter(Boolean)
        );

        const valoresExcluidos = new Set(
            (select.dataset.excludedValues || '')
                .split(',')
                .map((valor) => valor.trim())
                .filter(Boolean)
        );

        const eraObrigatorio = select.required;
        const idLista = `docente-resultados-${indice}`;

        const wrapper = document.createElement('div');

        wrapper.className = 'docente-autocomplete';

        const controle = document.createElement('div');

        controle.className = (
            'docente-autocomplete-controle'
        );

        const input = document.createElement('input');
        input.type = 'text';

        input.type = 'text';

        input.className = (
            'form-input docente-autocomplete-input'
        );

        input.placeholder = (
            select.dataset.placeholder
            || 'Digite o nome ou e-mail do docente'
        );

        input.autocomplete = 'off';

        input.setAttribute(
            'role',
            'combobox'
        );

        input.setAttribute(
            'aria-autocomplete',
            'list'
        );

        input.setAttribute(
            'aria-expanded',
            'false'
        );

        input.setAttribute(
            'aria-controls',
            idLista
        );

        const limpar = document.createElement('button');

        limpar.type = 'button';

        limpar.className = (
            'docente-autocomplete-limpar'
        );

        limpar.innerHTML = (
            '<svg viewBox="0 0 24 24" '
            + 'aria-hidden="true" focusable="false">'
            + '<path d="M7 7L17 17"></path>'
            + '<path d="M17 7L7 17"></path>'
            + '</svg>'
        );

        limpar.setAttribute(
            'aria-label',
            'Limpar docente selecionado'
        );

        const resultados = document.createElement('ul');

        resultados.id = idLista;

        resultados.className = (
            'docente-autocomplete-resultados'
        );

        resultados.setAttribute(
            'role',
            'listbox'
        );

        resultados.hidden = true;

        const aviso = document.createElement('small');

        aviso.className = (
            'docente-autocomplete-aviso'
        );

        aviso.textContent = (
            `Digite pelo menos ${minimo} letras `
            + 'e escolha uma sugestão.'
        );

        select.parentNode.insertBefore(
            wrapper,
            select
        );

        wrapper.appendChild(select);
        wrapper.appendChild(controle);
        wrapper.appendChild(resultados);
        wrapper.appendChild(aviso);

        controle.appendChild(input);
        controle.appendChild(limpar);

        select.required = false;
        input.required = eraObrigatorio;

        let indiceAtivo = -1;
        let resultadosAtuais = [];

        function opcaoSelecionada() {
            return opcoes.find(
                (opcao) => (
                    opcao.value === select.value
                )
            );
        }

        function atualizarBotaoLimpar() {
            limpar.hidden = !(
                input.value
                || select.value
            );
        }

        function atualizarValidade() {
            const digitouSemSelecionar = (
                input.value.trim()
                && !select.value
            );

            if (digitouSemSelecionar) {
                input.setCustomValidity(
                    'Escolha um docente na lista '
                    + 'de sugestões.'
                );

                return;
            }

            if (
                eraObrigatorio
                && !select.value
            ) {
                input.setCustomValidity(
                    'Selecione um docente.'
                );

                return;
            }

            input.setCustomValidity('');
        }

        function fecharResultados() {
            resultados.hidden = true;
            resultados.innerHTML = '';

            resultadosAtuais = [];
            indiceAtivo = -1;

            input.setAttribute(
                'aria-expanded',
                'false'
            );

            input.removeAttribute(
                'aria-activedescendant'
            );
        }

        function valoresSelecionadosNoGrupo() {
            if (!grupoExclusivo) {
                return new Set();
            }

            const selecionados = new Set();

            document
                .querySelectorAll(
                    'select[data-exclusive-group="'
                    + grupoExclusivo
                    + '"]'
                )
                .forEach((outroSelect) => {
                    if (
                        outroSelect !== select
                        && outroSelect.value
                    ) {
                        selecionados.add(
                            outroSelect.value
                        );
                    }
                });

            return selecionados;
        }

        function valoresPermitidosComoMembro() {
            const permitidos = new Set(
                valoresFixosMembro
            );

            if (!grupoCandidatos) {
                return permitidos;
            }

            document
                .querySelectorAll(
                    'select[data-exclusive-group="'
                    + grupoCandidatos
                    + '"]'
                )
                .forEach((selectMembro) => {
                    if (selectMembro.value) {
                        permitidos.add(
                            selectMembro.value
                        );
                    }
                });

            return permitidos;
        }

        function limparSelecao(
            devolverFoco = true
        ) {
            select.value = '';
            input.value = '';

            select.dispatchEvent(
                new Event(
                    'change',
                    {
                        bubbles: true,
                    }
                )
            );

            atualizarBotaoLimpar();
            atualizarValidade();
            fecharResultados();

            if (devolverFoco) {
                input.focus();
            }
        }

        function escolher(opcao) {
            select.value = opcao.value;
            input.value = opcao.label;

            select.dispatchEvent(
                new Event(
                    'change',
                    {
                        bubbles: true,
                    }
                )
            );

            atualizarBotaoLimpar();
            atualizarValidade();
            fecharResultados();
        }

        function destacar(novoIndice) {
            const botoes = (
                resultados.querySelectorAll(
                    '.docente-autocomplete-opcao'
                )
            );

            botoes.forEach((botao) => {
                botao.classList.remove('ativa');

                botao.setAttribute(
                    'aria-selected',
                    'false'
                );
            });

            if (!botoes.length) {
                indiceAtivo = -1;
                return;
            }

            indiceAtivo = (
                novoIndice + botoes.length
            ) % botoes.length;

            const ativo = botoes[indiceAtivo];

            ativo.classList.add('ativa');

            ativo.setAttribute(
                'aria-selected',
                'true'
            );

            ativo.scrollIntoView({
                block: 'nearest',
            });

            input.setAttribute(
                'aria-activedescendant',
                ativo.id
            );
        }

        function mostrarResultados() {
            const termo = normalizar(
                input.value
            );

            if (termo.length < minimo) {
                fecharResultados();
                return;
            }

            const membrosPermitidos = (
                valoresPermitidosComoMembro()
            );

            resultadosAtuais = opcoes
                .filter((opcao) => (
                    opcao.busca.includes(termo)
                    && !valoresExcluidos.has(
                        opcao.value
                    )
                    && !selecionadosNoGrupo.has(
                        opcao.value
                    )
                    && (
                        !grupoCandidatos
                        || membrosPermitidos.has(
                            opcao.value
                        )
                    )
                ))
                .slice(0, 10);

            resultados.innerHTML = '';
            indiceAtivo = -1;

            if (!resultadosAtuais.length) {
                const item = (
                    document.createElement('li')
                );

                item.className = (
                    'docente-autocomplete-aviso'
                );

                item.textContent = (
                    grupoCandidatos
                        ? 'Nenhum integrante encontrado.'
                        : 'Nenhum docente encontrado.'
                );

                resultados.appendChild(item);
            } else {
                resultadosAtuais.forEach(
                    (
                        opcao,
                        opcaoIndice
                    ) => {
                        const item = (
                            document.createElement(
                                'li'
                            )
                        );

                        const botao = (
                            document.createElement(
                                'button'
                            )
                        );

                        botao.type = 'button';

                        botao.id = (
                            `${idLista}-opcao-`
                            + opcaoIndice
                        );

                        botao.className = (
                            'docente-autocomplete-opcao'
                        );

                        botao.textContent = (
                            opcao.label
                        );

                        botao.setAttribute(
                            'role',
                            'option'
                        );

                        botao.setAttribute(
                            'aria-selected',
                            'false'
                        );

                        botao.addEventListener(
                            'mousedown',
                            (evento) => {
                                evento.preventDefault();
                            }
                        );

                        botao.addEventListener(
                            'click',
                            () => {
                                escolher(opcao);
                                input.focus();
                            }
                        );

                        item.appendChild(botao);

                        resultados.appendChild(
                            item
                        );
                    }
                );
            }

            resultados.hidden = false;

            input.setAttribute(
                'aria-expanded',
                'true'
            );
        }

        const selecionadaInicial = (
            opcaoSelecionada()
        );

        if (selecionadaInicial) {
            input.value = (
                selecionadaInicial.label
            );
        }

        atualizarBotaoLimpar();
        atualizarValidade();

        input.addEventListener(
            'input',
            () => {
                const selecionada = (
                    opcaoSelecionada()
                );

                if (
                    selecionada
                    && input.value
                    !== selecionada.label
                ) {
                    select.value = '';

                    select.dispatchEvent(
                        new Event(
                            'change',
                            {
                                bubbles: true,
                            }
                        )
                    );
                }

                atualizarBotaoLimpar();
                atualizarValidade();
                mostrarResultados();
            }
        );

        input.addEventListener(
            'focus',
            () => {
                if (
                    normalizar(
                        input.value
                    ).length >= minimo
                    && !select.value
                ) {
                    mostrarResultados();
                }
            }
        );

        input.addEventListener(
            'keydown',
            (evento) => {
                if (
                    evento.key === 'ArrowDown'
                    || evento.key === 'ArrowUp'
                ) {
                    evento.preventDefault();

                    if (resultados.hidden) {
                        mostrarResultados();
                    }

                    destacar(
                        indiceAtivo
                        + (
                            evento.key
                            === 'ArrowDown'
                                ? 1
                                : -1
                        )
                    );
                }

                if (
                    evento.key === 'Enter'
                    && indiceAtivo >= 0
                    && resultadosAtuais[
                        indiceAtivo
                    ]
                ) {
                    evento.preventDefault();

                    escolher(
                        resultadosAtuais[
                            indiceAtivo
                        ]
                    );
                }

                if (evento.key === 'Escape') {
                    fecharResultados();
                }
            }
        );

        limpar.addEventListener(
            'click',
            () => {
                limparSelecao();
            }
        );

        document.addEventListener(
            'change',
            (evento) => {
                if (
                    !grupoCandidatos
                    || !evento.target.matches(
                        'select[data-exclusive-group="'
                        + grupoCandidatos
                        + '"]'
                    )
                ) {
                    return;
                }

                const membrosPermitidos = (
                    valoresPermitidosComoMembro()
                );

                if (
                    select.value
                    && !membrosPermitidos.has(
                        select.value
                    )
                ) {
                    limparSelecao(false);
                    return;
                }

                if (!resultados.hidden) {
                    mostrarResultados();
                }
            }
        );

        document.addEventListener(
            'click',
            (evento) => {
                if (
                    !wrapper.contains(
                        evento.target
                    )
                ) {
                    fecharResultados();
                }
            }
        );

        if (select.form) {
            select.form.addEventListener(
                'submit',
                () => {
                    atualizarValidade();
                }
            );
        }
    }

    document.addEventListener(
        'DOMContentLoaded',
        () => {
            document
                .querySelectorAll(
                    'select.js-docente-autocomplete'
                )
                .forEach(
                    (
                        select,
                        indice
                    ) => {
                        iniciarAutocomplete(
                            select,
                            indice
                        );
                    }
                );
        }
    );
}());