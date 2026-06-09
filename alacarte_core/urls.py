from django.contrib import admin
from django.urls import path
from core import views # Importăm vederile din aplicația creată

urlpatterns = [
    path('', views.pagina_autentificare, name='autentificare'), # Pagina principala
    path('admin/', admin.site.urls),
    path('meniu/', views.pagina_meniu),
    path('staff/', views.dashboard_staff, name='staff_dashboard'),
    path('plaseaza-comanda/', views.plaseaza_comanda),
]