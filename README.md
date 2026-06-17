# ALaCarteOS

ALaCarteOS este un sistem de operare și o aplicație web concepute pentru managementul fluxurilor operaționale din cadrul restaurantelor (sectorul HoReCa). Sistemul facilitează interacțiunea dintre clienți și personalul restaurantului printr-o arhitectură bazată pe acces via coduri QR, eliminând necesitatea creării de conturi pentru clienți.

Proiectul integrează componente pentru preluarea comenzilor, un dashboard securizat destinat personalului (bucătari, ospătari) și un sistem automatizat de asistență bazat pe inteligență artificială, având scopul de a optimiza timpii de preparare și de a gestiona eficient catalogul de produse și stocurile de ingrediente.

## Tehnologii principale

- Backend: Python 3, Django
- Frontend: HTML5, JavaScript (Vanilla), CSS (Vanilla)
- Bază de date: SQLite (local) / PostgreSQL (producție)
- CI/CD: GitHub Actions (pentru linting cu Flake8, testare automată și scanare de securitate)
- Integrare AI: Google Gemini API

## Arhitectură și Funcționalități cheie

- Dashboard pentru Personal (Staff): Interfață dedicată bucătarilor și ospătarilor pentru monitorizarea și administrarea comenzilor. Include module pentru actualizarea statusului comenzilor în timp real.
- Gestionarea Produselor și a Stocurilor: Sistem de gestiune a meniului, a rețetelor și a timpilor de preparare. Sistemul include funcționalitatea Auto-86, care dezactivează automat produsele atunci când stocul ingredientelor asociate scade sub cantitatea necesară rețetei.
- Agent AI Integrat: Modul de inteligență artificială implementat pentru a oferi predicții operaționale referitoare la încărcarea stațiilor de lucru, analiza tendințelor de comandă și generarea automată de rapoarte executive la sfârșitul zilei.
- Securitate și Permisiuni: Arhitectură de acces bazată pe roluri (Role-Based Access Control) care restricționează accesul la rutele de administrare doar pentru personalul autorizat.

## Cerințe preliminare (Prerequisites)

Pentru a rula și dezvolta acest proiect local, este necesar un mediu configurat cu:
- Python 3.12 sau o versiune ulterioară compatibilă
- pip (managerul de pachete Python)
- virtualenv (recomandat pentru izolarea dependențelor)
- Git

## Instalare și Configurare Locală

1. Clonarea depozitului de cod:
   git clone https://github.com/ALaCarteOS-ORG/ALaCarteOS.git
   cd ALaCarteOS

2. Crearea și activarea mediului virtual:
   Pe mediul Windows:
   python -m venv venv
   venv\Scripts\activate

   Pe mediul macOS/Linux:
   python3 -m venv venv
   source venv/bin/activate

3. Instalarea dependențelor necesare:
   pip install --upgrade pip
   pip install -r requirements.txt

4. Configurarea variabilelor de mediu:
   Creați un fișier denumit `.env` (cu punct la început) în directorul rădăcină al proiectului. O metodă simplă este să copiați fișierul de exemplu:
   
   Pe mediul Windows:
   copy .env.example .env

   Pe mediul macOS/Linux:
   cp .env.example .env

   După creare, deschideți fișierul `.env` și completați variabilele de configurare necesare, în mod special cheile API pentru agentul AI (`GEMINI_API_KEY`) și URL-ul bazei de date.

5. Rularea migrațiilor pentru crearea schemei bazei de date:
   python manage.py migrate

6. Pornirea serverului de dezvoltare:
   python manage.py runserver

   Aplicația va putea fi accesată în browser la adresa http://127.0.0.1:8000/.

## Contribuție și Workflow

Dezvoltarea proiectului respectă un flux de lucru standardizat bazat pe branch-uri de funcționalitate (feature branches). Modificările directe pe branch-ul main sunt strict interzise.

Pentru a contribui la proiect:
1. Creați un branch nou plecând de la main sau develop (ex. feature/nume-modul).
2. Efectuați modificările necesare. Asigurați-vă că stilul de cod este conform (rulați Flake8) și că testele automate locale trec.
3. Deschideți un Pull Request (PR) către branch-ul principal.
4. Procesul de merge va fi aprobat exclusiv după ce pipeline-ul de CI/CD (GitHub Actions) validează cu succes noul cod adăugat.
