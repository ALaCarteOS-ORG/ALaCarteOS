from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
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
    timp_preparare_min = models.PositiveIntegerField(default=15, help_text="Timp estimat de preparare în minute")

    def __str__(self):
        return self.nume

    def verifica_disponibilitate(self):
        """
        Verifică dacă toate ingredientele din rețetă sunt disponibile
        în cantitate suficientă pentru cel puțin o porție.
        Returnează (disponibil: bool, ingrediente_lipsa: list)
        """
        ingrediente_lipsa = []
        reteta = self.ingrediente_reteta.select_related('ingredient').all()
        
        # Dacă produsul nu are rețetă definită, rămâne disponibil
        if not reteta.exists():
            return True, []
        
        for ir in reteta:
            if ir.ingredient.cantitate_stoc < ir.cantitate_necesara:
                ingrediente_lipsa.append({
                    'ingredient': ir.ingredient.nume,
                    'stoc_actual': float(ir.ingredient.cantitate_stoc),
                    'necesar_portie': float(ir.cantitate_necesara),
                    'unitate': ir.ingredient.unitate_masura
                })
        
        return len(ingrediente_lipsa) == 0, ingrediente_lipsa

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

    def scade_stocuri(self):
        """
        Scade cantitățile de ingrediente din stoc pentru toate
        produsele din această comandă. Rulează la trecerea în status 'servita'.
        
        Returnează un dict cu:
        - 'ingrediente_sub_prag': ingrediente care au scăzut sub pragul de alertă
        - 'produse_dezactivate': produse dezactivate automat (Auto-86)
        """
        ingrediente_sub_prag_dict = {}
        produse_dezactivate = []
        ingrediente_modificate = set()  # Evităm verificări duplicate
        
        for element in self.elemente.select_related('produs').all():
            reteta = element.produs.ingrediente_reteta.select_related('ingredient').all()
            
            for ir in reteta:
                # Scădem: cantitate_necesara * cantitate_comandata
                cantitate_de_scazut = ir.cantitate_necesara * Decimal(str(element.cantitate))
                ir.ingredient.cantitate_stoc = max(
                    Decimal('0.00'),
                    ir.ingredient.cantitate_stoc - cantitate_de_scazut
                )
                ir.ingredient.save()
                ingrediente_modificate.add(ir.ingredient.id)
                
                # Verificăm dacă a scăzut sub pragul de alertă
                if ir.ingredient.cantitate_stoc <= ir.ingredient.prag_alerta:
                    ingrediente_sub_prag_dict[ir.ingredient.id] = {
                        'id': ir.ingredient.id,
                        'nume': ir.ingredient.nume,
                        'stoc_ramas': float(ir.ingredient.cantitate_stoc),
                        'prag': float(ir.ingredient.prag_alerta),
                        'unitate': ir.ingredient.unitate_masura
                    }
        
        # AUTO-86: Verificăm toate produsele care folosesc ingredientele modificate
        if ingrediente_modificate:
            produse_afectate = Produs.objects.filter(
                ingrediente_reteta__ingredient__id__in=ingrediente_modificate,
                disponibil=True
            ).distinct()
            
            for produs in produse_afectate:
                este_disponibil, _ = produs.verifica_disponibilitate()
                if not este_disponibil:
                    produs.disponibil = False
                    produs.save()
                    produse_dezactivate.append({
                        'id': produs.id,
                        'nume': produs.nume
                    })
        
        return {
            'ingrediente_sub_prag': list(ingrediente_sub_prag_dict.values()),
            'produse_dezactivate': produse_dezactivate
        }

class ElementComanda(models.Model):
    comanda = models.ForeignKey(Comanda, related_name='elemente', on_delete=models.CASCADE)
    produs = models.ForeignKey(Produs, on_delete=models.CASCADE)
    cantitate = models.PositiveIntegerField(default=1)
    pret_unitar = models.DecimalField(max_digits=6, decimal_places=2)

    def __str__(self):
        return f"{self.cantitate} x {self.produs.nume}"
