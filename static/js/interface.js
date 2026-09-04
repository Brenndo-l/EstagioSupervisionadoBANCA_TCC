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

}());