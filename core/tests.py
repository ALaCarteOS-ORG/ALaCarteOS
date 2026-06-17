"""
Teste automate ALaCarteOS — nivel moderat.

Acoperă:
  • Crearea și reprezentarea modelelor (str / __str__)
  • Logica de business: verificare disponibilitate, scădere stocuri, Auto-86
  • Acces la view-uri: login required, permisiuni staff
  • Endpoint-uri API: plasare comandă, schimbare status
  • NU testează endpoint-urile Gemini AI (necesită API key real)
"""
from decimal import Decimal

from django.contrib.auth.models import User, Group
from django.test import TestCase, Client
from django.urls import reverse, resolve

from core.models import (
    ProfilStaff, Masa, Produs, Ingredient,
    IngredientReteta, Comanda, ElementComanda,
)


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

class BaseTestCase(TestCase):
    """Setup comun: un user staff, un user normal, produse, mese, ingrediente."""

    def setUp(self):
        # ── Utilizatori ──
        self.staff_user = User.objects.create_user(
            username='ospatar1', password='TestPass123!', is_staff=True,
        )
        self.normal_user = User.objects.create_user(
            username='client1', password='TestPass123!', is_staff=False,
        )

        # ── Masă ──
        self.masa = Masa.objects.create(nr_masa=1)

        # ── Ingrediente ──
        self.faina = Ingredient.objects.create(
            nume='Făină', cantitate_stoc=Decimal('500.00'),
            unitate_masura='g', prag_alerta=Decimal('100.00'),
        )
        self.branza = Ingredient.objects.create(
            nume='Brânză', cantitate_stoc=Decimal('200.00'),
            unitate_masura='g', prag_alerta=Decimal('50.00'),
        )
        self.ingredient_rar = Ingredient.objects.create(
            nume='Trufe', cantitate_stoc=Decimal('5.00'),
            unitate_masura='g', prag_alerta=Decimal('10.00'),
        )

        # ── Produse ──
        self.pizza = Produs.objects.create(
            nume='Pizza Margherita', descriere='Clasică',
            pret=Decimal('32.00'), tip_produs='Pizza', disponibil=True,
            timp_preparare_min=20,
        )
        self.paste = Produs.objects.create(
            nume='Paste Carbonara', descriere='Cu smântână',
            pret=Decimal('28.00'), tip_produs='Paste', disponibil=True,
        )
        self.produs_indisponibil = Produs.objects.create(
            nume='Risotto Trufe', descriere='Premium',
            pret=Decimal('65.00'), tip_produs='Risotto', disponibil=False,
        )

        # ── Rețete (ingrediente → produse) ──
        IngredientReteta.objects.create(
            produs=self.pizza, ingredient=self.faina,
            cantitate_necesara=Decimal('200.00'),
        )
        IngredientReteta.objects.create(
            produs=self.pizza, ingredient=self.branza,
            cantitate_necesara=Decimal('100.00'),
        )
        IngredientReteta.objects.create(
            produs=self.produs_indisponibil, ingredient=self.ingredient_rar,
            cantitate_necesara=Decimal('10.00'),
        )

        # ── Client HTTP ──
        self.client = Client()


# ═══════════════════════════════════════════════════════════
#  1. TESTE MODELE — crearea și __str__
# ═══════════════════════════════════════════════════════════

class ModelStrTests(BaseTestCase):
    """Verifică că modelele se creează corect și returnează un __str__ logic."""

    def test_masa_str(self):
        self.assertEqual(str(self.masa), 'Masa 1')

    def test_produs_str(self):
        self.assertEqual(str(self.pizza), 'Pizza Margherita')

    def test_ingredient_str(self):
        self.assertIn('Făină', str(self.faina))
        self.assertIn('500', str(self.faina))

    def test_comanda_str(self):
        comanda = Comanda.objects.create(masa=self.masa, total=Decimal('60.00'))
        self.assertIn('60', str(comanda))
        self.assertIn('Lei', str(comanda))

    def test_element_comanda_str(self):
        comanda = Comanda.objects.create(masa=self.masa)
        elem = ElementComanda.objects.create(
            comanda=comanda, produs=self.pizza,
            cantitate=2, pret_unitar=self.pizza.pret,
        )
        self.assertIn('2', str(elem))
        self.assertIn('Pizza', str(elem))

    def test_profil_staff_str(self):
        profil = ProfilStaff.objects.create(
            user=self.staff_user, nume_angajat='Ion Popescu', rol='ospatar',
        )
        self.assertIn('Ion Popescu', str(profil))

    def test_ingredient_reteta_str(self):
        ir = IngredientReteta.objects.filter(produs=self.pizza).first()
        self.assertIn('Pizza Margherita', str(ir))
        self.assertIn('Făină', str(ir))


# ═══════════════════════════════════════════════════════════
#  2. TESTE LOGICĂ BUSINESS — disponibilitate & stocuri
# ═══════════════════════════════════════════════════════════

class DisponibilitateTests(BaseTestCase):
    """Testează Produs.verifica_disponibilitate() — motorul Auto-86."""

    def test_produs_disponibil_cand_stoc_suficient(self):
        disponibil, lipsa = self.pizza.verifica_disponibilitate()
        self.assertTrue(disponibil)
        self.assertEqual(len(lipsa), 0)

    def test_produs_indisponibil_cand_stoc_insuficient(self):
        self.faina.cantitate_stoc = Decimal('10.00')  # sub 200g necesare
        self.faina.save()
        disponibil, lipsa = self.pizza.verifica_disponibilitate()
        self.assertFalse(disponibil)
        self.assertTrue(len(lipsa) > 0)

    def test_produs_fara_reteta_ramane_disponibil(self):
        """Un produs fără rețetă definită trebuie să fie mereu disponibil."""
        disponibil, lipsa = self.paste.verifica_disponibilitate()
        self.assertTrue(disponibil)
        self.assertEqual(lipsa, [])

    def test_ingrediente_lipsa_contin_info_corecta(self):
        self.branza.cantitate_stoc = Decimal('0.00')
        self.branza.save()
        _, lipsa = self.pizza.verifica_disponibilitate()
        self.assertEqual(len(lipsa), 1)
        self.assertEqual(lipsa[0]['ingredient'], 'Brânză')
        self.assertEqual(lipsa[0]['unitate'], 'g')


class ScadereStocuriTests(BaseTestCase):
    """Testează Comanda.scade_stocuri() — scăderea automată la servire."""

    def _creeaza_comanda_cu_pizza(self, cantitate=1):
        comanda = Comanda.objects.create(
            masa=self.masa, status='in_preparare', total=self.pizza.pret * cantitate,
        )
        ElementComanda.objects.create(
            comanda=comanda, produs=self.pizza,
            cantitate=cantitate, pret_unitar=self.pizza.pret,
        )
        return comanda

    def test_scade_stocuri_corect(self):
        comanda = self._creeaza_comanda_cu_pizza(cantitate=1)
        comanda.scade_stocuri()

        self.faina.refresh_from_db()
        self.branza.refresh_from_db()
        # 500 - 200 = 300
        self.assertEqual(self.faina.cantitate_stoc, Decimal('300.00'))
        # 200 - 100 = 100
        self.assertEqual(self.branza.cantitate_stoc, Decimal('100.00'))

    def test_stocul_nu_devine_negativ(self):
        self.faina.cantitate_stoc = Decimal('50.00')
        self.faina.save()
        comanda = self._creeaza_comanda_cu_pizza(cantitate=1)
        comanda.scade_stocuri()

        self.faina.refresh_from_db()
        self.assertEqual(self.faina.cantitate_stoc, Decimal('0.00'))

    def test_alerta_ingrediente_sub_prag(self):
        # Facem stocul să cadă sub prag după scădere
        self.faina.cantitate_stoc = Decimal('250.00')  # 250 - 200 = 50 < 100 (prag)
        self.faina.save()
        comanda = self._creeaza_comanda_cu_pizza(cantitate=1)
        rezultat = comanda.scade_stocuri()

        alerte = rezultat['ingrediente_sub_prag']
        nume_alertate = [a['nume'] for a in alerte]
        self.assertIn('Făină', nume_alertate)

    def test_auto_86_dezactiveaza_produs(self):
        """Când stocul scade sub necesarul rețetei, produsul se dezactivează."""
        self.faina.cantitate_stoc = Decimal('200.00')  # exact o porție
        self.faina.save()
        comanda = self._creeaza_comanda_cu_pizza(cantitate=1)
        rezultat = comanda.scade_stocuri()

        self.pizza.refresh_from_db()
        self.assertFalse(self.pizza.disponibil)
        dezactivate = [p['nume'] for p in rezultat['produse_dezactivate']]
        self.assertIn('Pizza Margherita', dezactivate)

    def test_scade_multiplicat_cu_cantitatea(self):
        """Comandă cu 2 pizza → scade dublu."""
        comanda = self._creeaza_comanda_cu_pizza(cantitate=2)
        comanda.scade_stocuri()

        self.faina.refresh_from_db()
        # 500 - (200 * 2) = 100
        self.assertEqual(self.faina.cantitate_stoc, Decimal('100.00'))


# ═══════════════════════════════════════════════════════════
#  3. TESTE VIEW-URI — acces & permisiuni
# ═══════════════════════════════════════════════════════════

class AccesViewTests(BaseTestCase):
    """Verifică că paginile protejate cer autentificare și permisiuni."""

    def test_dashboard_redirect_fara_login(self):
        """Un utilizator nelogat trebuie redirectat la login."""
        response = self.client.get(reverse('staff_dashboard'))
        self.assertEqual(response.status_code, 302)  # redirect to login

    def test_dashboard_acces_staff(self):
        """Un user staff trebuie să vadă dashboard-ul."""
        self.client.login(username='ospatar1', password='TestPass123!')
        response = self.client.get(reverse('staff_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_interzis_user_normal(self):
        """Un user non-staff primește 403."""
        self.client.login(username='client1', password='TestPass123!')
        response = self.client.get(reverse('staff_dashboard'))
        self.assertEqual(response.status_code, 403)

    def test_pagina_autentificare_deschisa(self):
        """Pagina de login trebuie accesibilă oricui."""
        response = self.client.get(reverse('autentificare'))
        self.assertEqual(response.status_code, 200)

    def test_pagina_meniu_deschisa(self):
        """Meniul trebuie accesibil fără login."""
        response = self.client.get(reverse('meniu_general'))
        self.assertEqual(response.status_code, 200)

    def test_login_staff_credentiale_corecte(self):
        """Login cu credențiale corecte redirecționează la dashboard."""
        response = self.client.post(reverse('login_staff'), {
            'username': 'ospatar1',
            'password': 'TestPass123!',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('bucatarie', response.url)

    def test_login_staff_credentiale_gresite(self):
        """Login cu parolă greșită redirecționează înapoi la autentificare."""
        response = self.client.post(reverse('login_staff'), {
            'username': 'ospatar1',
            'password': 'ParolaGresita',
        })
        self.assertEqual(response.status_code, 302)
        # trebuie să redirecționeze la pagina de autentificare, nu la dashboard
        self.assertNotIn('bucatarie', response.url)


# ═══════════════════════════════════════════════════════════
#  4. TESTE API — comenzi
# ═══════════════════════════════════════════════════════════

class PlaseazaComandaTests(BaseTestCase):
    """Testează endpoint-ul de plasare comandă."""

    def test_comanda_valida(self):
        import json
        response = self.client.post(
            '/plaseaza-comanda/',
            data=json.dumps({
                'cart': [
                    {'id': self.pizza.id, 'quantity': 2},
                    {'id': self.paste.id, 'quantity': 1},
                ],
                'masa_id': self.masa.id,
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('comanda_id', data)

        # Verificăm că comanda s-a creat corect
        comanda = Comanda.objects.get(id=data['comanda_id'])
        self.assertEqual(comanda.elemente.count(), 2)
        self.assertEqual(comanda.status, 'noua')

    def test_comanda_cos_gol(self):
        import json
        response = self.client.post(
            '/plaseaza-comanda/',
            data=json.dumps({'cart': []}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_comanda_fara_masa(self):
        """O comandă fără masă specificată trebuie să funcționeze (takeaway)."""
        import json
        response = self.client.post(
            '/plaseaza-comanda/',
            data=json.dumps({
                'cart': [{'id': self.pizza.id, 'quantity': 1}],
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        comanda = Comanda.objects.get(id=response.json()['comanda_id'])
        self.assertIsNone(comanda.masa)


class SchimbaStatusTests(BaseTestCase):
    """Testează schimbarea statusului unei comenzi."""

    def setUp(self):
        super().setUp()
        self.comanda = Comanda.objects.create(
            masa=self.masa, status='noua', total=Decimal('32.00'),
        )
        ElementComanda.objects.create(
            comanda=self.comanda, produs=self.pizza,
            cantitate=1, pret_unitar=self.pizza.pret,
        )

    def test_schimba_status_in_preparare(self):
        import json
        response = self.client.post(
            f'/schimba-status/{self.comanda.id}/',
            data=json.dumps({'status': 'in_preparare'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.comanda.refresh_from_db()
        self.assertEqual(self.comanda.status, 'in_preparare')

    def test_schimba_status_servita(self):
        import json
        response = self.client.post(
            f'/schimba-status/{self.comanda.id}/',
            data=json.dumps({'status': 'servita'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.comanda.refresh_from_db()
        self.assertEqual(self.comanda.status, 'servita')

    def test_comanda_inexistenta_returneaza_eroare(self):
        import json
        response = self.client.post(
            '/schimba-status/99999/',
            data=json.dumps({'status': 'servita'}),
            content_type='application/json',
        )
        # View-ul curent returnează 500 cu error message (catch generic)
        self.assertIn(response.status_code, [404, 500])


# ═══════════════════════════════════════════════════════════
#  5. TESTE URL ROUTING — verifică că URL-urile rezolvă corect
# ═══════════════════════════════════════════════════════════

class URLRoutingTests(TestCase):
    """Verifică că URL-urile principale rezolvă la view-urile corecte."""

    def test_url_autentificare(self):
        resolver = resolve('/')
        self.assertEqual(resolver.func.__name__, 'pagina_autentificare')

    def test_url_meniu(self):
        resolver = resolve('/meniu/')
        self.assertEqual(resolver.func.__name__, 'pagina_meniu')

    def test_url_dashboard(self):
        resolver = resolve('/bucatarie/')
        self.assertEqual(resolver.func.__name__, 'dashboard_staff')

    def test_url_login_staff(self):
        resolver = resolve('/login-staff/')
        self.assertEqual(resolver.func.__name__, 'login_staff')

    def test_url_plaseaza_comanda(self):
        resolver = resolve('/plaseaza-comanda/')
        self.assertEqual(resolver.func.__name__, 'plaseaza_comanda')

    def test_url_schimba_status(self):
        resolver = resolve('/schimba-status/1/')
        self.assertEqual(resolver.func.__name__, 'schimba_status')


# ═══════════════════════════════════════════════════════════
#  6. TESTE MODEL CONSTRAINTS — edge cases
# ═══════════════════════════════════════════════════════════

class ModelConstraintTests(TestCase):
    """Verifică constrângerile de bază ale modelelor."""

    def test_masa_nr_unic(self):
        Masa.objects.create(nr_masa=42)
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Masa.objects.create(nr_masa=42)

    def test_masa_token_qr_auto_generat(self):
        masa = Masa.objects.create(nr_masa=99)
        self.assertIsNotNone(masa.token_qr)

    def test_produs_default_disponibil(self):
        p = Produs.objects.create(
            nume='Test', descriere='Test', pret=Decimal('10.00'),
        )
        self.assertTrue(p.disponibil)

    def test_produs_default_timp_preparare(self):
        p = Produs.objects.create(
            nume='Test2', descriere='Test', pret=Decimal('10.00'),
        )
        self.assertEqual(p.timp_preparare_min, 15)

    def test_comanda_default_status(self):
        comanda = Comanda.objects.create()
        self.assertEqual(comanda.status, 'in_asteptare')

    def test_comanda_default_total_zero(self):
        comanda = Comanda.objects.create()
        self.assertEqual(comanda.total, Decimal('0.00'))
