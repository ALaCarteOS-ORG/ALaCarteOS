import json
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.db import transaction
from django.db.models import F
from .models import Produs, Comanda, ElementComanda, Masa, Ingredient

@login_required # Doar cei logați pot vedea
def dashboard_staff(request):
    # Verificăm dacă face parte din staff (am lăsat și grupul Bucatar pentru compatibilitate cu setările vechi)
    if request.user.is_staff or request.user.is_superuser or request.user.groups.filter(name__in=['Staff', 'Bucatar']).exists():
        # Preluăm comenzile active și aducem optimizat informațiile despre Masă pe ecranul KDS
        comenzi = Comanda.objects.exclude(status__in=['servita', 'platita', 'anulata']).order_by('-urgenta', 'data_creare').select_related('masa').prefetch_related('elemente__produs')
        
        # Extragem ingredientele aflate la limita stocului și produsele pentru Modulul 86
        ingrediente_alerta = Ingredient.objects.filter(cantitate_stoc__lte=F('prag_alerta')).order_by('cantitate_stoc')
        produse_meniu = Produs.objects.all().order_by('nume')
        
        return render(request, 'staff.html', {'comenzi': comenzi, 'ingrediente_alerta': ingrediente_alerta, 'produse_meniu': produse_meniu})
    else:
        return HttpResponse("Acces interzis! Doar personalul autorizat are acces.", status=403)

def pagina_autentificare(request):
    return render(request, 'index.html')

def login_staff(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        parola = request.POST.get('password')
        
        # Verificăm datele în baza de date
        user = authenticate(request, username=username, password=parola)
        
        if user is not None:
            if user.is_staff or user.is_superuser or user.groups.filter(name__in=['Staff', 'Bucatar']).exists():
                login(request, user)
                return redirect('staff_dashboard')
            else:
                messages.error(request, 'Acces interzis! Nu ai permisiuni de Staff.')
        else:
            messages.error(request, 'Date de autentificare incorecte (ID sau Parolă greșită).')
            
    return redirect('autentificare')

def pagina_meniu(request, nr_masa=None):
    produse = Produs.objects.filter(disponibil=True)
    mese = Masa.objects.all().order_by('nr_masa') # Trimitem lista de mese pentru selectia manuala
    masa = None
    if nr_masa:
        try:
            # Căutăm masa după numărul ei
            masa = Masa.objects.get(nr_masa=nr_masa)
        except Masa.DoesNotExist:
            # Aici poți decide ce faci dacă masa nu există: afișezi o eroare, redirecționezi etc.
            # Momentan, o vom ignora și va fi tratată ca o comandă "la pachet".
            pass
    return render(request, 'meniu.html', {'produse': produse, 'masa': masa, 'mese': mese})

def plaseaza_comanda(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            cart_items = data.get('cart', [])
            masa_id = data.get('masa_id') # Preluăm ID-ul mesei din cererea JavaScript
            
            if not cart_items:
                return JsonResponse({'error': 'Coșul este gol!'}, status=400)

            # Folosim transaction.atomic pentru a ne asigura că dacă o inserare eșuează, nu se salvează nimic pe jumătate
            with transaction.atomic():
                
                # Verificăm dacă am primit un ID de masă și dacă acesta corespunde unei mese reale
                masa_obj = None
                if masa_id:
                    try:
                        masa_obj = Masa.objects.get(id=masa_id)
                    except (Masa.DoesNotExist, ValueError):
                        # Dacă ID-ul mesei e invalid, comanda va fi fără masă (la pachet)
                        pass

                # Creăm comanda, legând-o de masă dacă a fost găsită
                comanda = Comanda.objects.create(total=0, masa=masa_obj)
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

@login_required
def schimba_status_comanda(request, comanda_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            nou_status = data.get('status')
            comanda = Comanda.objects.get(id=comanda_id)
            
            # Dacă statusul devine "in_preparare", scădem ingredientele din stoc
            if nou_status == 'in_preparare' and comanda.status not in ['in_preparare', 'servita']:
                with transaction.atomic():
                    for element in comanda.elemente.all():
                        for reteta in element.produs.ingrediente_reteta.all():
                            ingredient = reteta.ingredient
                            cantitate_totala = reteta.cantitate_necesara * element.cantitate
                            ingredient.cantitate_stoc -= cantitate_totala
                            ingredient.save()
            
            comanda.status = nou_status
            comanda.save()
            return JsonResponse({'success': True})
        except Comanda.DoesNotExist:
            return JsonResponse({'error': 'Comanda nu exista'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Metoda nepermisa'}, status=405)