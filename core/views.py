import json
import os
import random
from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone
from django.core.cache import cache
from .models import Produs, Comanda, ElementComanda, Masa, Ingredient

# === IMPORTURI PENTRU GEMINI SI .ENV ===
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from google import genai
from dotenv import load_dotenv

# 1. Încărcăm variabilele de mediu (inclusiv GEMINI_API_KEY)
load_dotenv(override=True)

# 2. Configurăm API-ul Google Gemini
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


# ===========================================================================
#  FUNCȚII UTILITARE — AGENT AI 2 (Tendințe & Date Operaționale)
# ===========================================================================

def calculeaza_tendinte():
    """
    Calculează tendințele de cerere pentru fiecare produs,
    comparând comenzile din ultimele 24h cu cele din ziua precedentă.
    Returnează o listă de dict-uri sortată descrescător după trend.
    """
    acum = timezone.now()
    ieri_start = acum - timedelta(hours=48)
    ieri_end = acum - timedelta(hours=24)
    azi_start = acum - timedelta(hours=24)

    # Comenzi din ultimele 24h (inclusiv cele servite, nu și anulate)
    comenzi_azi = ElementComanda.objects.filter(
        comanda__data_creare__gte=azi_start,
        comanda__data_creare__lte=acum
    ).exclude(comanda__status='anulata')

    # Comenzi din perioada anterioară (24-48h)
    comenzi_ieri = ElementComanda.objects.filter(
        comanda__data_creare__gte=ieri_start,
        comanda__data_creare__lte=ieri_end
    ).exclude(comanda__status='anulata')

    # Agregăm cantitățile per produs
    vanzari_azi = {}
    for elem in comenzi_azi.values('produs__id', 'produs__nume').annotate(total=Sum('cantitate')):
        vanzari_azi[elem['produs__id']] = {
            'nume': elem['produs__nume'],
            'cantitate': elem['total']
        }

    vanzari_ieri = {}
    for elem in comenzi_ieri.values('produs__id', 'produs__nume').annotate(total=Sum('cantitate')):
        vanzari_ieri[elem['produs__id']] = {
            'nume': elem['produs__nume'],
            'cantitate': elem['total']
        }

    # Calculăm tendința procentuală
    tendinte = []
    toate_produsele_ids = set(list(vanzari_azi.keys()) + list(vanzari_ieri.keys()))

    for prod_id in toate_produsele_ids:
        azi_data = vanzari_azi.get(prod_id, {})
        ieri_data = vanzari_ieri.get(prod_id, {})
        
        cantitate_azi = azi_data.get('cantitate', 0)
        cantitate_ieri = ieri_data.get('cantitate', 0)
        
        # Stabilim numele
        nume = azi_data.get('nume') or ieri_data.get('nume', 'N/A')
        
        # Calculăm procentajul
        if cantitate_ieri > 0:
            procent = round((cantitate_azi / cantitate_ieri) * 100)
        elif cantitate_azi > 0:
            procent = 200  # Produs nou sau fără istoric — creștere semnificativă
        else:
            procent = 100  # Fără date

        # Determinăm direcția
        if procent > 105:
            directie = 'up'
        elif procent < 95:
            directie = 'down'
        else:
            directie = 'stable'

        tendinte.append({
            'id': prod_id,
            'nume': nume,
            'procent': procent,
            'directie': directie,
            'cantitate_azi': cantitate_azi
        })

    # Sortăm descrescător după procent (cele mai populare primele)
    tendinte.sort(key=lambda x: x['procent'], reverse=True)
    
    # Returnăm top 6 (cele mai relevante)
    return tendinte[:6]


# ===========================================================================
#  PAGINI PRINCIPALE
# ===========================================================================

@login_required
def dashboard_staff(request):
    if request.user.is_staff or request.user.is_superuser or request.user.groups.filter(name__in=['Staff', 'Bucatar']).exists():
        
        # === ALGORITM PRIORITIZARE AUTOMATĂ ===
        # Marcăm ca "urgente" comenzile active mai vechi de 20 minute
        prag_timp = timezone.now() - timedelta(minutes=20)
        Comanda.objects.exclude(
            status__in=['servita', 'platita', 'anulata']
        ).filter(urgenta=False, data_creare__lte=prag_timp).update(urgenta=True)
        # ======================================

        comenzi = Comanda.objects.exclude(
            status__in=['servita', 'platita', 'anulata']
        ).order_by('-urgenta', 'data_creare').select_related('masa').prefetch_related('elemente__produs')
        
        ingrediente_alerta = Ingredient.objects.filter(
            cantitate_stoc__lte=F('prag_alerta')
        ).order_by('cantitate_stoc')
        
        produse_meniu = Produs.objects.all().order_by('nume')
        
        # AGENT AI 2: Tendințe dinamice calculate din date reale
        tendinte = calculeaza_tendinte()
        
        return render(request, 'staff.html', {
            'comenzi': comenzi,
            'ingrediente_alerta': ingrediente_alerta,
            'produse_meniu': produse_meniu,
            'tendinte': tendinte,
        })
    else:
        return HttpResponse("Acces interzis! Doar personalul autorizat are acces.", status=403)

def pagina_autentificare(request):
    return render(request, 'index.html')

def login_staff(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        parola = request.POST.get('password')
        
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

def logout_staff(request):
    logout(request)
    return redirect('autentificare')

def pagina_meniu(request, nr_masa=None):
    produse = Produs.objects.filter(disponibil=True)
    mese = Masa.objects.all()
    return render(request, 'meniu.html', {'produse': produse, 'mese': mese})


# ===========================================================================
#  AGENT AI 1 — Ospătar Virtual (Recomandări Clienți)
# ===========================================================================

@csrf_exempt
@require_POST
def ai_recomandare(request):
    try:
        # === MOD DEMO ===
        if settings.DEMO_MODE:
            produse_disponibile = Produs.objects.filter(disponibil=True).exclude(id__in=[int(item['id']) for item in json.loads(request.body).get('cart', [])])
            if not produse_disponibile.exists(): return JsonResponse({'error': 'Nu sunt alte produse disponibile'}, status=404)
            prod_final = random.choice(list(produse_disponibile))
            motiv = f"Pentru a completa perfect aromele, vă recomandăm {prod_final.nume}."
            return JsonResponse({
                'recomandare': motiv,
                'produs_recomandat': {'id': str(prod_final.id), 'nume': prod_final.nume, 'pret': float(prod_final.pret)}
            })
        # ================
        data = json.loads(request.body)
        cart_items = data.get('cart', [])
        
        if not cart_items:
            return JsonResponse({'error': 'Coș gol'}, status=400)
        
        nume_produse_cos = [item['name'] for item in cart_items]
        id_produse_cos = [int(item['id']) for item in cart_items]
        
        produse_disponibile = Produs.objects.filter(disponibil=True).exclude(id__in=id_produse_cos)
        
        if not produse_disponibile.exists():
             return JsonResponse({'error': 'Nu sunt alte produse disponibile'}, status=404)
             
        meniu_text = ", ".join([f"ID: {p.id} | Nume: {p.nume} | Tip: {p.tip_produs}" for p in produse_disponibile])
        
        # 3. Prompt-ul actualizat pentru Gemini - îi cerem explicit să nu folosească formatare
        prompt = (
            f"Sunt un somelier și ospătar virtual de top într-un restaurant fine-dining. "
            f"Clientul a adăugat în coș următoarele preparate: {', '.join(nume_produse_cos)}. "
            f"Alege UN SINGUR preparat complementar din acest meniu disponibil: [{meniu_text}]. "
            f"Dacă are friptură, sugerează vin roșu. Dacă are pizza, o bere artizanală, etc. "
            f"Răspunde STRICT cu un obiect JSON valid, fără formatare markdown, fără backticks (```), "
            f"doar structura brută, astfel: "
            f"{{\"id_produs\": ID_ales, \"motiv\": \"Argument scurt de ce se potrivește\"}}"
        )
        
        # 4. Generăm răspunsul cu modelul rapid de la Gemini
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        
        # 5. Curățăm textul (evităm eroarea clasică de formatare a AI-urilor cu ```json)
        raw_text = response.text.strip()
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_text:
            parts = raw_text.split("```")
            if len(parts) >= 3:
                raw_text = parts[1].strip()
            
        # 6. Extragem datele cu sistem de protecție la erori
        try:
            rezultat_ai = json.loads(raw_text)
        except json.JSONDecodeError:
            # Dacă AI-ul s-a încurcat și nu a returnat JSON, alegem primul produs disponibil
            prod_final = produse_disponibile.first()
            return JsonResponse({
                'recomandare': f"Pentru a echilibra perfect comanda, vă recomandăm să adăugați {prod_final.nume}.",
                'produs_recomandat': {'id': str(prod_final.id), 'nume': prod_final.nume, 'pret': float(prod_final.pret)}
            })
        
        prod_id = rezultat_ai.get('id_produs')
        motiv = rezultat_ai.get('motiv', 'O alegere excelentă!')
        
        try:
            prod_final = Produs.objects.get(id=prod_id)
        except (Produs.DoesNotExist, ValueError, TypeError):
            prod_final = produse_disponibile.first()
        
        return JsonResponse({
            'recomandare': motiv,
            'produs_recomandat': {'id': str(prod_final.id), 'nume': prod_final.nume, 'pret': float(prod_final.pret)}
        })
        
    except Exception as e:
        error_msg = str(e)
        print(f"Eroare AI API: {error_msg}")
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
             # Fallback silentios de siguranta daca am ramas fara cereri
             prod_final = produse_disponibile.first()
             return JsonResponse({
                 'recomandare': f"Pentru a echilibra perfect comanda, vă recomandăm să adăugați {prod_final.nume}.",
                 'produs_recomandat': {'id': str(prod_final.id), 'nume': prod_final.nume, 'pret': float(prod_final.pret)}
             })
        return JsonResponse({'error': error_msg}, status=500)


# ===========================================================================
#  OPERAȚIUNI COMENZI
# ===========================================================================

@csrf_exempt
@require_POST
def plaseaza_comanda(request):
    try:
        data = json.loads(request.body)
        cart_items = data.get('cart', [])
        masa_id = data.get('masa_id')
        
        if not cart_items:
            return JsonResponse({'error': 'Coș gol'}, status=400)
            
        with transaction.atomic():
            masa = Masa.objects.filter(id=masa_id).first() if masa_id else None
            comanda = Comanda.objects.create(masa=masa, status='noua')
            
            total_comanda = Decimal('0.00')
            for item in cart_items:
                produs = Produs.objects.get(id=item['id'])
                cantitate = item['quantity']
                ElementComanda.objects.create(
                    comanda=comanda,
                    produs=produs,
                    cantitate=cantitate,
                    pret_unitar=produs.pret
                )
                total_comanda += produs.pret * cantitate
            
            comanda.total = total_comanda
            comanda.save()
            
        return JsonResponse({'comanda_id': comanda.id})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def schimba_status(request, id):
    """
    Schimbă statusul unei comenzi. Când statusul devine 'servita',
    AGENT AI 2 intervine automat:
    1. Scade stocurile ingredientelor din rețetele produselor servite
    2. Verifică dacă produse trebuie dezactivate automat (Auto-86)
    """
    try:
        data = json.loads(request.body)
        nou_status = data.get('status')
        
        with transaction.atomic():
            comanda = Comanda.objects.get(id=id)
            comanda.status = nou_status if nou_status else comanda.status
            comanda.save()
            
            # AGENT AI 2: Scădere stocuri la marcarea ca "Servită"
            rezultat_stocuri = None
            if nou_status == 'servita':
                rezultat_stocuri = comanda.scade_stocuri()
        
        response_data = {'success': True}
        
        if rezultat_stocuri:
            response_data['stocuri'] = rezultat_stocuri
            
            # Logare în terminal pentru vizibilitate
            if rezultat_stocuri['produse_dezactivate']:
                produse_names = [p['nume'] for p in rezultat_stocuri['produse_dezactivate']]
                print(f"[AUTO-86] Produse dezactivate automat: {', '.join(produse_names)}")
            if rezultat_stocuri['ingrediente_sub_prag']:
                for ing in rezultat_stocuri['ingrediente_sub_prag']:
                    print(f"[STOC ALERT] {ing['nume']}: {ing['stoc_ramas']} {ing['unitate']} (prag: {ing['prag']})")
        
        return JsonResponse(response_data)
    except Comanda.DoesNotExist:
        return JsonResponse({'error': 'Comanda nu a fost găsită'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ===========================================================================
#  AGENT AI 2 — Modulul "86" (Toggle Disponibilitate Produs)
# ===========================================================================

@csrf_exempt
@require_POST
def toggle_disponibilitate(request, id):
    """
    Activează/Dezactivează un produs din meniu direct din dashboard-ul staff.
    Înlocuiește nevoia de a accesa panoul Admin pentru Modulul 86.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Neautentificat'}, status=401)
        
    try:
        produs = Produs.objects.get(id=id)
        
        # Dacă încercăm să reactivăm, verificăm dacă stocurile permit
        data = json.loads(request.body) if request.body else {}
        nou_status = data.get('disponibil')
        
        if nou_status is not None:
            # Dacă vrem să-l activăm, verificăm stocurile
            if nou_status and not produs.disponibil:
                este_posibil, ingrediente_lipsa = produs.verifica_disponibilitate()
                if not este_posibil:
                    return JsonResponse({
                        'success': False,
                        'error': 'Nu se poate reactiva — stocuri insuficiente.',
                        'ingrediente_lipsa': ingrediente_lipsa
                    }, status=400)
            
            produs.disponibil = nou_status
        else:
            # Toggle simplu
            if not produs.disponibil:
                este_posibil, ingrediente_lipsa = produs.verifica_disponibilitate()
                if not este_posibil:
                    return JsonResponse({
                        'success': False,
                        'error': 'Nu se poate reactiva — stocuri insuficiente.',
                        'ingrediente_lipsa': ingrediente_lipsa
                    }, status=400)
            produs.disponibil = not produs.disponibil
        
        produs.save()
        
        return JsonResponse({
            'success': True,
            'produs_id': produs.id,
            'produs_nume': produs.nume,
            'disponibil': produs.disponibil
        })
    except Produs.DoesNotExist:
        return JsonResponse({'error': 'Produsul nu a fost găsit'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ===========================================================================
#  AGENT AI 2 — Predicții Operaționale Gemini
# ===========================================================================

@login_required
def ai_predictie_kds(request):
    """
    Endpoint care folosește Gemini pentru a genera predicții operaționale
    bazate pe datele curente ale restaurantului: comenzi active, stocuri,
    tendințe, ora zilei. Răspunde cu text de predicție și sugestii.
    """
    # Colectăm datele operaționale indiferent de mod
    acum = timezone.now()
    ora_curenta = acum.strftime("%H:%M")
    comenzi_active = Comanda.objects.exclude(status__in=['servita', 'platita', 'anulata']).count()
    tendinte = calculeaza_tendinte()

    # === MOD DEMO ===
    if settings.DEMO_MODE:
        predictie_mock = f"Atenție la stația grill, cererea pentru {tendinte[0]['nume']} este în creștere." if tendinte else "Fluxul de comenzi este constant. Mențineți ritmul."
        rezultat_final = {
            'success': True, 'predictie': predictie_mock,
            'statie_recomandata': 'grill' if tendinte and 'friptura' in tendinte[0]['nume'].lower() else 'generală',
            'nivel_alerta': 'mediu' if comenzi_active > 5 else 'scazut', 'ora_generare': ora_curenta,
            'tendinte_sumar': [{'nume': t['nume'], 'procent': t['procent'], 'directie': t['directie']} for t in tendinte[:4]]
        }
        return JsonResponse(rezultat_final)
    # ================
    try:
        # 1. Colectăm datele operaționale
        acum = timezone.now()
        ora_curenta = acum.strftime("%H:%M")
        zi_saptamana = ['Luni', 'Marți', 'Miercuri', 'Joi', 'Vineri', 'Sâmbătă', 'Duminică'][acum.weekday()]
        
        # --- CACHE CHECK (Protejăm limitele gratuite API) ---
        cached_data = cache.get('ai_kds_predictie')
        if cached_data:
            # Returnăm predictia salvată anterior, doar îi actualizăm ora afișată
            cached_data['ora_generare'] = ora_curenta
            return JsonResponse(cached_data)
        # ----------------------------------------------------

        # Comenzi active
        # (Mutat mai sus pentru a fi disponibil și în Modul Demo)
        tendinte = calculeaza_tendinte()
        top_produse = ", ".join([f"{t['nume']} ({t['cantitate_azi']} porții, {t['procent']}%)" for t in tendinte[:4]]) if tendinte else "Fără date suficiente"
        
        # Stocuri critice
        stocuri_critice = Ingredient.objects.filter(
            cantitate_stoc__lte=F('prag_alerta')
        ).values_list('nume', flat=True)
        stocuri_text = ", ".join(stocuri_critice) if stocuri_critice else "Toate stocurile sunt OK"
        
        # Produse dezactivate (86-ed)
        produse_86 = Produs.objects.filter(disponibil=False).values_list('nume', flat=True)
        produse_86_text = ", ".join(produse_86) if produse_86 else "Niciun produs dezactivat"
        
        # 2. Construim prompt-ul pentru Gemini
        prompt = (
            f"Ești un asistent AI de management pentru un restaurant fine-dining. "
            f"Analizează următoarele date operaționale și oferă O SINGURĂ predicție concisă "
            f"(maxim 2 propoziții) pentru echipa de bucătari:\n\n"
            f"- Ziua: {zi_saptamana}, Ora: {ora_curenta}\n"
            f"- Comenzi active acum: {comenzi_active}\n"
            f"- Tendințe produse (ultimele 24h vs. ieri): {top_produse}\n"
            f"- Ingrediente cu stoc critic: {stocuri_text}\n"
            f"- Produse indisponibile (86): {produse_86_text}\n\n"
            f"Răspunde STRICT cu un obiect JSON valid, fără formatare markdown, fără backticks, "
            f"doar structura brută, astfel: "
            f"{{\"predictie\": \"Textul predicției scurt și acționabil\", "
            f"\"statie_recomandata\": \"numele stației de pregătit care va fi cel mai solicitată\", "
            f"\"nivel_alerta\": \"scazut/mediu/ridicat\"}}"
        )
        
        # 3. Generăm răspunsul cu Gemini
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        
        raw_text = response.text.strip()
        # Curățăm markdown dacă este cazul
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_text:
            parts = raw_text.split("```")
            if len(parts) >= 3:
                raw_text = parts[1].strip()
        
        try:
            rezultat = json.loads(raw_text)
        except json.JSONDecodeError:
            # Fallback inteligent bazat pe date
            rezultat = {
                'predictie': f"Aveți {comenzi_active} comenzi active. Monitorizați stocurile critice.",
                'statie_recomandata': 'generală',
                'nivel_alerta': 'mediu' if comenzi_active > 5 else 'scazut'
            }
        
        rezultat_final = {
            'success': True,
            'predictie': rezultat.get('predictie', ''),
            'statie_recomandata': rezultat.get('statie_recomandata', ''),
            'nivel_alerta': rezultat.get('nivel_alerta', 'scazut'),
            'ora_generare': ora_curenta,
            'tendinte_sumar': [{'nume': t['nume'], 'procent': t['procent'], 'directie': t['directie']} for t in tendinte[:4]]
        }
        
        # Salvăm rezultatul în memorie pentru 15 minute (900 secunde)
        cache.set('ai_kds_predictie', rezultat_final, 900)
        
        return JsonResponse(rezultat_final)
        
    except Exception as e:
        error_msg = str(e)
        print(f"[AI KDS] Eroare predicție: {error_msg}")
        
        predictie_fallback = 'Sistemul AI este temporar indisponibil. Monitorizați manual comenzile.'
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            predictie_fallback = 'Limita zilnică AI atinsă. Folosim rutine standard de KDS.'

        return JsonResponse({
            'success': False,
            'error': error_msg,
            'predictie': predictie_fallback
        }, status=500)

@login_required
def ai_raport_zi(request):
    """
    Generăm Raportul de Sfârșit de Zi: AI-ul analizează volumele zilei curente 
    (vânzări, încasări, produse de top, stocuri) și generează un text structurat.
    """
    try:
        # Colectăm datele zilei curente indiferent de mod
        azi_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        comenzi_azi = Comanda.objects.filter(data_creare__gte=azi_start)
        total_comenzi = comenzi_azi.count()
        comenzi_anulate = comenzi_azi.filter(status='anulata').count()
        comenzi_finalizate = comenzi_azi.filter(status__in=['servita', 'platita'])
        venit_total = comenzi_finalizate.aggregate(total_venit=Sum('total'))['total_venit'] or 0
        elemente_azi = ElementComanda.objects.filter(comanda__in=comenzi_finalizate)
        top_produse = elemente_azi.values('produs__nume').annotate(cantitate_totala=Sum('cantitate')).order_by('-cantitate_totala')[:3]
        top_produse_text = ", ".join([f"{p['produs__nume']} ({p['cantitate_totala']} porții)" for p in top_produse]) if top_produse else "Nu există date de vânzări"
        stocuri_critice = Ingredient.objects.filter(cantitate_stoc__lte=F('prag_alerta')).values_list('nume', flat=True)
        stocuri_text = ", ".join(stocuri_critice) if stocuri_critice else "Toate stocurile sunt în parametri optimi."

        # === MOD DEMO ===
        if settings.DEMO_MODE:
            raport_mock = (f"**1. Rezumatul Vânzărilor**\nO zi productivă! Am procesat un total de **{total_comenzi} comenzi**, cu un venit estimat de **{venit_total:.2f} Lei**. Numărul de comenzi anulate a fost de {comenzi_anulate}, un indicator bun al eficienței operaționale.\n\n**2. Performanța Meniului**\nVedetele zilei au fost: **{top_produse_text}**. Aceste preparate continuă să fie preferatele clienților noștri.\n\n**3. Atenționări pentru Mâine**\nPentru a asigura un flux lin mâine, vă rog să acordați atenție următoarelor stocuri: **{stocuri_text}**. Recomandăm aprovizionarea prioritară a acestora.")
            return JsonResponse({'success': True, 'raport': raport_mock})
        # ================
        # 1. Colectăm datele zilei curente (de la ora 00:00 la ora curentă)
        azi_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        comenzi_azi = Comanda.objects.filter(data_creare__gte=azi_start)
        
        total_comenzi = comenzi_azi.count()
        comenzi_anulate = comenzi_azi.filter(status='anulata').count()
        comenzi_finalizate = comenzi_azi.filter(status__in=['servita', 'platita'])
        
        venit_total = comenzi_finalizate.aggregate(total_venit=Sum('total'))['total_venit'] or 0
        
        # Cele mai vândute produse de azi
        elemente_azi = ElementComanda.objects.filter(comanda__in=comenzi_finalizate)
        top_produse = elemente_azi.values('produs__nume').annotate(cantitate_totala=Sum('cantitate')).order_by('-cantitate_totala')[:3]
        top_produse_text = ", ".join([f"{p['produs__nume']} ({p['cantitate_totala']} porții)" for p in top_produse]) if top_produse else "Nu există date de vânzări"

        # Probleme stoc
        stocuri_critice = Ingredient.objects.filter(cantitate_stoc__lte=F('prag_alerta')).values_list('nume', flat=True)
        stocuri_text = ", ".join(stocuri_critice) if stocuri_critice else "Toate stocurile sunt în parametri optimi."

        # 2. Construim prompt-ul
        prompt = (
            f"Ești managerul asistent (Agent AI) al unui restaurant fine-dining. Generează un raport executiv scurt, prietenos dar profesional, pentru sfârșitul zilei.\n\n"
            f"Datele de astăzi:\n"
            f"- Total comenzi procesate: {total_comenzi} (din care {comenzi_anulate} anulate)\n"
            f"- Venit total generat (din comenzile servite/plătite): {venit_total} Lei\n"
            f"- Top 3 cele mai vândute produse astăzi: {top_produse_text}\n"
            f"- Situația stocurilor pentru mâine: {stocuri_text}\n\n"
            f"Structurează raportul în 3 paragrafe scurte cu titluri (ex: 1. Rezumatul Vânzărilor, 2. Performanța Meniului, 3. Atenționări pentru Mâine). Fii concis."
        )

        # 3. Apelăm Gemini
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        
        return JsonResponse({'success': True, 'raport': response.text})
        
    except Exception as e:
        error_msg = str(e)
        print(f"[AI Raport] Eroare: {error_msg}")
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            return JsonResponse({'success': False, 'error': 'Limita gratuită a modelului AI a fost atinsă temporar. Te rugăm să aștepți sau să încerci din nou mai târziu.'}, status=429)
        return JsonResponse({'success': False, 'error': error_msg}, status=500)