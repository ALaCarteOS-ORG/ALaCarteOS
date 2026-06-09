from django.db import models
from django.contrib.auth.models import User

class Produs(models.Model):
    nume = models.CharField(max_length=100)
    descriere = models.TextField()
    pret = models.DecimalField(max_digits=6, decimal_places=2)
    tip_produs = models.CharField(max_length=100, null=True, blank=True)
    imagine_url = models.URLField(blank=True, null=True, default='https://via.placeholder.com/400x300?text=Fara+Imagine')
    disponibil = models.BooleanField(default=True)

    def __str__(self):
        return self.nume

class Comanda(models.Model):
    data_creare = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, default='in_asteptare')

    def __str__(self):
        return f"Comanda #{self.id} - {self.total} Lei"

class ElementComanda(models.Model):
    comanda = models.ForeignKey(Comanda, related_name='elemente', on_delete=models.CASCADE)
    produs = models.ForeignKey(Produs, on_delete=models.CASCADE)
    cantitate = models.PositiveIntegerField(default=1)
    pret_unitar = models.DecimalField(max_digits=6, decimal_places=2)

    def __str__(self):
        return f"{self.cantitate} x {self.produs.nume}"

class ProfilStaff(models.Model):
    ROLURI = (
        ('ospatar', 'Ospătar'),
        ('bucatar', 'Bucătar'),
        ('admin', 'Admin'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profil_staff')
    nume_angajat = models.CharField(max_length=100)
    rol = models.CharField(max_length=20, choices=ROLURI)

    def __str__(self):
        return f"{self.nume_angajat} - {self.get_rol_display()}"
