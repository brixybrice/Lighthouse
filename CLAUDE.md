# Lighthouse

App macOS (PySide6) de posemètre/luxmètre temps réel, pilotée par deux
capteurs ESP32/BH1750 envoyant leur mesure de luminance par UDP. Propose un
diaphragme calculé à partir de la valeur d'exposition (Lux → EV), de
l'ISO/EI, du filtre ND choisi et du temps de pose — pour la coordination
lumière sur plateau.

## Origine du nom

Un phare mesure et projette de la lumière pour guider — image directe pour
un outil qui mesure la lumière ambiante pour guider un réglage d'exposition.
Nom anglais, court, identique à l'usage en français ; même logique de
nommage que les projets voisins (Sémaphore, BodyBoard).

## Statut actuel

App fonctionnelle : panneaux capteurs carrés avec courbe animée, panneau
Settings assorti (ISO/ND/Framerate/Shutter angle), mode "Average" combinant
tous les capteurs en une seule courbe/valeur, menu bar natif (un item par
capteur, grisé si déconnecté), dialogue d'ajout/suppression de capteurs,
fenêtre flottante optionnelle. Voir "Architecture actuelle" plus bas pour
le détail fichier par fichier.

Avant d'écrire la moindre ligne de l'app, le protocole réseau réel a été
validé en direct sur le réseau du studio avec un script CLI jetable
(`scripts/probe_udp_sensors.py`) — même démarche que `rfexplorer-viewer` →
Sémaphore : prototyper contre le vrai matériel d'abord, porter dans
l'app ensuite. Résultat de cette validation : voir "Matériel et protocole"
ci-dessous.

## Origine du projet

Le calcul d'exposition vivait à l'origine dans un réseau TouchDesigner plus
large (fichier `kinovaRecord.toe`, aujourd'hui chiffré par un mot de passe
projet et donc illisible hors de TD). Le script Python `onValueChange`
d'origine servait de point de départ pour la formule :

```python
def onValueChange(channel, sampleIndex, val, prev):
    isoBase = 100
    isoVal = op('int_ISO_1').par.Value0
    isoCompense = math.log2(isoVal / isoBase)

    EV = math.log2(val) - math.log2(2.5)
    EVCompense = EV + isoCompense

    shutterSpeed = 1/60
    fstop = math.sqrt(2 ** EVCompense * shutterSpeed)
    op('table_fstop_sensor1')[0, 0] = fstop
```

`val` est la valeur reçue du capteur (déjà en lux, cf. ci-dessous), `2.5`
une constante de calibration empirique de ce montage (pas de norme
photométrique standard derrière — à recalibrer si besoin face à un
posemètre de référence, via un réglage dans l'UI plutôt qu'en dur dans le
code).

## Matériel et protocole

- Deux ESP32 + capteur **BH1750** (I2C, sortie native en lux), IP fixes sur
  le réseau du studio :
  - Capteur 1 : `192.168.5.51`, port UDP **2121**
  - Capteur 2 : `192.168.5.52`, port UDP **8000**
- **Format confirmé par test direct** (pas de doc/firmware disponible, et le
  `.toe` d'origine est chiffré) : un paquet UDP = une valeur **ASCII texte
  brute**, ex. `b'11.67'`. Ce n'est **pas** de l'OSC, malgré le contexte
  TouchDesigner qui le suggérait au départ (`python-osc` échoue à parser ces
  paquets — `ParseError: index out of range`). Décodage : simplement
  `float(data.decode().strip())`, pas de dépendance réseau externe requise.
  Débit observé et confirmé normal : ~2 messages/seconde par capteur.
- Les deux capteurs se distinguent uniquement par leur **port** d'écoute ;
  l'adresse IP source n'a pas besoin d'être filtrée pour que ça fonctionne,
  elle reste utile à titre indicatif/diagnostic dans les réglages.
- Test réalisé en cohabitation avec TouchDesigner, resté ouvert et branché
  sur les mêmes ports pendant le test (`SO_REUSEPORT` côté script de sonde).

## Formule d'exposition (Lux → EV → diaph)

```
EV_base      = log2(lux) - log2(K)          # K = 2.5 par défaut, calibration empirique, éditable
EV_iso       = EV_base + log2(ISO / 100)
EV_effectif  = EV_iso - ND_stops             # ND réduit la lumière → le diaph doit s'ouvrir davantage
fstop        = sqrt(2**EV_effectif * shutter_seconds)
```

`ND_stops` : menu déroulant valeur unique, `ND_STOPS` dans `core/exposure.py`
— None=0 jusqu'à ND2.7=9 stops par tiers de densité (OD/0.3, convention
photo standard : ND0.3=1, ND0.6=2, ND0.9=3, ND1.2=4, ND1.5=5, ND1.8=6,
ND2.1=7, ND2.4=8, ND2.7=9).
`ISO` : échelle standard par tiers de diaph, `ISO_VALUES` dans
`core/exposure.py` (25 → 25600, ex. 100, 125, 160, 200, 250, 320, 400...).
`shutter_seconds` n'est pas saisi directement : l'UI propose deux menus
séparés, **Framerate** (23.976, 24, 25, 29.97, 30, 50, 59.94, 60) et
**Shutter angle** (45, 90, 172.8, 180, 270, 360°, éditables), combinés via
`shutter_seconds_from_angle(angle, fps) = (angle/360) / fps` — raisonnement
cinéma (obturateur rotatif) plutôt qu'un temps de pose photo classique.
Défauts : ISO/EI **800**, Framerate 24, Shutter angle 172.8° (= 1/50s).

## Architecture actuelle

Même séparation cœur/UI que Sémaphore, étendue au fil des retours utilisateur
(capteurs dynamiques, réglages, icône de tray) :

```
src/lighthouse/
├── main.py                     # bootstrap QApplication (setQuitOnLastWindowClosed(False) — voir "Menu bar" ci-dessous)
├── core/                        # pas de dépendance Qt — testable sans GUI
│   ├── exposure.py              # fonctions pures EV/ISO/ND/fstop
│   ├── history.py                # SampleHistory : fenêtre temporelle glissante pour le graphe
│   ├── settings.py              # dataclass typée : capteurs (dict extensible, pas limité à 2), derniers ISO/ND/shutter, floating_window
│   ├── _storage.py               # JSON atomique (repris de Semaphore/core/_storage.py)
│   └── logging_setup.py          # RotatingFileHandler (repris de Semaphore)
├── workers/
│   └── udp_listener_worker.py    # QThread unique, select() sur N sockets UDP bruts (autant que de capteurs configurés)
└── ui/
    ├── theme.py                  # thème sombre (adapté de Semaphore/ui/theme.py)
    ├── widgets.py                 # WideComboBox — corrige le popup Qt trop étroit par défaut
    ├── graph_widget.py            # strip-chart QPainter multi-courbes, défilement temps réel (voir "Animation")
    ├── sensor_panel.py            # un panneau CARRÉ (QFrame, pas QGroupBox — voir note) par capteur
    ├── average_panel.py            # panneau CARRÉ "Average" : courbes de tous les capteurs + moyenne, une seule valeur
    ├── settings_panel.py           # panneau CARRÉ de même taille, réglages ISO/ND/Framerate/Angle + case "Average"
    ├── settings_dialog.py         # QDialog (⚙ dans settings_panel) : édition/ajout/suppression de capteurs, floating window
    ├── tray_icon.py                # une icône par capteur (ou une seule en mode Average) dans la menu bar
    └── main_window.py             # settings_panel (gauche) + panneaux capteurs OU average_panel (droite)
```

Toute l'UI (labels, boutons, messages) est en anglais — voir "Conventions".

**Capteurs dynamiques** : `AppSettings.sensors` n'est plus limité aux deux
capteurs d'origine — `SettingsDialog` permet d'en ajouter/retirer, chaque
capteur gardant son propre IP/port/K de calibration. Changer les capteurs
depuis ce dialogue redémarre `UdpListenerWorker` (`MainWindow._restart_worker`)
avec la nouvelle liste de ports.

**Graphe** : affiche le Lux brut, pas l'EV/fstop calculé — ces derniers
sautent de façon discontinue à chaque changement d'ISO/ND/shutter, ce qui
lirait comme du bruit capteur alors que ça n'en est pas. `GRAPH_HEIGHT=96`
dans `sensor_panel.py`. Supporte plusieurs courbes (`GraphSeries`,
`graph_widget.py`) — utilisé par `AveragePanel` pour superposer chaque
capteur (fin, terne) sous la moyenne (épais, vert).

**Animation (`MainWindow._animation_timer`, ~30fps)** : même intention que
la courbe animée de Sémaphore (`SpectrumPlot`, `QTimer` 30fps dans son
CLAUDE.md) — compenser un débit matériel lent (~2Hz UDP ici, ~1-2 sweeps/s
là-bas) qui donnerait sinon une sensation saccadée. Différence
d'implémentation : Sémaphore anime en interpolant entre deux sweeps
matériels ; ici, `LuxGraphWidget.paintEvent` calcule son bord droit à
partir de `time.monotonic()` (l'instant présent), pas du timestamp du
dernier échantillon — un simple `update()` à 30fps (`panel.animate()`,
appelé sur tous les panneaux, visibles ou non) suffit donc à faire défiler
tout le graphe en continu, sans interpolation de valeurs à calculer.

**Mode Average (`average_panel.py`, case à cocher dans `settings_panel.py`,
persistée dans `AppSettings.show_average`)** : les `SensorPanel` restent
toujours vivants et alimentés (`MainWindow._panels`) même quand ils ne sont
pas affichés — seul `MainWindow._rebuild_display()` change ce qui est
ajouté à `panels_layout` (les capteurs individuellement, ou `AveragePanel`
seul), via `setParent(None)` (détache, ne détruit pas) plutôt que
`deleteLater()`. La moyenne est calculée sur le **Lux brut** des capteurs
non périmés (`is_stale`) uniquement — un capteur déconnecté est exclu de
la moyenne plutôt que de la fausser avec sa dernière valeur figée. Le K de
calibration utilisé pour l'exposition moyenne est la moyenne des K par
capteur (une approximation : en toute rigueur il faudrait moyenner en
espace EV/log2, pas en Lux linéaire — mais les courbes affichées SONT le
Lux brut, donc moyenner le Lux d'abord reste le plus cohérent visuellement,
et les K sont d'ordinaire identiques entre capteurs de toute façon).

**Panneau carré (`sensor_panel.py`)** : `SensorPanel` est un `QFrame`, pas
un `QGroupBox`. Premier essai avec `QGroupBox` + `setFixedSize(220,220)` :
confirmé "pas carré" par screenshot réel de l'app (pas juste en théorie) —
le titre natif d'un `QGroupBox` réserve une marge AU-DESSUS de la bordure
(`margin-top` dans le stylesheet), donc le rectangle visiblement bordé est
plus large que haut même quand le widget lui-même fait 220×220. Le nom du
capteur est maintenant un `QLabel` gras normal, premier élément du layout,
dans un `QFrame` dont toute la boîte (220×220, `SQUARE_SIZE`) est la
bordure — plus rien n'est réservé en dehors.

Layout interne (haut → bas) : point de statut + nom du capteur sur une
ligne (`name_row`, point à GAUCHE du nom, pas à côté de l'IP), adresse
IP:port seule en dessous, mesures (lux/EV/fstop), un `addStretch(1)`, puis
le graphe — le stretch pousse le graphe jusqu'au bord bas du carré tout en
créant l'espacement voulu autour des mesures, sans avoir à calculer de
marge fixe.

**Fenêtre principale ajustée au contenu** : `MainWindow._fit_to_content()`
(appelée à la fin de `__init__` et après `_rebuild_sensor_panels()`) fait
`setMinimumSize(0,0)` + `setMaximumSize(QWIDGETSIZE_MAX,...)` puis
`adjustSize()` sur le central widget et la fenêtre — plutôt qu'un
`window.resize(640, 420)` deviné à la main dans `main.py` qui laissait un
vide sous les carrés (220px de haut + marges ≠ 420). Comme les panneaux
sont `setFixedSize`, `adjustSize()` calcule exactement la bonne taille.

**Menu bar (tray, `tray_icon.py`)** : `SensorTrayIcons` possède un
`NSStatusItem` **natif par capteur** (PyObjC, `pyobjc-framework-Cocoa`) —
ou un seul, "Average", en mode Average — affichant `f/2.8` (préfixe repris
— voir plus bas), valeur snappée à l'échelle standard 1/3-stop
(`snap_to_standard_fstop`), tous partageant un seul `NSMenu` (Show/Hide +
Quit) via un petit `NSObject` cible (`_MenuTarget`) qui pont les actions
Objective-C vers de simples callables Python.
`NSStatusItem.button().setFont_(NSFont.boldSystemFontOfSize_(18))` +
`setTitle_(text)` : c'est macOS lui-même qui dessine le texte avec son
moteur de police, pas une image qu'on lui fait avaler.

`update_display()` prend `dict[str, tuple[float | None, bool]]` (fstop,
is_stale) plutôt qu'un simple float : un capteur déconnecté **reste
affiché mais grisé** (`_apply_title` bascule sur
`setAttributedTitle_(NSColor.tertiaryLabelColor())` plutôt que de
retirer l'item) — vérifié par screenshot réel côte à côte : un `f/2.8`
grisé et un `f/2.8` blanc plein, contraste net entre les deux.

**Historique — pourquoi pas `QSystemTrayIcon`** : la première implémentation
rendait le texte dans un `QPixmap`. Après plusieurs rounds de tests réels
(lancer l'app hors sandbox, `screencapture` la vraie menu bar, mesurer au
pixel — jamais à l'œil, ça a trompé plusieurs fois) :
- Texte noir sur transparent (pari sur le mécanisme "template image" de
  Qt/Cocoa) → invisible. Badge opaque avec coins arrondis (donc un peu de
  transparence) → réduit à un sliver illisible. Badge entièrement opaque →
  lisible. Texte blanc sur transparent sans badge → lisible aussi.
- Mais agrandir `FONT_POINT_SIZE` au-delà d'un certain point n'avait
  **plus aucun effet visible** : mesuré au pixel, 28pt et 40pt donnaient le
  même glyphe de ~19px physiques. Qt/Cocoa ajuste le pixmap d'un
  `QSystemTrayIcon` à une case de taille fixe côté système, indépendamment
  de l'image source — grossir le rendu n'ajoutait que de la marge
  invisible.
`NSStatusItem` natif contourne ce plafond entièrement : la taille de
police demandée est la taille qui s'affiche, point.

**Piège NSMenuItem** : `setTarget_()` ne retient PAS sa cible côté
Objective-C (target-action historique, référence faible) — `_MenuTarget`
doit être gardé en vie par `SensorTrayIcons` (`self._target`) pour toute
la durée de vie de l'app, sinon les clics de menu ne feraient plus rien
silencieusement une fois l'objet ramassé par le GC Python.

`core/` n'importe jamais Qt. Le worker UDP tourne sur un `QThread` dédié
(même discipline que `Semaphore/workers/rf_worker.py` : try/except global,
jamais de thread mort silencieux, signal d'erreur explicite à la place) et
ne parle à l'UI que par `Signal`s portant des types simples — jamais de
widget Qt touché depuis ce thread.

## Packaging

Calqué sur `Semaphore/freeze.sh` (setuptools + src layout, version
dynamique depuis `lighthouse.__version__`, build universal2 via deux venvs
python.org, bundle id `com.brixybrice.lighthouse`). Points propres à cette
app :
- macOS demande la permission "Local Network" pour de l'UDP entrant — il
  faudra injecter `NSLocalNetworkUsageDescription` dans l'`Info.plist` au
  même endroit où Sémaphore injecte déjà `NSLocationUsageDescription`.
- `pyobjc-framework-Cocoa` (tray natif, voir "Menu bar" plus haut) : même
  famille de dépendance que `pyobjc-framework-CoreWLAN`/`CoreLocation`
  dans Sémaphore, PyInstaller devrait la détecter automatiquement, mais si
  le tray manque à l'exécution du `.app` packagé, vérifier les
  `hiddenimports` du `.spec` en premier (`AppKit`, `Foundation`, `objc`).

## Conventions

- Code, commentaires et UI en anglais (comme les autres projets), les
  échanges de conception peuvent rester en français.
- `core/` n'importe jamais Qt.
- Tout protocole matériel non documenté se valide d'abord par un script CLI
  jetable dans `scripts/` contre le vrai matériel, avant d'être porté dans
  `core/`.
