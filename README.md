# timerMQTT

Application Windows affichant un timer reçu par MQTT en surimpression, avec configuration et systray.
Générer avec Copilot (GPT5 Preview)

## Dépendances
- PyQt5
- paho-mqtt

## Fonctionnalités
- Fenêtre transparente always-on-top
- Affichage du timer (décrémenté localement)
- Synchronisation via MQTT
- Configuration serveur MQTT (URL, utilisateur, mot de passe)
- Icône systray
- Logique de validité du timer
- Personnalisation taille et couleur de police
- Alarme sonore quand le timer atteint 00:00:00 (répétée jusqu'au clic)

## Installation
Installez les dépendances avec :
```
pip install -r requirements.txt
```

## Lancement
```
python main.py
```

## Paramètres
Depuis l'icône systray > Paramètres…
- Serveur: mqtt://hote:1883 (port par défaut 1883)
- Topic: sujet MQTT du timer
- Utilisateur/Mot de passe: optionnel
- Taille de police et couleur (#RRGGBB)

## Packaging Windows

1) Construire l'exécutable (PyInstaller):
```
pyinstaller --noconfirm --clean timerMQTT.spec
```
Le binaire se trouve dans `dist/timerMQTT/timerMQTT.exe`.

2) Créer un installateur (Inno Setup):
- Ouvrez `installer.iss` dans Inno Setup Compiler, puis Build.
L'installateur sera généré dans `dist/`.

Notes:
- L’alarme sonore utilise `winsound` (Windows). Elle se répète tant que vous ne cliquez pas sur le timer.
- La position de la fenêtre et les paramètres sont sauvegardés via QSettings.
