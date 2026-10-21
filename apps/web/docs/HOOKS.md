# Hooks — `hooks/`

Un hook, c’est du **React** (`useState`, `useEffect`, plus tard `useQuery`).  
Ce n’est **ni** de l’UI Atomic Design, **ni** une règle métier.

- `domain/` = fonctions pures, **sans** React → **aucun hook ici**
- `components/` = affichage → pas de `useQuery`, pas de règles “est-ce couvert ?”
- `hooks/` = l’adaptateur React : état local + appels au domaine (et plus tard à `api/`)

Pas encore de code : seulement l’endroit et qui a le droit de les importer.

---

## Deux familles, deux dossiers

```text
apps/web/src/hooks/
  ui/             # visuel uniquement — les composants PEUVENT s’en servir
  wish/           # état du souhait — SEULES les pages (routes/)
  coverage/
  panel/
  constraints/
  plan/
  quote/
```

Même découpage que `domain/`, pour ne pas tout mélanger dans un `hooks/` fourre-tout.

| Famille | Question | Qui l’importe | Exemple plus tard |
|---|---|---|---|
| `hooks/ui/` | Comment l’UI se comporte ? | molécules / organismes / pages | `useReducedMotion`, ouvrir/fermer, hover |
| `hooks/<sujet>/` | Quel état métier sur cet écran ? | **routes/ seulement** | `useWish`, `usePanel`, `usePlan` |

---

## Règles d’import

```text
hooks/ui          ──►  domain          INTERDIT  (sauf `useAgency` → `domain/agency`)
hooks/ui          ──►  api             INTERDIT
hooks/ui          ──►  components      INTERDIT

hooks/wish (etc.) ──►  domain/wish     oui
hooks/wish        ──►  api             INTERDIT   (le fetch, c’est api/)
hooks/wish        ──►  components      INTERDIT
hooks/wish        ──►  hooks/ui        oui, si besoin d’un détail visuel

components        ──►  hooks/ui        oui
components        ──►  useTranslation  oui        (les textes, voir I18N.md)
components        ──►  hooks/wish      INTERDIT   (sinon PreferencePanel “sait” trop)

routes            ──►  hooks/*         oui
routes            ──►  domain          oui, si un calcul one-shot sans état
api               ──►  hooks           INTERDIT
domain            ──►  hooks           INTERDIT
```

Chaîne d’un écran :

```text
Page (routes/)
  → hook produit (hooks/panel)
      → fonctions pures (domain/panel)
  → organisme (PreferencePanel)
      → molécules / atomes
      → éventuellement hooks/ui (animation, reduce-motion)
```

---

## Ce que chaque dossier produit fera

Ce sont des **noms** pour plus tard, pas des fichiers à remplir maintenant.

| Dossier | Le hook retiendra | Il demandera à |
|---|---|---|
| `hooks/wish/` | le texte en cours de saisie | `domain/wish` (valide ?) |
| `hooks/coverage/` | couvert ou pas, suggestions | `domain/coverage` |
| `hooks/panel/` | quels tags sont on | `domain/panel` |
| `hooks/constraints/` | budget, voyageurs, dates | `domain/constraints` |
| `hooks/plan/` | le plan affiché, jour ouvert | `domain/plan` |
| `hooks/quote/` | le devis affiché, accepter / refuser | `domain/quote` |
| `hooks/ui/` | motion, media query, faits d’agence pour le logo et le pied de page | personne côté métier, sauf `useAgency` → `domain/agency` |

Quand le backend existera : un hook **API** (`useCreateWish`, TanStack Query) vivra dans `api/`, pas dans `hooks/wish/`. Le hook produit pourra *appeler* le hook API depuis la **page**, ou la page appellera les deux. Le domaine reste sans `fetch`.

---

## Ce qu’on ne fait pas

- `useState` métier dans `PreferencePanel` (le panneau affiche `selected` / `onToggle`)
- `useEffect` + `fetch` dans un organisme
- un hook dans `domain/` (ça casserait les tests sans React)
- un seul `useNovoya.ts` de 400 lignes

---

## Ordre plus tard, au code

1. fonctions dans `domain/` + tests sans React ;
2. hook du même nom dans `hooks/<sujet>/` qui appelle ces fonctions ;
3. la page utilise le hook et passe des props aux organismes ;
4. `hooks/ui/` seulement pour un comportement visuel partagé.
