// src/lib/cart.js

document.addEventListener('DOMContentLoaded', () => {
    // 1. Încărcăm coșul din localStorage sau inițializăm un array gol
    let cart = JSON.parse(localStorage.getItem('alacarte_cart')) || [];

    // 2. Selectăm elementele cheie din interfață
    const cartCountEl = document.getElementById('cart-count');
    const cartItemsContainer = document.getElementById('cart-items-container');
    const cartTotalPrice = document.getElementById('cart-total-price');

    // Randăm coșul imediat ce se încarcă pagina
    renderCart();

    // 3. Adăugarea produselor în coș (din pagina principală)
    document.querySelectorAll('.btn-add-cart').forEach(button => {
        button.addEventListener('click', (e) => {
            const id = e.target.getAttribute('data-id');
            const name = e.target.getAttribute('data-name');
            const price = parseFloat(e.target.getAttribute('data-price'));

            addToCart(id, name, price);
            
            // Deschidem panoul lateral de coș automat pentru a vedea ce s-a adăugat
            const cartPanelElement = document.getElementById('cartPanel');
            const cartPanel = bootstrap.Offcanvas.getInstance(cartPanelElement) || new bootstrap.Offcanvas(cartPanelElement);
            cartPanel.show();
        });
    });

    function addToCart(id, name, price) {
        const existingItem = cart.find(item => item.id === id);
        if (existingItem) {
            existingItem.quantity += 1; // Creștem cantitatea dacă e deja în coș
        } else {
            cart.push({ id, name, price, quantity: 1 }); // Produs nou
        }
        saveAndRender();
    }

    // 4. Modificarea cantității din interiorul coșului (+ / -)
    window.updateQuantity = function(id, change) {
        const item = cart.find(item => item.id === id);
        if (item) {
            item.quantity += change;
            
            // Dacă cantitatea ajunge la 0 sau mai puțin, ștergem produsul
            if (item.quantity <= 0) {
                removeFromCart(id);
            } else {
                saveAndRender();
            }
        }
    };

    // 5. Ștergerea completă a produselor din coș
    window.removeFromCart = function(id) {
        cart = cart.filter(item => item.id !== id);
        saveAndRender();
    };

    // 6. Salvarea în memoria browserului și actualizarea UI-ului
    function saveAndRender() {
        localStorage.setItem('alacarte_cart', JSON.stringify(cart));
        renderCart();

        // --- NOU: Actualizare live a AI-ului la orice modificare a coșului ---
        const cartPanelElement = document.getElementById('cartPanel');
        if (cartPanelElement && cartPanelElement.classList.contains('show')) {
            if (cart.length > 0) {
                fetchAiRecommendation(); // Cere o recomandare nouă
            } else {
                document.getElementById('ai-recommendation-container').style.display = 'none';
            }
        }
    }

    // 7. Funcția care desenează produsele în coș
    function renderCart() {
        if (!cartItemsContainer) return;

        // Actualizăm numărul total de produse în butonul de sus
        const totalItems = cart.reduce((sum, item) => sum + item.quantity, 0);
        if (cartCountEl) cartCountEl.innerText = totalItems;

        // Golim containerul pentru a-l redesena
        cartItemsContainer.innerHTML = '';
        let totalCost = 0;

        if (cart.length === 0) {
            cartItemsContainer.innerHTML = '<p class="text-muted text-center mt-5">Coșul tău este gol.</p>';
        } else {
            cart.forEach(item => {
                const itemTotal = item.price * item.quantity;
                totalCost += itemTotal;
                
                cartItemsContainer.innerHTML += `
                    <div class="d-flex justify-content-between align-items-center mb-3 p-2 border-bottom">
                        <div class="flex-grow-1">
                            <h6 class="mb-0" style="font-weight: 700;">${item.name}</h6>
                            <small class="text-muted">${item.price} Lei / buc</small>
                            
                            <!-- Controale pentru Cantitate -->
                            <div class="d-flex align-items-center mt-2">
                                <button class="btn btn-sm btn-outline-secondary px-2 py-0" onclick="updateQuantity('${item.id}', -1)">-</button>
                                <span class="mx-3 fw-bold">${item.quantity}</span>
                                <button class="btn btn-sm btn-outline-secondary px-2 py-0" onclick="updateQuantity('${item.id}', 1)">+</button>
                            </div>
                        </div>
                        
                        <div class="text-end ms-3">
                            <span class="fw-bold d-block mb-2">${itemTotal} Lei</span>
                            <button class="btn btn-sm btn-outline-danger border-0" onclick="removeFromCart('${item.id}')">
                                <i class="fa-solid fa-trash"></i>
                            </button>
                        </div>
                    </div>
                `;
            });
        }

        // Actualizăm prețul total afișat jos
        if (cartTotalPrice) cartTotalPrice.innerText = `${totalCost} Lei`;
    }

    // 8. Trimiterea comenzii catre Server (Checkout)
    const btnCheckout = document.getElementById('btn-checkout');
    if (btnCheckout) {
        btnCheckout.addEventListener('click', async () => {
            if (cart.length === 0) {
                alert('Coșul tău este gol. Adaugă preparate înainte de a comanda!');
                return;
            }

            // Preluam tokenul de securitate CSRF din HTML
            const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
            
            // Preluăm ID-ul mesei din selectorul manual din cos
            const masaSelector = document.getElementById('masa-selector');
            const masaId = masaSelector && masaSelector.value !== "" ? masaSelector.value : null;
            
            btnCheckout.innerText = 'Se trimite...';
            btnCheckout.disabled = true;

            try {
                const response = await fetch('/plaseaza-comanda/', {
                    method: 'POST',
                    headers: { 
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    body: JSON.stringify({ cart: cart, masa_id: masaId })
                });
                const data = await response.json();
                
                if (response.ok) {
                    alert('Comandă plasată cu succes! Se prepară... (ID: ' + data.comanda_id + ')');
                    cart = []; // Golim cosul
                    saveAndRender();
                    bootstrap.Offcanvas.getInstance(document.getElementById('cartPanel')).hide();
                } else {
                    alert('Eroare: ' + data.error);
                }
            } catch (error) {
                console.error(error);
                alert('A apărut o problemă la plasarea comenzii.');
            } finally {
                btnCheckout.innerText = 'Trimite Comanda →';
                btnCheckout.disabled = false;
            }
        });
    }

    // 9. INTEGRARE AI: Ospătarul Virtual se activează când se deschide coșul
    const cartPanelElement = document.getElementById('cartPanel');
    if (cartPanelElement) {
        cartPanelElement.addEventListener('shown.bs.offcanvas', () => {
            if (cart.length > 0) {
                fetchAiRecommendation();
            } else {
                document.getElementById('ai-recommendation-container').style.display = 'none';
            }
        });
    }

    async function fetchAiRecommendation() {
        const aiContainer = document.getElementById('ai-recommendation-container');
        const aiText = document.getElementById('ai-suggestion-text');
        const aiBtn = document.getElementById('btn-add-ai-suggestion');
        
        aiContainer.style.display = 'block';
        aiText.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Analizez comanda pentru asocieri culinare...';
        aiBtn.style.display = 'none';

        try {
            const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
            const response = await fetch('/ai-recomandare/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ cart: cart })
            });

            const data = await response.json();
            if (response.ok && data.recomandare) {
                aiText.innerHTML = `<strong>Recomandare:</strong> ${data.recomandare}`;
                aiBtn.style.display = 'block';
                aiBtn.disabled = false; // Resetăm starea butonului la o nouă recomandare
                aiBtn.innerText = `+ Adaugă ${data.produs_recomandat.nume} (${data.produs_recomandat.pret} Lei)`;
                
                aiBtn.onclick = () => {
                    addToCart(data.produs_recomandat.id.toString(), data.produs_recomandat.nume, data.produs_recomandat.pret);
                    aiBtn.innerText = "Adăugat cu succes!";
                    aiBtn.disabled = true;
                };
            } else {
                // Afisam eroarea în loc să o ascundem, pentru a înțelege problema reală
                aiText.innerHTML = `<span class="text-danger"><i class="fa-solid fa-triangle-exclamation"></i> Eroare: ${data.error || 'Răspuns invalid.'}</span>`;
                aiBtn.style.display = 'none';
            }
        } catch (error) {
            console.error("Eroare la obținerea recomandării AI:", error);
            aiText.innerHTML = `<span class="text-danger"><i class="fa-solid fa-plug-circle-exclamation"></i> Conexiunea cu agentul AI a eșuat.</span>`;
            aiBtn.style.display = 'none';
        }
    }
});