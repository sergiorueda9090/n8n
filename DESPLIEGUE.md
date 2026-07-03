# Despliegue de Aurora Financiera en EC2 (Apache + Gunicorn + HTTPS)

Guía paso a paso para desplegar la app **Django** en una instancia EC2 con
Apache2 como *reverse proxy* hacia Gunicorn, estáticos servidos desde
`/var/www/html/static`, y HTTPS con Let's Encrypt (Certbot) para
`sruedadev.com`.

Arquitectura final:

```
Navegador  ──HTTPS──▶  Apache (:443)  ──proxy──▶  Gunicorn (127.0.0.1:8001)  ──▶  Django
                          │
                          └── /static/  ──▶  /var/www/html/static  (Apache directo)
```

- Código Django: `/var/www/aurora`
- Estáticos públicos: `/var/www/html/static`

---

## ⚠️ 0. Seguridad ANTES de empezar

Estos archivos **NUNCA** deben subir al servidor ni a git (ya están en `.gitignore`):

- `.env`  → contiene `SECRET_KEY` y credenciales.
- `n8n-bedrock-ocr_accessKeys.csv` → **contiene claves AWS**. Si alguna vez se
  expuso, **rótala/desactívala en la consola de AWS IAM** por precaución.

En producción se crea un `.env` nuevo directamente en la EC2 (paso 5).
`SECRET_KEY` de producción debe ser **distinta** a la local.

---

## 1. Subir el código a GitHub (desde tu máquina local)

El repo ya está inicializado y con el commit inicial. Créalo en GitHub y súbelo
(ya tienes `gh` autenticado como `srueda123`):

```bash
cd /home/srueda/Documentos/linux/aurora-financiera
gh repo create aurora-financiera --private --source=. --remote=origin --push
```

Esto crea el repo **privado**, añade el remoto `origin` y sube la rama `main`.
Verifica: `git remote -v`

> El `.gitignore` ya protege `.env` y el CSV de claves AWS: **no se suben**.

---

## 1-bis. Credenciales en la EC2 para clonar (Deploy Key SSH — recomendado)

Como el repo es **privado**, la EC2 necesita credenciales para clonarlo. La
forma más segura es una **Deploy Key**: un par de llaves SSH exclusivo de este
repo y de **solo lectura** (si se filtra, no compromete tu cuenta ni otros repos).

**En la EC2**, genera la llave:

```bash
ssh-keygen -t ed25519 -C "ec2-aurora-deploy" -f ~/.ssh/aurora_deploy -N ""
cat ~/.ssh/aurora_deploy.pub      # copia TODO lo que imprime
```

**En GitHub** (navegador): repo `aurora-financiera` → **Settings** →
**Deploy keys** → **Add deploy key** → pega la clave pública, título
`ec2-aurora`, **NO** marques "Allow write access" → **Add key**.

**En la EC2**, indica a git que use esa llave para GitHub:

```bash
cat >> ~/.ssh/config <<'EOF'
Host github-aurora
    HostName github.com
    User git
    IdentityFile ~/.ssh/aurora_deploy
    IdentitiesOnly yes
EOF
chmod 600 ~/.ssh/config
```

Prueba y clona:

```bash
ssh -T git@github-aurora            # debe saludarte con tu usuario
git clone git@github-aurora:srueda123/aurora-financiera.git /tmp/aurora-src
```

> **Alternativa (PAT por HTTPS):** en vez de la Deploy Key, en GitHub crea un
> *Fine-grained token* de solo lectura (Settings → Developer settings →
> Personal access tokens) con acceso a este repo, y clona con:
> `git clone https://USUARIO:TOKEN@github.com/srueda123/aurora-financiera.git`
> La Deploy Key es preferible en servidores.

---

## 1-ter. Entrar a la instancia

```bash
ssh -i ~/.ssh/TU_LLAVE.pem ubuntu@IP_EC2
```
(Ubuntu AMI usa el usuario `ubuntu`; Amazon Linux usa `ec2-user`. Usa la
Elastic IP si tienes.)

---

## 2. Instalar dependencias del sistema (en la EC2)

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip apache2 \
                    libapache2-mod-proxy-html

# Módulos de Apache necesarios para el proxy y el header HTTPS:
sudo a2enmod proxy proxy_http headers ssl rewrite
sudo systemctl restart apache2
```

---

## 3. Clonar el código en `/var/www/aurora`

Clonamos directamente ahí (dueño `ubuntu`) para que luego `git pull` actualice
sin fricción:

```bash
sudo mkdir -p /var/www/aurora /var/www/html/static
sudo chown ubuntu:ubuntu /var/www/aurora /var/www/html/static
git clone git@github-aurora:srueda123/aurora-financiera.git /var/www/aurora
```

---

## 4. Entorno virtual + dependencias de Python

```bash
cd /var/www/aurora
python3 -m venv env
./env/bin/pip install --upgrade pip
./env/bin/pip install -r requirements.txt
```

> Si usarás **SQLite** (opción simple) puedes quitar `psycopg2-binary` del
> `requirements.txt`. Si usarás **PostgreSQL/Supabase**, déjalo.

---

## 5. Crear el `.env` de producción

```bash
cp /var/www/aurora/.env.produccion.example /var/www/aurora/.env
nano /var/www/aurora/.env
```

Rellena como mínimo:

- `SECRET_KEY` → genérala:
  ```bash
  ./env/bin/python -c "import secrets;print(secrets.token_urlsafe(50))"
  ```
- `DEBUG=False`
- `ALLOWED_HOSTS=sruedadev.com,www.sruedadev.com,127.0.0.1`
- `CSRF_TRUSTED_ORIGINS=https://sruedadev.com,https://www.sruedadev.com`
- `STATIC_ROOT=/var/www/html/static`
- Base de datos (SQLite o Postgres, ver la plantilla).
- `N8N_WEBHOOK_URL` → usa la URL de **producción** (`/webhook/aura-web`, no la de test).

---

## 6. Migraciones + recopilar estáticos

```bash
cd /var/www/aurora
./env/bin/python manage.py migrate
./env/bin/python manage.py collectstatic --noinput   # -> /var/www/html/static
```

(Opcional) crea un superusuario para `/admin/`:

```bash
./env/bin/python manage.py createsuperuser
```

---

## 7. Permisos

El código lo maneja `ubuntu` (dueño del clon y de la Deploy Key) y Gunicorn
corre como `ubuntu`. Apache solo necesita **leer** los estáticos:

```bash
chmod 600 /var/www/aurora/.env               # solo tu usuario lo lee
chmod -R a+rX /var/www/html/static           # Apache (www-data) puede leerlos
```

---

## 8. Servicio Gunicorn (systemd)

```bash
sudo cp /var/www/aurora/deploy/gunicorn.service \
        /etc/systemd/system/gunicorn-aurora.service

sudo systemctl daemon-reload
sudo systemctl enable --now gunicorn-aurora
sudo systemctl status gunicorn-aurora     # debe verse "active (running)"
```

Prueba local de que Django responde:

```bash
curl -I http://127.0.0.1:8001/            # debe devolver HTTP 200/302
```

---

## 9. Configurar Apache (VirtualHost)

```bash
sudo cp /var/www/aurora/deploy/aurora-apache.conf \
        /etc/apache2/sites-available/aurora.conf

sudo a2ensite aurora.conf
sudo a2dissite 000-default.conf      # desactiva el sitio por defecto
sudo apache2ctl configtest           # debe decir "Syntax OK"
sudo systemctl reload apache2
```

Comprueba en el navegador `http://sruedadev.com` — ya debería cargar la
landing con estilos e imágenes.

---

## 10. HTTPS con Certbot (Let's Encrypt)

```bash
sudo apt install -y certbot python3-certbot-apache
sudo certbot --apache -d sruedadev.com -d www.sruedadev.com
```

Elige **redirección automática HTTP → HTTPS** cuando lo pregunte.
Certbot crea el bloque `<VirtualHost *:443>` con el certificado.

### 10.1 Ajuste importante tras Certbot

Edita el vhost SSL que generó Certbot y asegúrate de que el header enviado a
Django sea **https** (para que valide CSRF del chatbot y genere URLs seguras):

```bash
sudo nano /etc/apache2/sites-available/aurora-le-ssl.conf
```

Dentro del `<VirtualHost *:443>`, deja/añade:

```apache
RequestHeader set X-Forwarded-Proto "https"
```

Luego:

```bash
sudo apache2ctl configtest && sudo systemctl reload apache2
```

Renovación automática (ya viene por defecto). Verifícala:

```bash
sudo certbot renew --dry-run
```

---

## 11. Verificación final

- `https://sruedadev.com` carga con candado ✅
- Imágenes y CSS cargan (vienen de `/static/`) ✅
- El chatbot **Aurorita** responde (prueba escribir un mensaje) — esto valida
  que `POST /api/chat/` → n8n funciona con CSRF/HTTPS ✅
- `https://sruedadev.com/admin/` abre el admin ✅

---

## 12. Actualizaciones futuras (redeploy con git)

En tu máquina, haz commit y push de los cambios:

```bash
git add -A && git commit -m "..." && git push
```

En la EC2, baja los cambios y recarga:

```bash
cd /var/www/aurora
sudo -u www-data git pull
sudo ./env/bin/python manage.py migrate
sudo ./env/bin/python manage.py collectstatic --noinput
sudo systemctl restart gunicorn-aurora
```

> `sudo -u www-data git pull` mantiene los permisos correctos. Como el paso 3
> clonó el repo en `/var/www/aurora`, esa carpeta ya es un repo git conectado a
> tu `origin`.

---

## 13. Solución de problemas

| Síntoma | Dónde mirar / Causa probable |
|---|---|
| Error 500 | `sudo journalctl -u gunicorn-aurora -n 50` — falta una var en `.env` o dependencia |
| CSS/imágenes rotas | ¿Corriste `collectstatic`? ¿`STATIC_ROOT=/var/www/html/static`? ¿permisos www-data? |
| 502 Bad Gateway | Gunicorn caído: `sudo systemctl status gunicorn-aurora` |
| Chatbot da 403 | Falta `CSRF_TRUSTED_ORIGINS` o el header `X-Forwarded-Proto https` en el vhost 443 |
| `DisallowedHost` | Añade el dominio a `ALLOWED_HOSTS` en `.env` |
| Chatbot no conecta | `N8N_WEBHOOK_URL` apunta a `/webhook-test/` (solo dev). Usa `/webhook/aura-web` |
| Logs de Apache | `sudo tail -f /var/log/apache2/aurora_error.log` |

---

### Resumen de puertos / rutas

| Elemento | Valor |
|---|---|
| Código Django | `/var/www/aurora` |
| Virtualenv | `/var/www/aurora/env` |
| Estáticos | `/var/www/html/static` |
| Gunicorn | `127.0.0.1:8001` (interno) |
| Apache | `:80` → redirige a `:443` |
| Servicio | `gunicorn-aurora.service` |
