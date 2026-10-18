"""Accès à PostgreSQL.

Le backend ne connaît la base que par la variable d'environnement DATABASE_URL,
construite par docker-compose à partir du .env. Le nom d'hôte "db" est résolu
par le DNS interne de Docker (nom du service dans docker-compose.yml).
"""
import os

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

# Pool de connexions : on réutilise quelques connexions ouvertes au lieu
# d'en ouvrir une nouvelle à chaque requête.
pool = AsyncConnectionPool(
    conninfo=os.environ.get("DATABASE_URL", ""),
    min_size=1,
    max_size=5,
    open=False,                       # ouvert au démarrage de l'appli (voir main.py)
    kwargs={"row_factory": dict_row}, # les lignes reviennent sous forme de dict
)


async def ping() -> None:
    async with pool.connection() as conn:
        await conn.execute("SELECT 1")


async def insert_game(game_id: str, white_name: str, white_token_hash: str, fen: str) -> None:
    async with pool.connection() as conn:
        await conn.execute(
            "INSERT INTO games (id, white_name, white_token_hash, fen) VALUES (%s, %s, %s, %s)",
            (game_id, white_name, white_token_hash, fen),
        )


async def set_black_player(game_id: str, black_name: str, black_token_hash: str) -> None:
    async with pool.connection() as conn:
        await conn.execute(
            """UPDATE games
               SET black_name = %s, black_token_hash = %s, status = 'playing', updated_at = now()
               WHERE id = %s""",
            (black_name, black_token_hash, game_id),
        )


async def insert_move(game_id: str, ply: int, uci: str, san: str, fen_after: str) -> None:
    # Le coup et la nouvelle position sont écrits dans la même transaction :
    # soit les deux sont enregistrés, soit aucun.
    async with pool.connection() as conn:
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO moves (game_id, ply, uci, san, fen_after) VALUES (%s, %s, %s, %s, %s)",
                (game_id, ply, uci, san, fen_after),
            )
            await conn.execute(
                "UPDATE games SET fen = %s, updated_at = now() WHERE id = %s",
                (fen_after, game_id),
            )


async def finish_game(game_id: str, result: str, end_reason: str) -> None:
    async with pool.connection() as conn:
        await conn.execute(
            """UPDATE games
               SET status = 'finished', result = %s, end_reason = %s, updated_at = now()
               WHERE id = %s""",
            (result, end_reason, game_id),
        )


async def get_game(game_id: str) -> dict | None:
    async with pool.connection() as conn:
        cur = await conn.execute("SELECT * FROM games WHERE id = %s", (game_id,))
        return await cur.fetchone()


async def get_moves(game_id: str) -> list[dict]:
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT ply, uci, san, played_at FROM moves WHERE game_id = %s ORDER BY ply",
            (game_id,),
        )
        return await cur.fetchall()


async def list_recent_games(limit: int) -> list[dict]:
    async with pool.connection() as conn:
        cur = await conn.execute(
            """SELECT g.id, g.white_name, g.black_name, g.status, g.result, g.end_reason,
                      g.created_at, g.updated_at,
                      (SELECT count(*) FROM moves m WHERE m.game_id = g.id) AS move_count
               FROM games g
               ORDER BY g.updated_at DESC
               LIMIT %s""",
            (limit,),
        )
        return await cur.fetchall()
