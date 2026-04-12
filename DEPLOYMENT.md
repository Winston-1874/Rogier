# Rogier — Guide de deploiement

Ce guide permet de deployer Rogier sur un serveur Ubuntu 24.04 LTS avec nginx et systemd. Il est destine a un non-developpeur.

---

## Prerequis

- Un serveur (VPS) sous Ubuntu 24.04 LTS avec acces root ou sudo
- Un nom de domaine pointe vers l'IP du serveur (optionnel mais recommande pour HTTPS)
- Python 3.11 ou 3.12 installe

Verifier la version de Python :

```bash
python3 --version
# Doit afficher Python 3.11.x ou 3.12.x
```

Si Python 3.11+ n'est pas installe :

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip
```

---

## 1. Creer un utilisateur dedie

```bash
sudo useradd -r -m -s /bin/bash rogier
sudo su - rogier
```

## 2. Cloner le depot

```bash
cd /home/rogier
git clone <url-du-depot> app
cd app
```

## 3. Creer l'environnement virtuel

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## 4. Configurer l'application

Copier le fichier d'exemple et le remplir :

```bash
cp .env.example .env
nano .env
```

### Variables obligatoires

- **`ROGIER_SECRET_KEY`** : cle secrete pour signer les cookies de session. Generer avec :

  ```bash
  openssl rand -hex 32
  ```

- **`ROGIER_ADMIN_PASSWORD_HASH`** : hash bcrypt du mot de passe administrateur. Generer avec :

  ```bash
  source .venv/bin/activate
  python scripts/create_admin_password_hash.py
  ```

  Copier la valeur affichee dans `.env`.

- **`ROGIER_DATA_DIR`** : repertoire de stockage des donnees. Recommande :

  ```
  ROGIER_DATA_DIR=/home/rogier/app/data
  ```

  Le repertoire sera cree automatiquement au demarrage.

### Variables optionnelles

- `ROGIER_MAX_UPLOAD_MB` : taille max d'upload en Mo (defaut : 10)
- `ROGIER_CONTACT_URL` : URL de contact affichee dans le User-Agent des requetes Justel
- `ROGIER_CONTACT_EMAIL` : email de contact pour le User-Agent
- `ROGIER_SESSION_MAX_AGE_DAYS` : duree de vie du cookie de session en jours (defaut : 30)
- `ROGIER_LOG_LEVEL` : niveau de log (defaut : INFO)

### Verification

Tester que l'application demarre :

```bash
source .venv/bin/activate
python -m rogier.main
# Doit afficher "Rogier demarre avec ROGIER_DATA_DIR=..."
# Arreter avec Ctrl+C
```

## 5. Creer le service systemd

Revenir en utilisateur root/sudo :

```bash
exit  # quitter l'utilisateur rogier
```

Creer le fichier de service :

```bash
sudo nano /etc/systemd/system/rogier.service
```

Contenu :

```ini
[Unit]
Description=Rogier - Chunking de textes legislatifs belges
After=network.target

[Service]
Type=simple
User=rogier
Group=rogier
WorkingDirectory=/home/rogier/app
EnvironmentFile=/home/rogier/app/.env
ExecStart=/home/rogier/app/.venv/bin/python -m rogier.main
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Activer et demarrer le service :

```bash
sudo systemctl daemon-reload
sudo systemctl enable rogier
sudo systemctl start rogier
```

Verifier le statut :

```bash
sudo systemctl status rogier
# Doit afficher "active (running)"
```

Consulter les logs :

```bash
sudo journalctl -u rogier -f
```

## 6. Configurer nginx en reverse proxy

Installer nginx :

```bash
sudo apt install -y nginx
```

Creer la configuration :

```bash
sudo nano /etc/nginx/sites-available/rogier
```

Contenu (remplacer `votre-domaine.be` par votre domaine, ou utiliser `_` pour repondre sur toutes les requetes) :

```nginx
server {
    listen 80;
    server_name votre-domaine.be;

    client_max_body_size 15M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Activer le site :

```bash
sudo ln -s /etc/nginx/sites-available/rogier /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

Tester dans le navigateur : `http://votre-domaine.be` doit afficher la page de connexion.

## 7. Activer HTTPS avec Let's Encrypt (recommande)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d votre-domaine.be
```

Suivre les instructions. Certbot modifie automatiquement la configuration nginx pour rediriger HTTP vers HTTPS.

Verifier le renouvellement automatique :

```bash
sudo certbot renew --dry-run
```

## 8. Sauvegardes

Les donnees de Rogier sont stockees dans `ROGIER_DATA_DIR` (par defaut `/home/rogier/app/data/`). Ce repertoire contient :

- `documents/` : metadonnees des documents importes (JSON)
- `versions/` : historique des versions (JSON)
- `raw/` : fichiers HTML bruts importes
- `exports/` : manifests d'export (JSON)

Pour sauvegarder, copier ce repertoire entier :

```bash
sudo -u rogier tar czf /home/rogier/backup-$(date +%Y%m%d).tar.gz -C /home/rogier/app data/
```

---

## Depannage

### L'application ne demarre pas

```bash
sudo journalctl -u rogier --no-pager -n 50
```

Erreurs courantes :
- **"variable obligatoire absente"** : une variable d'environnement manque dans `.env`
- **"contient encore la valeur placeholder"** : remplacer la valeur par defaut par une vraie valeur
- **"n'est pas accessible en ecriture"** : verifier les permissions de `ROGIER_DATA_DIR`

### nginx renvoie 502 Bad Gateway

Verifier que le service Rogier tourne :

```bash
sudo systemctl status rogier
```

Verifier que le port 8000 est bien ecoute :

```bash
ss -tlnp | grep 8000
```

### Mise a jour

```bash
sudo su - rogier
cd app
git pull
source .venv/bin/activate
pip install -e .
exit
sudo systemctl restart rogier
```
