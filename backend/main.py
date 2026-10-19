"""Backend ChessDock : API REST + serveur WebSocket (FastAPI).

Ce conteneur n'expose AUCUN port sur la machine : il n'est joignable que
par Nginx (service frontend) via le réseau Docker "front-net", et il parle
à PostgreSQL via le réseau interne "back-net".

Routes :
  GET  /api/health          -> état du backend et de la base
  GET  /api/games           -> dernières parties enregistrées en base
  GET  /api/games/{code}    -> détail d'une partie + historique des coups
  WS   /ws                  -> le jeu en temps réel (voir README, « Protocole WebSocket »)
"""
import json
import logging
import os
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

import database as db
from games import Game, GameError, GameManager, clean_code, clean_name

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("chessdock")

# Origines autorisées en plus de « même site » (liste séparée par des virgules dans le .env)
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGIN", "").split(",") if o.strip()]
MAX_MESSAGE_BYTES = 2048  # un message de jeu fait quelques dizaines d'octets


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Démarrage : on ouvre le pool de connexions. Grâce au healthcheck +
    # depends_on: service_healthy, Postgres est déjà prêt à ce moment-là.
    await db.pool.open(wait=True, timeout=30)
    log.info("Connecté à PostgreSQL")
    yield
    await db.pool.close()


app = FastAPI(title="ChessDock API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET"],
    allow_headers=[],
)
manager = GameManager()


# ==================== API REST ====================

@app.get("/api/health")
async def health():
    try:
        await db.ping()
        return {"backend": "ok", "db": "ok", "games_in_memory": len(manager.games)}
    except Exception:
        log.exception("Base injoignable")
        # Pas de détail technique renvoyé au client (on ne divulgue pas l'infra)
        raise HTTPException(status_code=503, detail={"backend": "ok", "db": "unreachable"})


@app.get("/api/games")
async def recent_games(limit: int = 20):
    return await db.list_recent_games(max(1, min(limit, 100)))


@app.get("/api/games/{code}")
async def game_detail(code: str):
    try:
        code = clean_code(code)
    except GameError as e:
        raise HTTPException(status_code=400, detail=str(e))
    game = await db.get_game(code)
    if game is None:
        raise HTTPException(status_code=404, detail="Partie introuvable")
    # On ne renvoie jamais les empreintes de jetons
    game = {k: v for k, v in game.items() if not k.endswith("_token_hash")}
    game["moves"] = await db.get_moves(code)
    return game


# ==================== WebSocket ====================

def origin_allowed(ws: WebSocket) -> bool:
    """Bloque les connexions WebSocket venant d'un autre site (Cross-Site WebSocket Hijacking).

    Un navigateur envoie toujours l'en-tête Origin. On accepte si la page vient
    du même hôte que celui qui reçoit la connexion (cas normal, y compris quand
    on joue depuis un autre PC via http://IP:8080), ou si l'origine est listée
    dans CORS_ORIGIN.
    """
    origin = ws.headers.get("origin")
    if origin is None:
        return True  # client hors navigateur (tests en ligne de commande)
    if origin in ALLOWED_ORIGINS:
        return True
    return urlparse(origin).netloc == ws.headers.get("host")


def parse_message(raw: str) -> dict:
    if len(raw) > MAX_MESSAGE_BYTES:
        raise GameError("Message trop long.")
    try:
        msg = json.loads(raw)
    except ValueError:
        raise GameError("Message JSON invalide.")
    if not isinstance(msg, dict):
        raise GameError("Message JSON invalide.")
    return msg


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    if not origin_allowed(ws):
        await ws.close(code=1008)  # 1008 = violation de politique
        return
    await ws.accept()

    # La partie et la couleur de CETTE connexion (None tant qu'elle n'a rien rejoint)
    game: Game | None = None
    color: str | None = None

    async def leave_current_game():
        nonlocal game, color
        if game is not None:
            await manager.detach(game, color, ws)
        game, color = None, None

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = parse_message(raw)
                kind = msg.get("type")

                if kind == "create_game":
                    name = clean_name(msg.get("name"))
                    await leave_current_game()
                    game, token = await manager.create(name, ws)
                    color = "white"
                    # Le jeton permet de revenir dans la partie après une coupure.
                    await ws.send_json({"type": "game_created", "game_id": game.id, "color": color, "token": token})
                    await ws.send_json(game.state())

                elif kind == "join_game":
                    name = clean_name(msg.get("name"))
                    code = clean_code(msg.get("game_id"))
                    if game is not None and game.id == code:
                        raise GameError("Tu es déjà dans cette partie.")
                    await leave_current_game()
                    game, token = await manager.join(code, name, ws)
                    color = "black"
                    await ws.send_json({"type": "game_joined", "game_id": game.id, "color": color, "token": token})
                    await manager.broadcast_state(game)  # les deux joueurs voient la partie démarrer

                elif kind == "rejoin_game":
                    code = clean_code(msg.get("game_id"))
                    await leave_current_game()
                    game, color = await manager.rejoin(code, msg.get("token"), ws)
                    await ws.send_json({"type": "game_joined", "game_id": game.id, "color": color})
                    await manager.broadcast_state(game)  # l'adversaire voit « reconnecté »

                elif kind == "move":
                    if game is None:
                        raise GameError("Tu n'es dans aucune partie.")
                    uci = str(msg.get("from", "")) + str(msg.get("to", ""))
                    promotion = msg.get("promotion")
                    await manager.play(game, color, uci, str(promotion) if promotion else None)

                elif kind == "resign":
                    if game is None:
                        raise GameError("Tu n'es dans aucune partie.")
                    await manager.resign(game, color)

                elif kind == "leave_game":
                    await leave_current_game()

                else:
                    raise GameError("Type de message inconnu.")

            except GameError as e:
                await ws.send_json({"type": "error", "message": str(e)})
            except (WebSocketDisconnect, RuntimeError):
                raise
            except Exception:
                log.exception("Erreur inattendue")
                await ws.send_json({"type": "error", "message": "Erreur interne du serveur."})
    except (WebSocketDisconnect, RuntimeError):
        pass  # le joueur a fermé l'onglet ou perdu la connexion
    finally:
        await leave_current_game()
