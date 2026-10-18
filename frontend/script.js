// ==============================
//  AFFICHAGE DE L'ÉCHIQUIER
//  Ce fichier ne connaît pas les règles : il dessine la position reçue
//  du serveur (notation FEN) et signale les clics à client.js.
// ==============================

const board = document.getElementById("board");

const pieceFiles = {
  wK: "white_king.svg",
  wQ: "white_queen.svg",
  wR: "white_rook.svg",
  wB: "white_bishop.svg",
  wN: "white_knight.svg",
  wP: "white_pawn.svg",
  bK: "black_king.svg",
  bQ: "black_queen.svg",
  bR: "black_rook.svg",
  bB: "black_bishop.svg",
  bN: "black_knight.svg",
  bP: "black_pawn.svg"
};

const imageBase = "pieces/";
const FILES = "abcdefgh";

// "rnbqkbnr/pppppppp/8/..." -> tableau 8x8 de "wP", "bK", "" (ligne 0 = rangée 8)
function parseFen(fen) {
  const rows = fen.split(" ")[0].split("/");

  return rows.map((row) => {
    const cells = [];

    for (const char of row) {
      if (/\d/.test(char)) {
        for (let i = 0; i < Number(char); i++) cells.push("");
      } else {
        const color = char === char.toUpperCase() ? "w" : "b";
        cells.push(color + char.toUpperCase());
      }
    }

    return cells;
  });
}

// (ligne, colonne) du tableau -> nom de case "e4"
function squareName(row, col) {
  return FILES[col] + (8 - row);
}

/**
 * Dessine l'échiquier.
 * options = {
 *   fen, orientation ("white" | "black"), selected ("e2" | null),
 *   targets (cases où la pièce sélectionnée peut aller), lastMove ("e2e4" | null),
 *   checkSquare (case du roi en échec | null), onSquareClick(name, piece)
 * }
 */
function renderBoard(options) {
  const pieces = parseFen(options.fen);
  const targets = options.targets || [];
  const last = options.lastMove
    ? [options.lastMove.slice(0, 2), options.lastMove.slice(2, 4)]
    : [];

  board.innerHTML = "";

  for (let i = 0; i < 8; i++) {
    for (let j = 0; j < 8; j++) {
      // Vue des noirs : on retourne simplement le plateau.
      const row = options.orientation === "black" ? 7 - i : i;
      const col = options.orientation === "black" ? 7 - j : j;
      const name = squareName(row, col);
      const piece = pieces[row][col];

      const square = document.createElement("div");
      square.classList.add("square", (row + col) % 2 === 0 ? "light" : "dark");
      square.dataset.square = name;

      if (options.selected === name) square.classList.add("selected");
      if (last.includes(name)) square.classList.add("last-move");
      if (options.checkSquare === name) square.classList.add("in-check");
      if (targets.includes(name)) {
        square.classList.add(piece ? "possible-capture" : "possible-move");
      }

      if (piece !== "") {
        const img = document.createElement("img");
        img.className = "piece";
        img.src = imageBase + pieceFiles[piece];
        img.alt = piece;
        img.draggable = false;
        square.appendChild(img);
      }

      square.addEventListener("click", () => {
        options.onSquareClick?.(name, piece);
      });

      board.appendChild(square);
    }
  }
}

// Case du roi d'une couleur ("w" ou "b"), pour le surligner en cas d'échec.
function findKing(fen, color) {
  const pieces = parseFen(fen);

  for (let row = 0; row < 8; row++) {
    for (let col = 0; col < 8; col++) {
      if (pieces[row][col] === color + "K") return squareName(row, col);
    }
  }

  return null;
}
