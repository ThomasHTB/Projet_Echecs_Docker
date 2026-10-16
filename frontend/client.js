
const statusElement = document.getElementById("connection-status");

// À adapter au port et à la route de Raphaël.
// Cette adresse est un exemple pour le développement local.
const chessSocket = new ChessSocket(
  "ws://localhost:8000/ws",
  {
    onOpen() {
      statusElement.textContent = "Connecté au serveur";
    },

    onClose() {
      statusElement.textContent = "Déconnecté — reconnexion en cours…";
    },

    onError() {
      statusElement.textContent = "Erreur de connexion";
    },

    onMessage(message) {
      switch (message.type) {
        case "game_state":
          console.log("État de la partie reçu :", message);
          // TODO : mettre à jour l'échiquier depuis l'état serveur.
          break;

        case "move_made":
          console.log("Coup confirmé :", message);
          // TODO : appliquer le coup validé.
          break;

        case "error":
          console.error("Erreur serveur :", message.message);
          break;

        default:
          console.warn("Message inconnu :", message.type);
      }
    }
  }
);

// chessSocket.connect();