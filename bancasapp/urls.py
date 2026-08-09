from django.urls import path
from . import views

urlpatterns = [
    # Caminho vazio '' significa a página principal (ex: localhost:8000/)
    path('', views.login_view, name='login'),
    path('dashboard/', views.dashboard, name='dashboard'),
    # Ex: localhost:8000/bancas/
    path('bancas/', views.visualizar_bancas, name='visualizar_bancas'),
    # Ex: localhost:8000/solicitar/
    path('solicitar/', views.solicitar_banca, name='solicitar_banca'),
    path('cadastrar/aluno/', views.cadastrar_aluno, name='cadastrar_aluno'),
    path('cadastrar/projeto/', views.cadastrar_projeto, name='cadastrar_projeto'),
    path('avaliar/<int:solicitacao_id>/<str:acao>/', views.avaliar_solicitacao, name='avaliar_solicitacao'),
    path('meus-tccs/', views.meus_tccs, name='meus_tccs'),
    path('pesquisar/', views.pesquisar, name='pesquisar'),
    path('documentos/', views.documentos, name='documentos'),
    path('documentos/<int:modelo_id>/download/', views.baixar_documento, name='baixar_documento'),
]