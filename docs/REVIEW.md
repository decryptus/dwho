# Revue du socle dwho — septembre 2026

## Pertinence

Dwho est la partie la plus directement utile aux services existants : elle partage
les conventions de configuration, les registres de plugins/modules, les notifications
et les adaptateurs. Covenant et Auton utilisent réellement ces interfaces. La supprimer
impliquerait de dupliquer ou de migrer ces comportements dans chaque application.

## Qualité du code

Les responsabilités des classes sont généralement identifiables, les erreurs sont
souvent contextualisées et les interfaces sont assez petites pour être testées.
Les défauts observés concernent surtout la propriété des données mutables, le cycle
de vie des ressources et les frontières texte/octets. Ce sont des défauts de fiabilité
plus que de choix d'algorithmes sophistiqués.

La version 0.3.60 corrige les défauts reproduits dans le chargeur, Redis, les connexions
SQL, les notifications, inotify et les sous-processus. Les identifiants SQL sont validés.
Le format crypto historique reste disponible ; le nouveau format authentifié est
explicitement distinct. Les objets pickle personnalisés demandent désormais
`trusted=True`, ce qui doit être vérifié par les applications concernées.

## Architecture et suite

Conserver le rôle de bibliothèque applicative, en réduisant progressivement les
registres globaux et les dépendances obligatoires. Définir ensuite des interfaces
explicites pour les adaptateurs et une politique commune de démarrage/arrêt.
Ne pas mélanger cette migration architecturale avec un changement silencieux de
format de données. L'ancienne cryptographie CBC reste non authentifiée ; elle est
maintenue pour la migration, pas présentée comme un nouveau protocole sûr.

Les tests couvrent les défauts reproduits et les applications utilisatrices ciblées.
Ils ne prouvent pas l'absence de tout défaut dans tous les plugins externes, systèmes
de fichiers, versions Redis ou pilotes SQL. La recommandation est de conserver et
stabiliser ce socle, pas de le réécrire entièrement.
