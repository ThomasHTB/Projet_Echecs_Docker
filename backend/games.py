"""Gestion des parties d'échecs en temps réel.

- Les règles (coups légaux, échec et mat, pat, nulles...) sont entièrement
  déléguées à la bibliothèque python-chess : pas de moteur maison.
- Le serveur est la seule autorité : le navigateur propose un coup, le serveur
  le valide, l'enregistre en base, puis diffuse la nouvelle position aux deux joueurs.
- Les parties en cours sont gardées en mémoire pour la rapidité, et TOUT est
  écrit dans PostgreSQL : si le conteneur backend redémarre, une partie est
  reconstruite depuis la base dès qu'un joueur se reconnecte.
"""
import asyncio
import hashlib
import re
import secrets
from dataclasses import dataclass, field

import chess
from fastapi import WebSocket

import database as db

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sans 0/O ni 1/I : codes faciles à dicter
CODE_LENGTH = 6
CODE_PATTERN = re.compile(rf"^[{CODE_ALPHABET}]{{{CODE_LENGTH}}}$")
NAME_MAX_LENGTH = 20
NAME_PATTERN = re.compile(r"^[\w \-.]{1,20}$")  # lettres (accents compris), chiffres, espace, _ - .


class GameError(Exception):
    """Erreur « normale » renvoyée au joueur (coup illégal, code inconnu...)."""


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def clean_name(raw) -> str:
    name = str(raw or "").strip()
    if not NAME_PATTERN.match(name):
        raise GameError(f"Pseudo invalide (1 à {NAME_MAX_LENGTH} caractères : lettres, chiffres, espace, _ - .).")
    return name


def clean_code(raw) -> str:
    code = str(raw or "").strip().upper()
    if not CODE_PATTERN.match(code):
        raise GameError("Code de partie invalide.")
    return code


@dataclass
class Game:
    id: str
    white_name: str
    white_token_hash: str
    board: chess.Board = field(default_factory=chess.Board)
    black_name: str | None = None
    black_token_hash: str | None = None
    status: str = "waiting"           # waiting -> playing -> finished
    result: str | None = None         # "1-0", "0-1", "1/2-1/2"
    end_reason: str | None = None
    sans: list[str] = field(default_factory=list)   # historique lisible (e4, Nf3...)
    sockets: dict[str, WebSocket] = field(default_factory=dict)  # "white"/"black" -> connexion
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)     # un seul coup traité à la fois

    def name_of(self, color: str) -> str | None:
        return self.white_name if color == "white" else self.black_name

    def color_to_move(self) -> str:
        return "white" if self.board.turn == chess.WHITE else "black"

    def state(self) -> dict:
        """Tout ce dont le navigateur a besoin pour afficher la partie."""
        last = self.board.move_stack[-1].uci() if self.board.move_stack else None
        return {
            "type": "game_state",
            "game_id": self.id,
            "fen": self.board.fen(),
            "turn": "w" if self.board.turn == chess.WHITE else "b",
            "status": self.status,
            "result": self.result,
            "end_reason": self.end_reason,
            "check": self.board.is_check(),
            "last_move": last,
            "moves": self.sans,
            "legal_moves": [m.uci() for m in self.board.legal_moves] if self.status == "playing" else [],
            "players": {
                c: {"name": self.name_of(c), "connected": c in self.sockets}
                for c in ("white", "black")
            },
        }


class GameManager:
    def __init__(self) -> None:
        self.games: dict[str, Game] = {}

    # ---------- utilitaires ----------

    async def _new_code(self) -> str:
        while True:
            code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
            if code not in self.games and await db.get_game(code) is None:
                return code

    async def _load(self, game_id: str) -> Game:
        """Retrouve une partie en mémoire, ou la reconstruit depuis PostgreSQL."""
        if game_id in self.games:
            return self.games[game_id]
        row = await db.get_game(game_id)
        if row is None:
            raise GameError("Aucune partie avec ce code.")
        game = Game(
            id=row["id"],
            white_name=row["white_name"],
            white_token_hash=row["white_token_hash"],
            black_name=row["black_name"],
            black_token_hash=row["black_token_hash"],
            status=row["status"],
            result=row["result"],
            end_reason=row["end_reason"],
        )
        # On rejoue les coups depuis le début (plutôt que de partir du FEN)
        # pour que python-chess connaisse l'historique (règle des 3 répétitions).
        for move in await db.get_moves(game_id):
            game.sans.append(move["san"])
            game.board.push_uci(move["uci"])
        self.games[game_id] = game
        return game

    async def broadcast_state(self, game: Game) -> None:
        await self._broadcast(game, game.state())

    async def _broadcast(self, game: Game, message: dict) -> None:
        for ws in list(game.sockets.values()):
            try:
                await ws.send_json(message)
            except Exception:
                pass  # connexion morte : elle sera nettoyée par detach()

    async def _attach(self, game: Game, color: str, ws: WebSocket) -> None:
        old = game.sockets.get(color)
        if old is not None and old is not ws:
            # Même joueur ouvert dans un autre onglet : l'ancien est déconnecté.
            try:
                await old.send_json({"type": "error", "message": "Partie ouverte dans un autre onglet."})
                await old.close()
            except Exception:
                pass
        game.sockets[color] = ws

    # ---------- actions des joueurs ----------

    async def create(self, name: str, ws: WebSocket) -> tuple[Game, str]:
        token = secrets.token_urlsafe(24)
        game = Game(id=await self._new_code(), white_name=name, white_token_hash=hash_token(token))
        await db.insert_game(game.id, name, game.white_token_hash, game.board.fen())
        self.games[game.id] = game
        await self._attach(game, "white", ws)
        return game, token

    async def join(self, game_id: str, name: str, ws: WebSocket) -> tuple[Game, str]:
        game = await self._load(game_id)
        async with game.lock:
            if game.status != "waiting":
                raise GameError("Cette partie a déjà deux joueurs.")
            token = secrets.token_urlsafe(24)
            await db.set_black_player(game.id, name, hash_token(token))
            game.black_name = name
            game.black_token_hash = hash_token(token)
            game.status = "playing"
        await self._attach(game, "black", ws)
        return game, token

    async def rejoin(self, game_id: str, token: str, ws: WebSocket) -> tuple[Game, str]:
        """Reconnexion après une coupure (rechargement de page, redémarrage du backend...)."""
        game = await self._load(game_id)
        token_hash = hash_token(str(token or ""))
        # compare_digest : comparaison en temps constant (évite de deviner le jeton petit à petit)
        if secrets.compare_digest(token_hash, game.white_token_hash):
            color = "white"
        elif game.black_token_hash and secrets.compare_digest(token_hash, game.black_token_hash):
            color = "black"
        else:
            raise GameError("Jeton de reconnexion invalide.")
        await self._attach(game, color, ws)
        return game, color

    async def play(self, game: Game, color: str, uci: str, promotion: str | None) -> None:
        async with game.lock:
            if game.status != "playing":
                raise GameError("La partie n'est pas en cours.")
            if game.color_to_move() != color:
                raise GameError("Ce n'est pas ton tour.")
            try:
                move = chess.Move.from_uci(str(uci) + (promotion or ""))
            except (ValueError, TypeError):
                raise GameError("Coup mal formé.")
            # Promotion oubliée par le client : on promeut en dame par défaut.
            queen_promotion = chess.Move(move.from_square, move.to_square, chess.QUEEN)
            if move.promotion is None and queen_promotion in game.board.legal_moves:
                move = queen_promotion
            if move not in game.board.legal_moves:
                raise GameError("Coup illégal.")

            san = game.board.san(move)
            game.board.push(move)
            try:
                await db.insert_move(game.id, len(game.board.move_stack), move.uci(), san, game.board.fen())
            except Exception:
                game.board.pop()  # la base a refusé : on annule le coup en mémoire aussi
                raise
            game.sans.append(san)

            outcome = game.board.outcome(claim_draw=True)
            if outcome is not None:
                await self._finish(game, outcome.result(), outcome.termination.name.lower())
        await self._broadcast(game, game.state())

    async def resign(self, game: Game, color: str) -> None:
        async with game.lock:
            if game.status != "playing":
                raise GameError("La partie n'est pas en cours.")
            await self._finish(game, "0-1" if color == "white" else "1-0", "resignation")
        await self._broadcast(game, game.state())

    async def _finish(self, game: Game, result: str, reason: str) -> None:
        await db.finish_game(game.id, result, reason)
        game.status, game.result, game.end_reason = "finished", result, reason

    async def detach(self, game: Game, color: str, ws: WebSocket) -> None:
        """Appelé quand une connexion se ferme."""
        if game.sockets.get(color) is not ws:
            return
        del game.sockets[color]
        if game.sockets:
            await self._broadcast(game, game.state())  # l'adversaire voit « déconnecté »
        else:
            # Plus personne : on libère la mémoire. La partie reste en base
            # et sera rechargée si un joueur revient avec son jeton.
            self.games.pop(game.id, None)
