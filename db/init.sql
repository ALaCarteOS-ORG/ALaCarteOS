CREATE EXTENSION IF NOT EXISTS "uuid-ossp";



CREATE TABLE IF NOT EXISTS mese (
    id SERIAL PRIMARY KEY,
    numar_masa INT NOT NULL UNIQUE,
    token_qr UUID DEFAULT uuid_generate_v4() NOT NULL, 
    status TEXT DEFAULT 'liber' CHECK (status IN ('liber', 'ocupat')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS produse (
    id SERIAL PRIMARY KEY,
    nume TEXT NOT NULL,
    descriere TEXT, 
    pret NUMERIC(10, 2) NOT NULL,
    categorie TEXT NOT NULL, 
    disponibil BOOLEAN DEFAULT TRUE,
    imagine_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS staff_accounts (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    nume_angajat TEXT NOT NULL,
    rol TEXT NOT NULL CHECK (rol IN ('ospatar', 'bucatar', 'admin')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS comenzi (
    id SERIAL PRIMARY KEY,
    masa_id INT REFERENCES mese(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'noua' CHECK (status IN ('noua', 'in_preparare', 'gata', 'servita', 'platita')),
    total_pret NUMERIC(10, 2) DEFAULT 0,
    observatii_client TEXT, 
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS articole_comanda (
    id SERIAL PRIMARY KEY,
    comanda_id INT REFERENCES comenzi(id) ON DELETE CASCADE,
    produs_id INT REFERENCES produse(id) ON DELETE RESTRICT,
    cantitate INT DEFAULT 1 CHECK (cantitate > 0),
    pret_unitar_la_momentul_comenzii NUMERIC(10, 2) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);