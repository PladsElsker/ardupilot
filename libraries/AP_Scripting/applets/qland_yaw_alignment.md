# Alignement du lacet pendant QLAND

Un compagnon tel qu’Autolander publie une mesure MAVLink `LANDING_TARGET`
contenant la position 3D,
l'orientation du marqueur et l'instant de capture. Le script
[`qland_yaw_alignment.lua`](qland_yaw_alignment.lua) calcule l'erreur de cap
sur le FC et commande uniquement une vitesse de lacet. Le véhicule reste en
`QLAND` et conserve sa descente native : le script ne commande ni changement de
mode, ni palier, ni gaz, ni override RC.

Cette suppression des paliers d'alignement peut réduire le temps de vol ; le gain
de batterie n'a pas été mesuré. Si le temps de descente restant est insuffisant,
le véhicule poursuit l'atterrissage sans garantir l'alignement complet.

## Firmware nécessaire

Ce script nécessite le firmware de ce dépôt avec l’API de lacet QLAND.
Les sources `ArduPlane/quadplane.{h,cpp}` et les bindings Lua de ce dépôt
fournissent `quadplane:set_landing_yaw_rate(deg_s)` et
`quadplane:clear_landing_yaw_rate()`. L'override RC a été écarté car il peut
rafraîchir l'activité radio et masquer une perte du récepteur.
La consigne expire dans le firmware après **200 ms** sans rafraîchissement.
Elle est acceptée uniquement en QLAND armé, pendant la descente et la phase finale,
avec AHRS sain, sans failsafe actif et sans entrée pilote de roulis, tangage ou lacet.
En phase finale, le firmware refuse la consigne à un mètre ou moins selon sa hauteur
estimée au-dessus du sol. Le Lua conserve sa propre coupure, à quatre mètres
au-dessus du marqueur par défaut, même si la phase finale commence plus haut.
Chaque changement de mode efface la consigne. Cette API ne modifie pas les
entrées RC ni leurs horodatages. Un firmware standard sans cette API produit
un message explicite au chargement du script et n'effectue aucune correction.

## Installation

Pour un FC physique, compiler ArduPlane depuis ce même dépôt
pour la carte avec le scripting activé, puis installer le firmware et copier
[`qland_yaw_alignment.lua`](qland_yaw_alignment.lua) dans `APM/scripts/` sur
la carte SD. Les essais d’intégration avec Autolander couvrent SITL ; le comportement
sur le matériel et le budget mémoire de sa carte restent à valider.

Activer `SCR_ENABLE=1`, redémarrer le FC et vérifier le message `QYAW: loaded`.
Les paramètres `QYAW_*` deviennent disponibles après chargement du script ;
actualiser la liste des paramètres dans la station sol. Conserver également
`plane_precland.lua` et la configuration `PLND_*` pour le centrage XY. Ce script
de centrage peut toujours ralentir ou interrompre la descente selon ses propres
paramètres. `PLND_YAW_ALIGN` décrit l'orientation du capteur de précision : il
ne définit pas le cap d'atterrissage désiré.

## Réglages sur le FC

Le script réserve la table de paramètres Lua **93** et le préfixe `QYAW_`.
Vérifier l'absence de conflit avec d'autres scripts installés. Le contrôleur est
désactivé par défaut, y compris dans SITL. Après `QYAW: loaded`, l'activer dans
MAVProxy ou la station sol :

```text
param set QYAW_ENABLE 1
```

Cette activation est sauvegardée par le FC. Sur cette révision, les paramètres
créés par Lua ne sont pas initialisés par `--add-param-file`/`--defaults` de
SITL : les régler par MAVLink après le chargement du script.

| Paramètre | Défaut | Rôle |
| --- | --- | --- |
| `QYAW_ENABLE` | 0 | Mettre à 1 pour activer la correction. |
| `QYAW_SYSID` / `QYAW_COMPID` | 255 / 191 | Source MAVLink du compagnon autorisée pour les mesures. |
| `QYAW_MIN_HGT` | 4 m | Hauteur verticale minimale au-dessus du marqueur, déduite de la pose et de l'attitude. Minimum accepté : 1 m. |
| `QYAW_DIST_MAX` | 2 m | Distance horizontale maximale à la cible. |
| `QYAW_MAX_AGE` | 0,4 s | Durée maximale depuis la réception d'une nouvelle capture ; borne aussi l'accumulation de retard de transport. Plage : 0,05–0,5 s. |
| `QYAW_STABLE` | 0,5 s | Acquisition continue avant correction. Plage : 0,1–5 s. |
| `QYAW_TOL` | 3° | Tolérance d'alignement ; reprise au-delà de tolérance + 2°. Plage : 1–20°. |
| `QYAW_RATE_MAX` | 20°/s | Limite de vitesse commandée. Maximum accepté par le script : 45°/s. |
| `QYAW_GAIN` | 1/s | Gain proportionnel appliqué à l'erreur de cap. Plage : ]0, 5]. |
| `QYAW_FORWARD` | 0° | Axe avant désiré dans le plan du marqueur : +X à 0°, +Y à 90°. |

Garder `Q_WVANE_ENABLE=0` pour éviter deux objectifs de cap concurrents. Les
paramètres invalides empêchent la correction. Le script tourne à 20 Hz et
libère le lacet si la cible disparaît, devient invalide, sort de l'enveloppe,
si un failsafe se déclenche ou si le pilote reprend les commandes. Une perte
de mesures n'interrompt pas l'atterrissage. Après une exception Lua, la consigne
est libérée ; l'expiration native couvre aussi un arrêt complet du moteur Lua.

## Mesure MAVLink

La publication utilise les extensions de
[`LANDING_TARGET` MAVLink 2](https://mavlink.io/en/messages/common.html#LANDING_TARGET) :

| Champ | Convention |
| --- | --- |
| `x`, `y`, `z` | Position du marqueur en mètres, repère `MAV_FRAME_BODY_FRD` : avant, droite, bas. |
| `q` | Quaternion unitaire `(w,x,y,z)` transformant les axes du marqueur vers BODY_FRD. |
| `time_usec` | Capture sur l'horloge monotone du compagnon, en microsecondes. Une capture n'est publiée qu'une fois. |
| `target_num` | 0 : une cible physique configurée, même lorsque le niveau FArUco visible change. |
| `type`, `position_valid` | `VISION_FIDUCIAL`, 1. |

Position et quaternion proviennent du même `body_from_marker`, qui inclut le
montage de caméra. Sans orientation connue, le quaternion est nul : le FC peut
utiliser la position pour le centrage, mais le script refuse de corriger le lacet.
Autolander cesse de publier les captures âgées de 400 ms ou plus.

Le Lua corrige le roulis et le tangage avant de projeter l'axe du marqueur dans
le plan horizontal. Une erreur positive demande une rotation horaire vue du
dessus. Une projection presque verticale est rejetée. La direction choisie
dépend donc de la convention d'axes du détecteur et de `QYAW_FORWARD` ; elle doit
être vérifiée avec le marqueur et le montage réellement utilisés.

Le timestamp 64 bits est conservé en quatre mots de 16 bits, compatibles avec
le Lua 32 bits d'ArduPilot. Les doublons et retours en arrière ne rafraîchissent
pas la cible. La durée locale utilise les compteurs `uint32_t` du FC, y compris
leur rebouclage. Les horloges n'ont pas besoin d'être synchronisées : le script
mesure l'âge à réception et les variations de retard de transport. Cela ne
mesure pas la latence absolue du premier paquet ni ne compense le mouvement
pendant l'exposition/le transport. Le lien doit conserver une faible latence.
Si l'horloge du compagnon repart en arrière après redémarrage, l'alignement
reste suspendu jusqu'à la prochaine sortie de QLAND/désactivation.

## Vérification

Depuis la racine de ce dépôt, avec Lua 5.4 :

```bash
lua5.4 libraries/AP_Scripting/tests/qland_yaw_alignment_test.lua libraries/AP_Scripting/applets/qland_yaw_alignment.lua
python3 -m pytest -q libraries/AP_Scripting/tests/test_qland_lua.py
```

Le test Lua simule les bindings du FC et vérifie les commandes de lacet,
les paramètres, la fraîcheur des mesures et la libération de la consigne.
Les tests d’intégration SITL utilisant les mesures publiées par Autolander
restent dans son dépôt : `tests/integration/test_qland_yaw_sitl.py`.
