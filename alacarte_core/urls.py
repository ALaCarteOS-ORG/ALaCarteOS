from django.contrib import admin
from django.urls import path
from core import views # Importăm vederile din aplicația creată

urlpatterns = [
    path('', views.pagina_autentificare, name='autentificare'), # Pagina principala
    path('admin/', admin.site.urls),
    path('login-staff/', views.login_staff, name='login_staff'),
    path('meniu/', views.pagina_meniu, name='meniu_general'),
    path('meniu/masa/<int:nr_masa>/', views.pagina_meniu, name='meniu_masa'),
    path('bucatarie/', views.dashboard_staff, name='staff_dashboard'),
    path('plaseaza-comanda/', views.plaseaza_comanda),
    path('schimba-status/<int:id>/', views.schimba_status),
    path('ai-recomandare/', views.ai_recomandare, name='ai_recomandare'),
    
    # === AGENT AI 2: Rute noi ===
    path('toggle-produs/<int:id>/', views.toggle_disponibilitate, name='toggle_produs'),
    path('ai-predictie-kds/', views.ai_predictie_kds, name='ai_predictie_kds'),
]