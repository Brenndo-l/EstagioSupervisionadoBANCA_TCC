from django.urls import path
from . import views

urlpatterns = [
    # Caminho vazio '' significa a página principal (ex: localhost:8000/)
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Ex: localhost:8000/bancas/
    path('bancas/', views.visualizar_bancas, name='visualizar_bancas'),
    
    # Ex: localhost:8000/solicitar/
    path('solicitar/', views.solicitar_banca, name='solicitar_banca'),

    path('', views.login_view, name="login")
]