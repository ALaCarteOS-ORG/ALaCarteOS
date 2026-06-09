import json
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login
from django.db import transaction
from .models import Produs, Comanda, ElementComanda

@login_required # Doar cei logați pot vedea
def dashboard_bucatarie(request):
    # Verificăm dacă userul are un cont de staff asignat cu rolul potrivit
    este_staff = hasattr(request.user, 'profil_staff') and request.user.profil_staff.rol in ['bucatar', 'ospatar', 'admin']
    este_grup = request.user.groups.filter(name__in=['Bucatar', 'Ospatar']).exists()
    
    if este_staff or este_grup or request.user.is_superuser:
        # Aici conectăm template-ul de interfață creat de prietenul tău
        # (Presupunând că l-a numit 'dashboard_staff.html' și e în folderul templates)
        return render(request, 'dashboard_staff.html')
    else:
        return HttpResponse("N-ai voie aici, acces doar pentru staff!", status=403)

@login_required
def api_comenzi_live(request):
    """ Endpoint JSON folosit de interfața din frontend pentru a afișa live comenzile """
    este_staff = hasattr(request.user, 'profil_staff') and request.user.profil_staff.rol in ['bucatar', 'ospatar', 'admin']
    este_grup = request.user.groups.filter(name__in=['Bucatar', 'Ospatar']).exists()
    
    if not (este_staff or este_grup or request.user.is_superuser):
        return JsonResponse({'error': 'Neautorizat'}, status=403)
        
    comenzi = Comanda.objects.all().order_by('id')
    
    data = []
    for c in comenzi:
        articole = c.elementcomanda_set.all()
        articole_data = [{
            'produs_nume': a.produs.nume,
            'cantitate': a.cantitate,
        } for a in articole]
        
        data.append({
            'id': c.id,
            'total': c.total,
            'articole': articole_data
        })
        
    return JsonResponse({'comenzi': data})

@login_required
def sterge_comanda(request, comanda_id):
    """ Endpoint pentru a șterge din baza de date comenzile gata/servite """
    este_staff = hasattr(request.user, 'profil_staff') and request.user.profil_staff.rol in ['bucatar', 'ospatar', 'admin']
    este_grup = request.user.groups.filter(name__in=['Bucatar', 'Ospatar']).exists()
    
    if not (este_staff or este_grup or request.user.is_superuser):
        return JsonResponse({'error': 'Neautorizat'}, status=403)
        
    if request.method in ['POST', 'DELETE']:
        comanda = get_object_or_404(Comanda, id=comanda_id)
        comanda.delete()
        return JsonResponse({'success': True, 'message': 'Comanda a fost ștearsă cu succes.'})
        
    return JsonResponse({'error': 'Metodă nepermisă'}, status=405)

def pagina_autentificare(request):
    # Dacă ești deja logat, te trimite direct la interfața staff
    if request.user.is_authenticated:
        return redirect('/bucatarie/')
        
    if request.method == 'POST':
        utilizator = request.POST.get('username')
        parola = request.POST.get('password')
        user = authenticate(request, username=utilizator, password=parola)
        
        if user is not None:
            login(request, user)
            return redirect('/bucatarie/')
        else:
            return HttpResponse("<h3>Autentificare eșuată!</h3><p>Ai introdus greșit utilizatorul sau parola.</p><a href='/'>Întoarce-te și încearcă din nou.</a>", status=401)
            
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