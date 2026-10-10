# Contribuer au projet

## Flux de travail

1. Lire `AGENTS.md` et les documents liés à la tâche.
2. Créer une branche descriptive, par exemple `feature/data-quality-checks` ou `fix/return-alignment`.
3. Modifier le code par petits changements.
4. Ajouter ou mettre à jour les tests.
5. Exécuter les tests et les outils de qualité.
6. Mettre à jour la documentation si une règle, une source ou un résultat change.
7. Décrire les changements, les tests réellement exécutés et les limites restantes dans la pull request.

## Commits

Suivre une convention simple de type Conventional Commits :
- `docs: clarify source limitations`
- `feat: add return metrics`
- `fix: handle duplicate dates`
- `test: cover drawdown calculation`
- `chore: update dependencies`

## Données et secrets

- Ne jamais ajouter de clé API, mot de passe ou token.
- Ne pas committer des données dont la licence interdit la redistribution.
- Ne pas inclure de données synthétiques dans les résultats présentés comme historiques.
- Ne pas supprimer un outlier sans justification documentée.

## Checklist avant contribution

- [ ] Tests pertinents exécutés.
- [ ] Résultats des tests rapportés honnêtement.
- [ ] Documentation mise à jour.
- [ ] Aucun secret ajouté.
- [ ] Aucun changement non lié ou réécriture globale non nécessaire.
