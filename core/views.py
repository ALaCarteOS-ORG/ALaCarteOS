import json
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.db import transaction
from .models import Produs, Comanda, ElementComanda

@login_required # Doar cei logați pot vedea
def dashboard_staff(request):
    # Verificăm dacă face parte din staff (am lăsat și grupul Bucatar pentru compatibilitate cu setările vechi)
    if request.user.groups.filter(name='Staff').exists() or request.user.groups.filter(name='Bucatar').exists() or request.user.is_superuser:
        return render(request, 'staff.html')
    else:
        return HttpResponse("Acces interzis! Doar personalul autorizat are acces.", status=403)

def pagina_autentificare(request):
    return render(request, 'index.html')

def pagina_meniu(request):
    produse = Produs.objects.filter(disponibil=True)
    return render(request, 'meniu.html', {'produse': produse})

def plaseaza_comanda(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            cart_items = data.get('cart', [])
            
            if not cart_items:
                return JsonResponse({'error': 'Coșul este gol!'}, status=400)

            # Folosim transaction.atomic pentru a ne asigura că dacă o inserare eșuează, nu se salvează nimic pe jumătate
            with transaction.atomic():
                comanda = Comanda.objects.create(total=0)
                total_comanda = 0

                for item in cart_items:
                    produs = Produs.objects.get(id=item['id'])
                    cantitate = int(item['quantity'])
                    pret_unitar = produs.pret # Prețul este luat direct din DB, sigur și corect
                    
                    ElementComanda.objects.create(
                        comanda=comanda, produs=produs,
                        cantitate=cantitate, pret_unitar=pret_unitar
                    )
                    total_comanda += (pret_unitar * cantitate)
                
                comanda.total = total_comanda
                comanda.save()
            return JsonResponse({'success': True, 'comanda_id': comanda.id})
        except Produs.DoesNotExist:
            return JsonResponse({'error': 'Unul dintre produse nu mai există în meniu.'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Metodă nepermisă'}, status=405)