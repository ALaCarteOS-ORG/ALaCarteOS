from django.contrib import admin
from .models import Produs, Comanda, ElementComanda, Masa, ProfilStaff, Ingredient, IngredientReteta

admin.site.register(Produs)
admin.site.register(Comanda)
admin.site.register(ElementComanda)
admin.site.register(Masa)
admin.site.register(ProfilStaff)
admin.site.register(Ingredient)
admin.site.register(IngredientReteta)
