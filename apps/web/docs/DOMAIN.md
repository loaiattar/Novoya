# Logique métier frontend — `domain/`

Atomic Design (`components/`) = **comment ça s’affiche**.  
`domain/` = **les règles du voyage**, sans React, sans HTML, sans fetch.

Pas encore de fonctions : seulement l’endroit, le découpage, et qui a le droit d’importer quoi.

---

## Les trois tiroirs, jamais mélangés

```text
apps/web/src/
  components/     # UI (Atomic Design)     → voir ATOMIC.md
  domain/         # règles métier          → ce fichier  (PAS de hooks)
  hooks/          # état React autour du domaine → voir HOOKS.md
  api/            # HTTP vers le backend   → plus tard, pas des règles
  routes/         # pages = unique colle
```

| Tiroir | Question | Exemple |
|---|---|---|
| `components/` | À quoi ça ressemble ? | un tag coché, un slider |
| `domain/` | Est-ce vrai / permis / cohérent ? | budget ≥ 0, destination couverte |
| `api/` | Comment on parle au serveur ? | `POST /wishes` |
| `hooks/` | Quel état React autour d’une règle ? | `usePanel` appelle `domain/panel` |
| `routes/` | Quel écran, avec quelles données ? | Accueil utilise le hook, puis `WishHero` |

---

## Règles d’import

```text
routes  ──►  hooks      oui
routes  ──►  domain     oui (calcul one-shot sans état)
routes  ──►  api        oui (plus tard)
routes  ──►  components oui

hooks   ──►  domain     oui
hooks   ──►  components INTERDIT
hooks   ──►  api        INTERDIT   (le fetch reste dans api/)

domain  ──►  components  INTERDIT
domain  ──►  hooks       INTERDIT
domain  ──►  api         INTERDIT   (le domaine ne fetch pas)
domain  ──►  routes      INTERDIT

components ──► domain    INTERDIT   (un bouton ne connaît pas un “wish”)
components ──► api       INTERDIT
i18n       ──► domain    oui, pour la règle de langue (domain/i18n)
api        ──► domain    oui, si on transforme une réponse serveur
api        ──► components INTERDIT
```

**Seul `routes/` assemble.** Le hook produit est l’état React ; le domaine reste des fonctions pures.  
Un organisme reçoit des props déjà calculées. Il ne décide pas si la destination est couverte.

---

## Découpage de `domain/`

Un dossier = **un morceau de produit**. Un dossier n’importe pas les autres sans raison. Si deux domaines se parlent trop, la règle est au mauvais endroit.

```text
apps/web/src/domain/
  wish/           # le texte du voyage
  coverage/       # on peut planifier ici, ou pas
  panel/          # tags, sections, réponses
  constraints/    # budget, voyageurs, dates
  plan/           # itinéraire jour par jour
  quote/          # le devis de l’agence
  auth/           # session : nom affiché, redirection sûre, clés des erreurs de connexion
  agency/         # faits d’agence lus dans brand/agency.json (jamais un to_check)
  i18n/           # quelle langue afficher (resolveLocale)
  catalog/        # partenaires et offres de l’admin : mêmes contrôles que l’API, corps envoyés
```

Le domaine ne contient **aucun libellé d’interface** : il renvoie une clé de traduction, et la page la traduit ([I18N.md](I18N.md)). Les **faits** d’agence (nom, e-mail, SIRET…) viennent de `brand/agency.json` : ce ne sont pas des textes à traduire.

### `wish/`

Le souhait : la phrase libre.

- le texte est-il assez précis pour continuer ?
- extraire une destination / un mois s’ils sont dans la phrase  
  (ex. “une semaine calme au bord de la mer **en mai**”)

Ne contient pas le champ de saisie (`WishField` est une molécule).

### `coverage/`

Est-ce que Novoya **couvre** cette destination ?

- oui → on peut ouvrir le panneau
- non → liste de destinations proches / couvertes à proposer

Ne contient pas l’écran d’erreur (`CoverageEmpty` est un organisme).

### `panel/`

Le panneau de préférences.

- un tag est off, précoché, ou on
- basculer un tag
- construire l’objet “réponses” à envoyer plus tard
- quelles sections afficher (le JSON, pas le rendu)

Ne contient pas `TagButton` ni `PreferencePanel`.

### `constraints/`

Les contraintes chiffrées, dernière étape du panneau.

- budget max > 0
- nombre de voyageurs ≥ 1
- dates dans le bon ordre (retour après aller)

Ne contient pas le slider ni le stepper.

### `plan/`

Le plan généré.

- plan “agent” vs plan “populaire / featured”
- un jour a un ordre et des activités
- le plan n’a **aucun prix** : les prix sont négociés par un agent et n’apparaissent que dans le devis

Ne contient pas `PlanTimeline` ni `PlanDayCard`.

### `quote/`

Le devis écrit par l’agent.

- statut : demandé, prêt, accepté, refusé
- le client peut accepter ou refuser seulement un devis prêt

Le total est calculé par le backend. Le front l’affiche, il ne le recalcule pas.

Ne contient pas `QuoteSummary`.

### `agency/`

Les faits de l’agence, lus **une fois** dans `brand/agency.json`.

- un champ `to_check` n’est jamais renvoyé
- une traduction encore `to_check` (souvent l’anglais) est omise
- le chemin du logo officiel, pour l’atome `Photo`

Ne contient pas `Logo` ni `SiteFooter`. Les composants passent par `hooks/ui/useAgency`.

---

## Comment une page s’en sert

Exemple : l’utilisateur envoie son souhait.

```text
Page Accueil (routes/)
  1. lit le texte du WishField          ← UI
  2. demande à domain/wish : valide ?   ← métier
  3. demande à domain/coverage : ok ?   ← métier
  4. si non → affiche CoverageEmpty     ← UI, props déjà prêtes
  5. si oui → va vers le panneau        ← navigation
```

Le composant n’a jamais su ce qu’était une “destination couverte”.  
Le domaine n’a jamais su ce qu’était un bouton.

---

## Ce qui n’entre pas dans `domain/`

- JSX, CSS, animation, **hooks React**
- `fetch`, TanStack Query, cookies
- écrans Gmail / Instagram / imports (hors périmètre)
- détails d’URL (`/wishes`) → ça, c’est `api/`

`api/` contient la config du client HTTP (`client.ts`) et le client généré (`generated/`, via `pnpm gen:api`). Le client TanStack Query est créé dans `src/router.tsx`. Pas de règles métier là-dedans.

---

## Ordre plus tard, au code

1. types + fonctions pures dans le dossier concerné (`wish`, `panel`, …) ;
2. tests sans React (le domaine se teste tout seul) ;
3. hook du même sujet dans `hooks/` (voir HOOKS.md) ;
4. la page utilise le hook, puis passe le résultat aux organismes.

Jusque-là, les dossiers existent, les responsabilités sont nommées, aucune fonction n’est écrite.
