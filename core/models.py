from django.db import models
from django.contrib.auth.models import User
import uuid

class ProfilStaff(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    nume_angajat = models.CharField(max_length=100)
    rol = models.CharField(
        max_length=20, 
        choices=[('ospatar', 'Ospătar'), ('bucatar', 'Bucătar'), ('admin', 'Admin')],
        default='ospatar'
    )

    def __str__(self):
        return f"{self.nume_angajat} - {self.get_rol_display()}"

class Masa(models.Model):
    nr_masa = models.IntegerField(unique=True)
    token_qr = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    def __str__(self):
        return f"Masa {self.nr_masa}"

class Produs(models.Model):
    nume = models.CharField(max_length=100)
    descriere = models.TextField()
    pret = models.DecimalField(max_digits=6, decimal_places=2)
    tip_produs = models.CharField(max_length=100, null=True, blank=True)
    imagine_url = models.URLField(blank=True, null=True, default='https://via.placeholder.com/400x300?text=Fara+Imagine')
    disponibil = models.BooleanField(default=True)

    def __str__(self):
        return self.nume

class Ingredient(models.Model):
    nume = models.CharField(max_length=100)
    cantitate_stoc = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    unitate_masura = models.CharField(max_length=20, help_text="ex: g, ml, buc")
    prag_alerta = models.DecimalField(max_digits=10, decimal_places=2, default=10.00, help_text="Notifică când stocul scade sub această valoare")

    def __str__(self):
        return f"{self.nume} - Stoc: {self.cantitate_stoc} {self.unitate_masura}"

class IngredientReteta(models.Model):
    produs = models.ForeignKey(Produs, related_name='ingrediente_reteta', on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    cantitate_necesara = models.DecimalField(max_digits=10, decimal_places=2, help_text="Cantitatea necesară pentru o porție")

    def __str__(self):
        return f"{self.cantitate_necesara} {self.ingredient.unitate_masura} {self.ingredient.nume} -> {self.produs.nume}"

class Comanda(models.Model):
    masa = models.ForeignKey(Masa, on_delete=models.SET_NULL, null=True, blank=True)
    data_creare = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, default='in_asteptare')
    urgenta = models.BooleanField(default=False)

    def __str__(self):
        return f"Comanda #{self.id} - {self.total} Lei"

class ElementComanda(models.Model):
    comanda = models.ForeignKey(Comanda, related_name='elemente', on_delete=models.CASCADE)
    produs = models.ForeignKey(Produs, on_delete=models.CASCADE)
    cantitate = models.PositiveIntegerField(default=1)
    pret_unitar = models.DecimalField(max_digits=6, decimal_places=2)

    def __str__(self):
        return f"{self.cantitate} x {self.produs.nume}"
