# Logique métier frontend — `domain/`

Atomic Design (`components/`) = **comment ça s’affiche**.  
`domain/` = **les règles du voyage**, sans React, sans HTML, sans fetch.

Pas encore de fonctions : seulement l’endroit, le découpage, et qui a le droit d’importer quoi.

---

## Les trois tiroirs, jamais mélangés

```text
frontend/src/
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
api        ──► domain    oui, si on transforme une réponse serveur
api        ──► components INTERDIT
```

**Seul `routes/` assemble.** Le hook produit est l’état React ; le domaine reste des fonctions pures.  
Un organisme reçoit des props déjà calculées. Il ne décide pas si la destination est couverte.

---

## Découpage de `domain/`

Un dossier = **un morceau de produit**. Un dossier n’importe pas les autres sans raison. Si deux domaines se parlent trop, la règle est au mauvais endroit.

```text
frontend/src/domain/
  wish/           # le texte du voyage
  coverage/       # on peut planifier ici, ou pas
  panel/          # tags, sections, réponses
  constraints/    # budget, voyageurs, dates
  plan/           # itinéraire jour par jour
```

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
- un jour a un ordre, des activités, un ordre de grandeur de prix
- le total reste dans le budget (règle de lecture côté front)

Ne contient pas `PlanTimeline` ni `PlanDayCard`.

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

`api/` contient le `queryClient` TanStack Query et le client généré (`generated/`, via `pnpm gen:api`). Pas de règles métier là-dedans.

---

## Ordre plus tard, au code

1. types + fonctions pures dans le dossier concerné (`wish`, `panel`, …) ;
2. tests sans React (le domaine se teste tout seul) ;
3. hook du même sujet dans `hooks/` (voir HOOKS.md) ;
4. la page utilise le hook, puis passe le résultat aux organismes.

Jusque-là, les dossiers existent, les responsabilités sont nommées, aucune fonction n’est écrite.
