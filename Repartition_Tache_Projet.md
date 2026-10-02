Contexte du projet

Dans le cadre de notre projet, nous avons choisi de développer une application web permettant à plusieurs utilisateurs de jouer aux échecs en ligne depuis des postes différents.

L'objectif est de proposer une plateforme simple permettant à deux joueurs de se connecter, de créer ou rejoindre une partie et de jouer une partie d'échecs en temps réel. Chaque joueur doit pouvoir visualiser l'échiquier depuis son propre poste et voir immédiatement les coups joués par son adversaire.

Pour répondre à ce besoin, nous avons choisi une architecture composée de trois services Docker :

Un frontend chargé de l'affichage de l'échiquier et de l'interaction avec les joueurs.
Un backend chargé de la logique du jeu, de la gestion des parties et de la communication en temps réel entre les joueurs.
Une base de données PostgreSQL permettant de stocker les utilisateurs, les parties et l'historique des coups.

La communication entre le frontend et le backend se fera notamment grâce aux "WebSockets ?", afin de transmettre les coups aux deux joueurs en temps réel sans qu'ils aient besoin de recharger la page.

L'ensemble de l'application sera conteneurisé avec Docker Compose, permettant de démarrer facilement les différents services et de reproduire le même environnement sur plusieurs postes.

Ce projet nous permet ainsi de mettre en pratique plusieurs notions liées au développement web et à la conteneurisation : création d'une API, communication temps réel, gestion d'une base de données, création de Dockerfiles, orchestration de plusieurs conteneurs, gestion des réseaux Docker et mise en place de bonnes pratiques de sécurité.


Thomas H → Frontend : échiquier + interface.

Raphael B → Backend : règles, parties, WebSocket.

Martin GK → Database + Docker : PostgreSQL, modèles de données, Dockerfiles, docker-compose, sécurité.
