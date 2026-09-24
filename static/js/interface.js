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

}());
