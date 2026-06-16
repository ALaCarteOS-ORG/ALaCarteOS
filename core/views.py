import json
import os
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.db import transaction
from django.db.models import F
from .models import Produs, Comanda, ElementComanda, Masa, Ingredient

# === IMPORTURI NOI PENTRU GEMINI SI .ENV ===
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from google import genai
from dotenv import load_dotenv

# 1. Încărcăm variabilele de mediu (inclusiv GEMINI_API_KEY)
load_dotenv()

# 2. Configurăm API-ul Google Gemini
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

@login_required
def dashboard_staff(request):
    if request.user.is_staff or request.user.is_superuser or request.user.groups.filter(name__in=['Staff', 'Bucatar']).exists():
        comenzi = Comanda.objects.exclude(status__in=['servita', 'platita', 'anulata']).order_by('-urgenta', 'data_creare').select_related('masa').prefetch_related('elemente__produs')
        
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
    mese = Masa.objects.all()
    return render(request, 'meniu.html', {'produse': produse, 'mese': mese})

@csrf_exempt
@require_POST
def ai_recomandare(request):
    try:
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
            raw_text = raw_text.split("```json").split("```")[0].strip()
        elif "```" in raw_text:
            raw_text = raw_text.split("```")[1].split("```").strip()
            
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
        print(f"Eroare AI API: {str(e)}") # Pentru vizibilitate în terminal
        return JsonResponse({'error': str(e)}, status=500)

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
            
            for item in cart_items:
                produs = Produs.objects.get(id=item['id'])
                ElementComanda.objects.create(
                    comanda=comanda,
                    produs=produs,
                    cantitate=item['quantity']
                )
        return JsonResponse({'comanda_id': comanda.id})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_POST
def schimba_status(request, id):
    try:
        data = json.loads(request.body)
        comanda = Comanda.objects.get(id=id)
        comanda.status = data.get('status', comanda.status)
        comanda.save()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)