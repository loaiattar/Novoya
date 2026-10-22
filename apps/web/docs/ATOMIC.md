# Architecture frontend — Atomic Design

Ce fichier décrit **comment le front Novoya est rangé**. Il n’y a pas encore de composants : seulement les niveaux, les dossiers, et ce qui ira dans chacun.

Novoya côté écran, c’est trois gestes :

1. l’utilisateur **écrit** le voyage qu’il veut (le souhait) ;
2. il **affine** dans un panneau de tags (préférences, puis budget / voyageurs / dates) ;
3. il **lit** un plan jour par jour, sans prix, puis demande un devis à l’agence.

Pas de Gmail, pas d’Instagram, pas d’import. Le plan n’affiche jamais de prix : seul le devis, écrit par un agent, en a un.

---

## Pourquoi Atomic Design

Sans règles, chaque page recopie boutons, tags et titres. Au bout de trois écrans, plus rien ne se ressemble.

Atomic Design coupe l’UI en **cinq niveaux**, du plus petit au plus grand. Un niveau n’a le droit d’importer **que** ce qui est plus petit que lui.

```text
Tokens        matière (couleur, typo, espace)     ← pas un composant
    ↓
Atomes        1 élément (bouton, champ, tag visuel)
    ↓
Molécules     1 geste (cocher un tag, écrire le souhait)
    ↓
Organismes    1 zone d’écran (le panneau, la timeline)
    ↓
Templates     la grille de la page, slots vides
    ↓
Pages         l’écran réel (la route)
```

**Règle d’import (jamais vers le haut) :**

- un atome n’importe **jamais** une molécule ;
- une molécule n’importe **jamais** un organisme ;
- un organisme n’importe **jamais** une page ;
- `components/` n’importe **jamais** `domain/` ni `api/` ni les hooks produit (`hooks/wish`, etc.) ;
- `components/` peut importer `hooks/ui/` (motion, media query) ;
- `components/` peut appeler `useTranslation` (`react-i18next`) : un texte relève de la présentation. Voir [I18N.md](I18N.md) ;
- **seule la page** (`routes/`) colle UI + hooks produit + métier + API.

Un organisme ne “va pas chercher” les données. Il reçoit des **props** (`label`, `selected`, `onClick`, `sections`). On peut le montrer avec du JSON fictif.

La logique métier n’est pas ici : voir [DOMAIN.md](DOMAIN.md).

---

## Dossiers

Tout vit sous `apps/web/src/`.

```text
apps/web/src/
  design/            # matière visuelle
  components/        # UI Atomic Design (ce fichier)
  domain/            # règles métier — voir DOMAIN.md
    wish/
    coverage/
    panel/
    constraints/
    plan/
    quote/
  api/               # HTTP, plus tard — pas des règles
  hooks/             # adaptateur React — voir HOOKS.md
    ui/              # visuel ; les composants peuvent l’importer
    wish/ coverage/ panel/ constraints/ plan/ quote/   # pages seulement
  routes/            # pages = unique colle UI + métier + API
```

Les pages sont les fichiers de `src/routes/`. `main.tsx` monte le routeur, et `router.tsx` crée le routeur et le client TanStack Query. Ne pas mettre de logique métier dans `design/` ni dans `components/`.


---

## 0. Tokens — la matière

Ce n’est pas de l’UI. C’est la palette avec laquelle tout le monde peint.

| Token | Contenu |
|---|---|
| Couleur | fond, surface, texte, accent, tag off / précoché / on, danger, badge “populaire” |
| Typo | 2 familles max : un titre éditorial + une UI |
| Espace | grille 8px |
| Radius, z-index | coins et superpositions |
| Motion (primitives) | durées `swift` / `ritual` / `scenic`, easings nommés |

Les animations “wow” (la phrase qui se brise en tags, la constellation, les jours qui apparaissent) **ne sont pas des tokens**. Ce sont des **scènes**, dans `design/motion/scenes/`, appelées par un organisme ou un template.

---

## 1. Atomes — une seule pièce

Un atome = un élément. Pas de label + champ + bouton ensemble. Pas d’histoire produit.

| Nom | Rôle |
|---|---|
| `Button` | primaire, ghost, icône |
| `Text` / `Heading` | texte courant et titres |
| `Icon` | icône seule |
| `Input` / `Textarea` | champ nu, sans label |
| `Tag` | pastille visuelle (off / précoché / on via props) |
| `Badge` | “populaire”, “couvert” |
| `Avatar` | photo / initiale |
| `Divider` | séparation |
| `Logo` | mot-symbole de l’agence, via `Photo` (WebP) |
| `GoogleLogo` | le « G » de Google (`public/icons/google.svg`) |
| `SkeletonBone` | placeholder de chargement |
| `ProgressDot` | un point du rituel de génération |
| `Price` | montant formaté (1 800 €), seulement dans le devis et le budget |

Dès qu’il faut un libellé **et** un champ **et** une action → ce n’est plus un atome, c’est une **molécule**.

---

## 2. Molécules — un geste Novoya

C’est le vrai vocabulaire de l’app. Si ce niveau est propre, le reste s’assemble.

| Nom | Fait de | Geste |
|---|---|---|
| `WishField` | Textarea + Button + halo | écrire le souhait et l’envoyer |
| `TagButton` | Tag + label + état cliquable | cocher / décocher une préférence |
| `SectionTitle` | kicker + titre + hint | nommer une section du panneau |
| `BudgetSlider` | label + slider + Price | fixer le budget max |
| `GoogleButton` | Icon + Button | “Continuer avec Google” |
| `TextField` | label + Input + message d’erreur | un champ de formulaire (e-mail, mot de passe) |
| `TextAreaField` / `SelectField` / `CheckField` | label + Textarea, select ou case à cocher | un champ des formulaires admin |
| `TravelerStepper` | boutons − / + et un nombre | nombre de voyageurs |
| `DateRangeField` | deux dates | départ / retour |
| `CoverageHint` | Text + Badge | on couvre / on ne couvre pas cette destination |
| `SuggestedDestination` | nom + action | proposer une destination couverte |
| `StatusLine` | ProgressDot + texte | “on cale les soirées…” |
| `RecapChip` | Tag figé | un choix déjà fait, compacté |
| `PlanDayStamp` | jour + date | “Jour 3 · mercredi” |
| `FeaturedBadge` | Badge + texte | plan catalogue / populaire |
| `NavItem` | Icon + label | entrée de navigation |
| `HomeLink` | Logo dans un lien accueil | marque cliquable |
| `EmptyNote` | texte + action optionnelle | état vide élégant |

Une molécule **ne sait pas** ce qu’est un “wish” métier. Elle reçoit `value`, `onChange`, `label`.

---

## 3. Organismes — une zone d’écran

Un organisme est une **région** que tu poses dans un template. Toujours alimenté par des props.

| Nom | Contient | Où on le voit |
|---|---|---|
| `AppHeader` | HomeLink, NavItem, Avatar | presque partout |
| `SiteFooter` | HomeLink, contact confirmé, mentions légales | toutes les pages sauf la connexion (les pages connectées via `AppShell`) |
| `WishHero` | WishField, CoverageHint | accueil |
| `CoverageEmpty` | CoverageHint + SuggestedDestination[] | destination non couverte |
| `PanelSection` | SectionTitle + TagButton[] | une section du panneau (style, rythme…) |
| `PreferencePanel` | PanelSection × N | le cœur de l’app |
| `ConstraintsStep` | BudgetSlider, TravelerStepper, DateRangeField | dernière étape du panneau |
| `ChoiceRecap` | RecapChip[] + Button | “voilà ce que tu as choisi” |
| `GenerationRitual` | StatusLine + scène motion | pendant que le plan se construit |
| `PlanTimeline` | PlanDayCard[] | le plan |
| `PlanDayCard` | tampon du jour, activités (sans prix) | un jour |
| `DayDetail` | contenu d’un jour ouvert | détail |
| `SignInForm` | GoogleButton, Divider, TextField × 2, Button, lien “mot de passe oublié” | connexion |
| `SignUpForm` | GoogleButton, Divider, TextField × 2, Button | inscription |
| `EmailForm` | TextField e-mail + Button | mot de passe oublié, renvoyer l’e-mail de vérification |
| `ResetPasswordForm` | TextField mot de passe + Button | nouveau mot de passe |
| `ChangePasswordForm` | TextField × 2 + Button | réglages du compte |
| `PartnersTable` / `OffersTable` | tableau, liens, cases mise en avant / masquée | admin des partenaires et des offres |
| `PartnerForm` / `OfferForm` | champs, note « à modifier dans DÉTOUR » si la ligne est importée | création et modification |
| `QuoteSummary` | lignes du devis, Price total, lien PDF, Button accepter / refuser | le devis |
| `SavedTripCard` | titre, dates, Badge (statut du devis) | liste “mes voyages” |
| `OnboardingSlide` | titre + texte + visuel | intro |

**`PreferencePanel`** est volontairement générique : il reçoit `sections` (id, titre, tags) et `onToggle(tagId)`. Il n’a pas besoin de connaître les sections à l’avance — c’est le JSON du backend, plus tard, qui les remplit.

---

## 4. Templates — la planche vide

Pas de vrais textes. Seulement la géométrie et les **slots** (`header`, `hero`, `main`, `cta`).

Le template gère la **transition de page** (entrée / sortie). Les organismes gèrent leur micro-animation.

| Template | Slots | Sert à |
|---|---|---|
| `AuthTemplate` | média / formulaire | connexion, inscription, e-mail, mot de passe |
| `EditorialTemplate` | header, hero, footer | splash, onboarding, accueil |
| `PanelTemplate` | header, progression, sections, CTA collant | panneau de préférences |
| `RitualTemplate` | plein écran, peu de chrome | génération du plan |
| `PlanTemplate` | header, résumé, timeline, aside (desktop) | le plan |
| `ListTemplate` | header, liste | mes voyages, réglages |

---

## 5. Pages — les écrans (routes)

Là seulement on branchera le routeur et, plus tard, l’API.

| Page | Template | Organismes principaux |
|---|---|---|
| Splash | Editorial | Logo, motion d’entrée |
| Onboarding | Editorial | OnboardingSlide (skippable) |
| Connexion | Auth | SignInForm (Google ou e-mail + mot de passe) |
| Inscription | Auth | SignUpForm |
| Vérification de l’e-mail | Auth | message + bouton “renvoyer l’e-mail” |
| Mot de passe oublié | Auth | TextField e-mail + Button |
| Nouveau mot de passe | Auth | TextField mot de passe + Button |
| Accueil | Editorial | AppHeader + WishHero |
| Destination non couverte | Editorial | CoverageEmpty |
| Panneau | Panel | PreferencePanel |
| Contraintes | Panel | ConstraintsStep |
| Recap | Panel | ChoiceRecap |
| Génération | Ritual | GenerationRitual |
| Plan | Plan | ChoiceRecap (lecture) + PlanTimeline |
| Détail d’un jour | Plan | DayDetail |
| Devis | Plan | QuoteSummary |
| Mes voyages | List | SavedTripCard[] |
| Réglages | List | compte, langue, thème |

Aucun écran “connecter une source”.

Les pages agent (file des devis, saisie des prix, partenaires et offres) vivent aussi dans `apps/web`, sous des routes réservées au rôle `agent`. La page admin des utilisateurs et de leurs rôles est réservée au rôle `admin`. Elles réutilisent les mêmes atomes et molécules. Leurs organismes seront ajoutés ici quand on les dessinera.

---

## Comment un écran s’assemble

Exemple : l’accueil.

```text
Page Accueil
  └ EditorialTemplate          ← grille (header + hero)
      ├ AppHeader              ← organisme
      │    ├ LogoMark          ← atome
      │    └ NavItem           ← molécule
      └ WishHero               ← organisme
           └ WishField         ← molécule
                ├ Textarea     ← atome
                └ Button       ← atome
```

Exemple : le panneau.

```text
Page Panneau
  └ PanelTemplate
      ├ (barre de progression) ← atomes
      └ PreferencePanel
           └ PanelSection × N
                ├ SectionTitle
                └ TagButton × N
                     └ Tag
```

Même `TagButton`, même `AppHeader`, templates différents. C’est ça “bien séparé”.

---

## Motion (couche à part)

Atomic Design ne parle pas des animations. On les **nomme** pour ne pas les recopier.

**Primitives** (`design/motion`) : durées, ressorts, `prefers-reduced-motion`.

**Scènes** (`design/motion/scenes`, un nom = un fichier, à écrire plus tard) :

| Scène | Où | Idée |
|---|---|---|
| `WishCaretHalo` | WishField | halo lié à la saisie |
| `TagSelect` | TagButton | scale + lueur au clic |
| `WishBreaksIntoTags` | WishHero → panneau | la phrase se morph en tags |
| `TagsToConstellation` | recap → génération | les tags se compressent |
| `PlanDayReveal` | PlanTimeline | jours qui arrivent au scroll |
| `PageOrchestration` | templates | entrée / sortie de page |

---

## Ce qui n’entre pas ici

- règles métier → `src/domain/` ([DOMAIN.md](DOMAIN.md))
- appels HTTP → `src/api/` (`client.ts` + `generated/` via `pnpm gen:api`)
- arbre de routes généré → `src/routeTree.gen.ts` (ne pas éditer)
- Gmail, Instagram, Docs, voyages importés

---

## Ordre quand on passera au code

1. Tokens, puis quelques atomes (`Button`, `Tag`, `Textarea`).
2. Les trois molécules produit : `TagButton`, `WishField`, `BudgetSlider`.
3. `PanelSection` → `PreferencePanel`.
4. `WishHero`, `GenerationRitual`, `PlanTimeline`.
5. Templates, puis routes.

Jusque-là, ce document **est** l’architecture : les dossiers existent, les pièces sont nommées, aucune n’est encore implémentée.
 