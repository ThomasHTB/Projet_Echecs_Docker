-- ============================================================
--  Schéma de la base ChessDock
--
--  Ce fichier est monté dans /docker-entrypoint-initdb.d/ du conteneur
--  PostgreSQL. L'image officielle l'exécute AUTOMATIQUEMENT, mais
--  UNIQUEMENT au tout premier démarrage (quand le volume pgdata est vide).
--  Pour le rejouer : docker compose down -v   (⚠️ efface les données)
-- ============================================================

-- Une partie d'échecs
CREATE TABLE IF NOT EXISTS games (
    id                 VARCHAR(8)  PRIMARY KEY,           -- code partagé entre les joueurs (ex : "K7P2QX")
    white_name         VARCHAR(20) NOT NULL,
    black_name         VARCHAR(20),                       -- NULL tant que personne n'a rejoint
    -- On ne stocke JAMAIS le jeton de reconnexion en clair, seulement son empreinte SHA-256
    white_token_hash   CHAR(64)    NOT NULL,
    black_token_hash   CHAR(64),
    fen                TEXT        NOT NULL,              -- position actuelle (notation FEN)
    status             VARCHAR(10) NOT NULL DEFAULT 'waiting'
                       CHECK (status IN ('waiting', 'playing', 'finished')),
    result             VARCHAR(7)  CHECK (result IN ('1-0', '0-1', '1/2-1/2')),
    end_reason         VARCHAR(30),                       -- checkmate, stalemate, resignation...
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- L'historique des coups d'une partie
CREATE TABLE IF NOT EXISTS moves (
    id          BIGSERIAL   PRIMARY KEY,
    game_id     VARCHAR(8)  NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    ply         INTEGER     NOT NULL,                     -- numéro du demi-coup (1, 2, 3...)
    uci         VARCHAR(5)  NOT NULL,                     -- notation machine : e2e4, e7e8q
    san         VARCHAR(10) NOT NULL,                     -- notation humaine : e4, Nf3, O-O
    fen_after   TEXT        NOT NULL,                     -- position après le coup
    played_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (game_id, ply)
);

CREATE INDEX IF NOT EXISTS idx_moves_game ON moves (game_id, ply);
CREATE INDEX IF NOT EXISTS idx_games_updated ON games (updated_at DESC);
