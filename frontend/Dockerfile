# ============================================================
#  Frontend : Nginx sert les fichiers statiques et relaie /api et /ws
#  vers le backend (reverse proxy).
#  Image "unprivileged" : Nginx tourne avec un utilisateur NON-root
#  et écoute donc sur 8080 (les ports < 1024 sont réservés à root).
# ============================================================
FROM nginxinc/nginx-unprivileged:1.27-alpine

# Configuration du serveur (remplace celle par défaut)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Seuls les fichiers utiles au navigateur sont copiés dans l'image
COPY index.html style.css script.js websocket.js client.js /usr/share/nginx/html/
COPY pieces/*.svg /usr/share/nginx/html/pieces/

EXPOSE 8080

# Docker vérifie régulièrement que Nginx répond (statut visible dans "docker compose ps")
HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
  CMD wget -q --spider http://127.0.0.1:8080/ || exit 1
