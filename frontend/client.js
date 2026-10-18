// ==============================
//  CLIENT DE JEU
//  Fait le lien entre l'interface, l'échiquier (script.js) et le serveur
//  (websocket.js). Le serveur valide tous les coups : ici on ne fait que proposer.
// ==============================

const statusElement = document.getElementById("connection-status");
const nameInput = document.getElementById("name-input");
const codeInput = document.getElementById("code-input");
const createButton = document.getElementById("create-game-btn");
const joinButton = document.getElementById("join-game-btn");
const gameMessage = document.getElementById("game-message");
const lobbySection = document.getElementById("lobby");
const gameSection = document.getElementById("game");
const gameCodeElement = document.getElementById("game-code");
const copyButton = document.getElementById("copy-code-btn");
const resignButton = document.getElementById("resign-btn");
const leaveButton = document.getElementById("leave-btn");
const opponentBar = document.getElementById("opponent-bar");
const meBar = document.getElementById("me-bar");
const movesList = document.getElementById("moves-list");
const promotionDialog = document.getElementById("promotion-dialog");

const SESSION_KEY = "chessdock.session"; // partie en cours de CET onglet
const NAME_KEY = "chessdock.name";       // pseudo mémorisé pour la prochaine fois

const END_REASONS = {
  checkmate: "échec et mat",
  stalemate: "pat",
  insufficient_material: "matériel insuffisant",
  threefold_repetition: "triple répétition",
  fivefold_repetition: "quintuple répétition",
  fifty_moves: "règle des 50 coups",
  seventyfive_moves: "règle des 75 coups",
  resignation: "abandon"
};

// État local de l'interface
let session = loadSession(); // { gameId, token, color } ou null
let state = null;            // dernier "game_state" reçu
let selected = null;         // case sélectionnée, ex : "e2"
let rejoinPending = false;

// ---------- Stockage navigateur (peut être bloqué : on protège chaque accès) ----------

function loadSession() {
  try {
    return JSON.parse(sessionStorage.getItem(SESSION_KEY));
  } catch {
    return null;
  }
}

function saveSession(value) {
  session = value;
  try {
    if (value) sessionStorage.setItem(SESSION_KEY, JSON.stringify(value));
    else sessionStorage.removeItem(SESSION_KEY);
  } catch { /* stockage indisponible : la reconnexion auto ne marchera pas, tant pis */ }
}

try {
  nameInput.value = localStorage.getItem(NAME_KEY) || "";
} catch { /* idem */ }

// ---------- Connexion WebSocket ----------
// On passe par la MÊME adresse que la page (Nginx relaie /ws vers le backend).
// Le backend n'a aucun port ouvert sur la machine : c'est voulu.
const wsUrl = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`;

const chessSocket = new ChessSocket(wsUrl, {
  onOpen() {
    statusElement.textContent = "🟢 Connecté au serveur";
    setLobbyEnabled(true);

    // Après une coupure ou un rechargement de page : on revient dans sa partie.
    if (session) {
      rejoinPending = true;
      chessSocket.send({ type: "rejoin_game", game_id: session.gameId, token: session.token });
      showMessage("Reconnexion à ta partie…");
    } else {
      showMessage("Choisis un pseudo, puis crée ou rejoins une partie.");
    }
  },

  onClose() {
    statusElement.textContent = "🔴 Déconnecté — reconnexion en cours…";
    setLobbyEnabled(false);
  },

  onError() {
    statusElement.textContent = "🔴 Erreur de connexion";
  },

  onMessage(message) {
    switch (message.type) {
      case "game_created":
      case "game_joined":
        rejoinPending = false;
        saveSession({
          gameId: message.game_id,
          // Le jeton n'est envoyé qu'à la création / au premier « rejoindre »
          token: message.token || session?.token,
          color: message.color
        });
        selected = null;
        showGame();
        showMessage(message.type === "game_created"
          ? "Partie créée ! Envoie le code à ton adversaire."
          : "");
        break;

      case "game_state":
        state = message;
        updateGame();
        break;

      case "error":
        if (rejoinPending) {
          // La partie n'existe plus ou le jeton est invalide : retour au lobby.
          rejoinPending = false;
          saveSession(null);
          showLobby();
        }
        showMessage("⚠️ " + (message.message || "Une erreur est survenue."));
        break;

      default:
        console.warn("Type de message inconnu :", message.type);
    }
  }
});

// ---------- Affichage ----------

function showMessage(text) {
  gameMessage.textContent = text;
}

function setLobbyEnabled(enabled) {
  createButton.disabled = !enabled;
  joinButton.disabled = !enabled;
}

function showLobby() {
  state = null;
  selected = null;
  lobbySection.hidden = false;
  gameSection.hidden = true;
}

function showGame() {
  lobbySection.hidden = true;
  gameSection.hidden = false;
  gameCodeElement.textContent = session.gameId;
}

function playerLabel(color) {
  const player = state.players[color];
  const icon = color === "white" ? "♔" : "♚";

  if (!player.name) return `${icon} En attente d'un adversaire…`;

  const offline = player.connected ? "" : " (déconnecté)";
  const turn = state.status === "playing" && state.turn === color[0] ? "  ⏳" : "";
  return `${icon} ${player.name}${offline}${turn}`;
}

function describeStatus() {
  if (state.status === "waiting") {
    return "En attente de l'adversaire… Partage le code : " + state.game_id;
  }

  if (state.status === "finished") {
    const reason = END_REASONS[state.end_reason] || state.end_reason;
    if (state.result === "1/2-1/2") return `Partie nulle (${reason}).`;

    const winner = state.result === "1-0" ? "white" : "black";
    const youWon = winner === session.color;
    return `${youWon ? "🏆 Tu as gagné" : "Tu as perdu"} (${reason}).`;
  }

  const myTurn = state.turn === session.color[0];
  return (state.check ? "Échec ! " : "") + (myTurn ? "À toi de jouer." : "Tour de l'adversaire.");
}

function updateGame() {
  if (!state || !session) return;

  const me = session.color;
  const opponent = me === "white" ? "black" : "white";

  opponentBar.textContent = playerLabel(opponent);
  meBar.textContent = playerLabel(me) + " (toi)";
  resignButton.disabled = state.status !== "playing";
  showMessage(describeStatus());

  // Historique : "1. e4 e5", "2. Nf3 Nc6"...
  movesList.innerHTML = "";
  for (let i = 0; i < state.moves.length; i += 2) {
    const li = document.createElement("li");
    li.textContent = state.moves[i] + (state.moves[i + 1] ? "  " + state.moves[i + 1] : "");
    movesList.appendChild(li);
  }

  drawBoard();
}

function drawBoard() {
  const targets = selected
    ? state.legal_moves.filter((m) => m.startsWith(selected)).map((m) => m.slice(2, 4))
    : [];

  renderBoard({
    fen: state.fen,
    orientation: session.color,
    selected,
    targets,
    lastMove: state.last_move,
    checkSquare: state.check ? findKing(state.fen, state.turn) : null,
    onSquareClick: handleSquareClick
  });
}

// ---------- Jouer un coup ----------

async function handleSquareClick(square, piece) {
  if (!state || state.status !== "playing") return;

  const myColor = session.color[0];
  if (state.turn !== myColor) return;

  // Clic sur une de mes pièces : (re)sélection
  if (piece && piece[0] === myColor) {
    selected = selected === square ? null : square;
    drawBoard();
    return;
  }

  if (!selected) return;

  // Le serveur nous a envoyé la liste des coups légaux : on vérifie avant d'envoyer.
  const candidates = state.legal_moves.filter((m) => m.startsWith(selected + square));
  const from = selected;
  selected = null;

  if (candidates.length === 0) {
    drawBoard();
    return;
  }

  // Plusieurs candidats = promotion (e7e8q, e7e8r...) : on demande la pièce.
  let promotion = null;
  if (candidates.length > 1) {
    promotion = await askPromotion();
  }

  chessSocket.send({ type: "move", from, to: square, promotion });
}

function askPromotion() {
  return new Promise((resolve) => {
    promotionDialog.returnValue = "";
    promotionDialog.addEventListener(
      "close",
      () => resolve(promotionDialog.returnValue || "q"), // fermé avec Échap : dame
      { once: true }
    );
    promotionDialog.showModal();
  });
}

// ---------- Boutons ----------

function readName() {
  const name = nameInput.value.trim();

  if (!name) {
    showMessage("⚠️ Choisis d'abord un pseudo.");
    nameInput.focus();
    return null;
  }

  try {
    localStorage.setItem(NAME_KEY, name);
  } catch { /* stockage indisponible */ }

  return name;
}

createButton.addEventListener("click", () => {
  const name = readName();
  if (!name) return;

  if (!chessSocket.send({ type: "create_game", name })) {
    showMessage("Impossible d'envoyer la demande : serveur déconnecté.");
    return;
  }

  showMessage("Création de la partie…");
});

joinButton.addEventListener("click", () => {
  const name = readName();
  if (!name) return;

  const code = codeInput.value.trim().toUpperCase();
  if (code.length !== 6) {
    showMessage("⚠️ Le code fait 6 caractères.");
    codeInput.focus();
    return;
  }

  if (!chessSocket.send({ type: "join_game", name, game_id: code })) {
    showMessage("Impossible d'envoyer la demande : serveur déconnecté.");
  }
});

codeInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") joinButton.click();
});

copyButton.addEventListener("click", async () => {
  if (!session) return;

  try {
    await navigator.clipboard.writeText(session.gameId);
    showMessage("Code copié ! Tu peux le partager.");
  } catch {
    showMessage("Copie automatique impossible. Sélectionne le code pour le copier.");
  }
});

resignButton.addEventListener("click", () => {
  if (window.confirm("Abandonner la partie ?")) {
    chessSocket.send({ type: "resign" });
  }
});

leaveButton.addEventListener("click", () => {
  if (state?.status === "playing" &&
      !window.confirm("Quitter ? Tu ne pourras plus revenir dans cette partie.")) {
    return;
  }

  chessSocket.send({ type: "leave_game" });
  saveSession(null);
  showLobby();
  showMessage("Tu as quitté la partie.");
});

chessSocket.connect();
