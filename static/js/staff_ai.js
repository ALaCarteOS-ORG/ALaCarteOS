// ===========================================================================
//  AGENT AI 2 — Staff Dashboard Intelligence (staff_ai.js)
//  Gestionează: Predicții AI, Toggle Modul 86, Notificări Toast
// ===========================================================================

document.addEventListener('DOMContentLoaded', () => {
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

    // ===========================================================================
    //  1. SISTEMUL DE NOTIFICĂRI TOAST
    // ===========================================================================

    /**
     * Afișează un toast de notificare în colțul din dreapta sus.
     * @param {string} mesaj - Textul notificării
     * @param {string} tip - 'success' | 'warning' | 'danger' | 'info'
     * @param {number} durata - Milisecunde până la dispariție (default 5000)
     */
    function showToast(mesaj, tip = 'info', durata = 5000) {
        let container = document.getElementById('kds-toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'kds-toast-container';
            container.className = 'kds-toast-container';
            document.body.appendChild(container);
        }

        const toast = document.createElement('div');
        toast.className = `kds-toast kds-toast-${tip}`;

        // Iconiță în funcție de tip
        const icoane = {
            success: 'fa-check-circle',
            warning: 'fa-triangle-exclamation',
            danger: 'fa-circle-xmark',
            info: 'fa-microchip'
        };

        toast.innerHTML = `
            <div class="kds-toast-icon">
                <i class="fa-solid ${icoane[tip] || icoane.info}"></i>
            </div>
            <div class="kds-toast-body">
                <span>${mesaj}</span>
            </div>
            <button class="kds-toast-close" onclick="this.parentElement.remove()">
                <i class="fa-solid fa-xmark"></i>
            </button>
        `;

        container.appendChild(toast);

        // Animație de intrare
        requestAnimationFrame(() => {
            toast.classList.add('kds-toast-show');
        });

        // Auto-dismiss
        setTimeout(() => {
            toast.classList.remove('kds-toast-show');
            toast.classList.add('kds-toast-hide');
            setTimeout(() => toast.remove(), 400);
        }, durata);
    }

    // Expunem global pentru a fi apelat din alte scripturi
    window.showKdsToast = showToast;


    // ===========================================================================
    //  2. PREDICȚII AI — Fetch & Auto-Refresh
    // ===========================================================================

    const predictieText = document.getElementById('ai-predictie-text');
    const aiStatusIndicator = document.getElementById('ai-status');
    let predictieInterval = null;

    async function fetchPredictieAI() {
        if (!predictieText) return;

        // Indicator de încărcare
        predictieText.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Se generează predicția AI...';

        // Pulsează indicatorul din navbar
        if (aiStatusIndicator) {
            aiStatusIndicator.classList.add('ai-pulse');
        }

        try {
            const response = await fetch('/ai-predictie-kds/', {
                method: 'GET',
                headers: {
                    'X-CSRFToken': csrfToken,
                    'Content-Type': 'application/json'
                }
            });

            const data = await response.json();

            if (data.success && data.predictie) {
                predictieText.innerHTML = `
                    <strong>Predicție AI:</strong><br>
                    ${data.predictie}
                `;

                // Actualizăm și nivelul de alertă vizual (opțional)
                if (data.nivel_alerta === 'ridicat') {
                    predictieText.closest('.mt-auto')?.classList.add('ai-alert-high');
                } else {
                    predictieText.closest('.mt-auto')?.classList.remove('ai-alert-high');
                }
            } else {
                predictieText.innerHTML = `
                    <strong>Predicție AI:</strong><br>
                    ${data.predictie || 'Monitorizați manual comenzile.'}
                `;
            }
        } catch (error) {
            console.error('[AI KDS] Eroare la fetch predicție:', error);
            predictieText.innerHTML = `
                <strong>Predicție AI:</strong><br>
                Conexiune întreruptă. Se reîncearcă automat...
            `;
        } finally {
            // Oprim pulsul după 2 secunde
            setTimeout(() => {
                if (aiStatusIndicator) {
                    aiStatusIndicator.classList.remove('ai-pulse');
                }
            }, 2000);
        }
    }

    // Fetch inițial + auto-refresh la 10 minute
    fetchPredictieAI();
    predictieInterval = setInterval(fetchPredictieAI, 10 * 60 * 1000);


    // ===========================================================================
    //  3. MODULUL "86" — Toggle Switch-uri Disponibilitate Produse
    // ===========================================================================

    document.querySelectorAll('.switch-86').forEach(switchEl => {
        switchEl.addEventListener('change', async function() {
            const produsId = this.getAttribute('data-produs-id');
            const produsNume = this.getAttribute('data-produs-name');
            const nouStatus = this.checked;
            const labelEl = document.getElementById(`label_${produsId}`);

            // Actualizare vizuală optimistă
            if (labelEl) {
                labelEl.textContent = nouStatus ? 'ACTIV' : 'EPUIZAT';
                labelEl.className = `form-check-label small fw-bold ms-2 ${nouStatus ? 'text-muted' : 'text-danger'}`;
            }

            // Actualizăm și numele produsului (text-danger dacă epuizat)
            const numeEl = document.getElementById(`name_${produsId}`);
            if (numeEl) {
                numeEl.className = `fw-bold ${nouStatus ? 'text-dark' : 'text-danger'}`;
            }

            try {
                const response = await fetch(`/toggle-produs/${produsId}/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    body: JSON.stringify({ disponibil: nouStatus })
                });

                const data = await response.json();

                if (response.ok && data.success) {
                    showToast(
                        `<strong>${produsNume}</strong> a fost ${data.disponibil ? 'activat' : 'scos din meniu'}.`,
                        data.disponibil ? 'success' : 'warning'
                    );
                } else {
                    // Revert: stocuri insuficiente
                    this.checked = !nouStatus;
                    if (labelEl) {
                        labelEl.textContent = !nouStatus ? 'ACTIV' : 'EPUIZAT';
                        labelEl.className = `form-check-label small fw-bold ms-2 ${!nouStatus ? 'text-muted' : 'text-danger'}`;
                    }
                    if (numeEl) {
                        numeEl.className = `fw-bold ${!nouStatus ? 'text-dark' : 'text-danger'}`;
                    }

                    let errorMsg = data.error || 'Eroare la modificare.';
                    if (data.ingrediente_lipsa && data.ingrediente_lipsa.length > 0) {
                        const lipsa = data.ingrediente_lipsa.map(i => `${i.ingredient} (${i.stoc_actual}/${i.necesar_portie} ${i.unitate})`).join(', ');
                        errorMsg += ` Lipsă: ${lipsa}`;
                    }
                    showToast(errorMsg, 'danger', 7000);
                }
            } catch (error) {
                console.error('[MOD-86] Eroare la toggle:', error);
                // Revert
                this.checked = !nouStatus;
                showToast('Eroare de conexiune. Încercați din nou.', 'danger');
            }
        });
    });


    // ===========================================================================
    //  4. AUTO-86 ALERTS — Procesare răspunsuri de la schimba_status
    // ===========================================================================

    /**
     * Procesează răspunsul de la /schimba-status/ și afișează notificări
     * pentru produsele dezactivate automat și ingredientele sub prag.
     * Apelată din event listener-ul de pe butoanele de status.
     */
    window.proceseazaAuto86 = function(data) {
        if (!data.stocuri) return;

        const { ingrediente_sub_prag, produse_dezactivate } = data.stocuri;

        // Notificări pentru ingrediente sub prag
        if (ingrediente_sub_prag && ingrediente_sub_prag.length > 0) {
            ingrediente_sub_prag.forEach(ing => {
                showToast(
                    `<strong>Stoc scăzut:</strong> ${ing.nume} — doar ${ing.stoc_ramas} ${ing.unitate} (prag: ${ing.prag})`,
                    'warning',
                    8000
                );
            });
        }

        // Notificări pentru produse dezactivate automat
        if (produse_dezactivate && produse_dezactivate.length > 0) {
            produse_dezactivate.forEach(prod => {
                showToast(
                    `<strong>AUTO-86:</strong> „${prod.nume}" a fost scos automat din meniu (stocuri insuficiente).`,
                    'danger',
                    10000
                );

                // Actualizăm și switch-ul din Modulul 86 (dacă panoul este deschis)
                const switchEl = document.getElementById(`switch_${prod.id}`);
                if (switchEl) {
                    switchEl.checked = false;
                    const labelEl = document.getElementById(`label_${prod.id}`);
                    if (labelEl) {
                        labelEl.textContent = 'EPUIZAT';
                        labelEl.className = 'form-check-label small fw-bold ms-2 text-danger';
                    }
                    const numeEl = document.getElementById(`name_${prod.id}`);
                    if (numeEl) {
                        numeEl.className = 'fw-bold text-danger';
                    }
                }
            });
        }
    };
});
