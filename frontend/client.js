
const statusElement = document.getElementById("connection-status");
const createButton = document.getElementById("create-game-btn");
const gameMessage = document.getElementById("game-message");
const gameCodeContainer = document.getElementById("game-code-container");
const gameCodeElement = document.getElementById("game-code");
const copyButton = document.getElementById("copy-code-btn");

let currentGameId = null;

const chessSocket = new ChessSocket("ws://localhost:8000/ws", {
  onOpen() {
    statusElement.textContent = "Connecté au serveur";
    createButton.disabled = false;
    gameMessage.textContent = "Tu peux créer une partie.";
  },

  onClose() {
    statusElement.textContent =
      "Déconnecté — reconnexion en cours…";

    createButton.disabled = true;
    gameMessage.textContent =
      "Serveur indisponible. Attente de reconnexion…";
  },

  onError() {
    statusElement.textContent = "Erreur de connexion";
  },

  onMessage(message) {
    console.log("Message reçu :", message);

    switch (message.type) {
      case "game_created": {
        if (!message.game_id) {
          gameMessage.textContent =
            "Erreur : le serveur n'a pas fourni de code.";
          break;
        }

        currentGameId = message.game_id;
        gameCodeElement.textContent = currentGameId;
        gameCodeContainer.hidden = false;

        gameMessage.textContent =
          "Partie créée ! Partage ce code avec ton adversaire.";

        createButton.disabled = false;
        createButton.textContent = "Créer une autre partie";
        break;
      }

      case "game_state":
        console.log("État de la partie :", message);
        break;

      case "move_made":
        console.log("Coup confirmé :", message);
        break;

      case "error":
        gameMessage.textContent =
          message.message || "Une erreur est survenue.";
        createButton.disabled = false;
        break;

      default:
        console.warn("Type de message inconnu :", message.type);
    }
  }
});

createButton.addEventListener("click", () => {
  if (currentGameId) {
    const confirmed = window.confirm(
      "Créer une nouvelle partie ? Le code actuel sera remplacé."
    );

    if (!confirmed) return;
  }

  if (!chessSocket.send({ type: "create_game" })) {
    gameMessage.textContent =
      "Impossible d'envoyer la demande : serveur déconnecté.";
    return;
  }

  currentGameId = null;
  gameCodeContainer.hidden = true;
  createButton.disabled = true;
  gameMessage.textContent =
    "Demande envoyée. Attente du code du serveur…";
});

copyButton.addEventListener("click", async () => {
  if (!currentGameId) return;

  try {
    await navigator.clipboard.writeText(currentGameId);
    gameMessage.textContent = "Code copié ! Tu peux le partager.";
  } catch (error) {
    gameMessage.textContent =
      "Copie automatique impossible. Sélectionne le code pour le copier.";
  }
});

chessSocket.connect();
