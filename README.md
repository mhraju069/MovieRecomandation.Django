# 🎬 Popn Picks — Backend API

A production-ready **Django REST Framework** backend powering the Popn Picks movie discovery and social platform. Built with async support via ASGI/Uvicorn, background tasks via Celery, real-time notifications via Firebase, and full payment processing via Stripe.

---

## 📋 Table of Contents

- [Tech Stack](#-tech-stack)
- [Architecture Overview](#-architecture-overview)
- [Project Structure](#-project-structure)
- [API Endpoints](#-api-endpoints)
- [Environment Variables](#-environment-variables)
- [Local Development Setup](#-local-development-setup)
- [Docker Compose Deployment](#-docker-compose-deployment)
- [Kubernetes (K8s) Deployment](#-kubernetes-k8s-deployment)
  - [Prerequisites](#prerequisites)
  - [Kind Cluster Setup](#kind-cluster-setup)
  - [Ingress Controller Setup](#ingress-controller-setup)
  - [Helm Chart Deployment](#helm-chart-deployment)
  - [Helm Values Reference](#helm-values-reference)
  - [Upgrading & Rollback](#upgrading--rollback)
  - [Production VPS Setup with Nginx & SSL](#production-vps-setup-with-nginx--ssl)
- [Database](#-database)
- [Background Tasks (Celery)](#-background-tasks-celery)
- [Push Notifications (Firebase)](#-push-notifications-firebase)
- [Payments (Stripe)](#-payments-stripe)
- [API Documentation](#-api-documentation)

---

## 🛠 Tech Stack

| Layer              | Technology                                      |
|--------------------|-------------------------------------------------|
| **Framework**      | Django 5.x + Django REST Framework              |
| **ASGI Server**    | Gunicorn + Uvicorn Workers                      |
| **Database**       | PostgreSQL 15 (SQLite for local dev)            |
| **Cache / Broker** | Redis 7                                         |
| **Task Queue**     | Celery (Worker + Beat Scheduler)                |
| **Reverse Proxy**  | Nginx                                           |
| **Auth**           | JWT via `djangorestframework-simplejwt`         |
| **Payments**       | Stripe                                          |
| **Notifications**  | Firebase Admin SDK (FCM)                        |
| **Movie Data**     | TMDB API                                        |
| **Containerized**  | Docker + Docker Compose                         |
| **Orchestration**  | Kubernetes (Kind) + Helm                        |
| **Admin UI**       | Django Unfold                                   |
| **API Docs**       | Swagger UI + ReDoc via `drf-yasg`               |

---

## 🏗 Architecture Overview

```
                          ┌─────────────────────────────────────────┐
                          │               VPS / Cloud               │
                          │                                         │
  User / Client           │   ┌──────────┐     ┌────────────────┐  │
  ──────────────► Port 80/443 ─► System   ├────► Kind Cluster   │  │
                          │   │  Nginx   │     │                │  │
                          │   └──────────┘     │  ┌──────────┐ │  │
                          │                    │  │ Ingress  │ │  │
                          │                    │  │Controller│ │  │
                          │                    │  └────┬─────┘ │  │
                          │                    │       │        │  │
                          │                    │  ┌────▼─────┐ │  │
                          │                    │  │  popn    │ │  │
                          │                    │  │  Service │ │  │
                          │                    │  └────┬─────┘ │  │
                          │                    │       │        │  │
                          │                    │  ┌────▼─────┐ │  │
                          │                    │  │ Django   │ │  │
                          │                    │  │  Pod(s)  │ │  │
                          │                    │  └──────────┘ │  │
                          │                    └────────────────┘  │
                          │                                         │
                          │   ┌──────┐  ┌──────────┐  ┌────────┐  │
                          │   │  DB  │  │  Redis   │  │ Celery │  │
                          │   │(PG15)│  │  (v7)    │  │Workers │  │
                          │   └──────┘  └──────────┘  └────────┘  │
                          └─────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
popn-backend/
├── config/                  # Django project configuration
│   ├── settings.py          # All settings (env-driven)
│   ├── urls.py              # Root URL configuration
│   ├── asgi.py              # ASGI entrypoint
│   └── wsgi.py              # WSGI entrypoint
│
├── authentication/          # Custom user model, auth, JWT
├── tmdb/                    # TMDB movie data integration
├── subscription/            # Subscription plans & management
├── payment/                 # Stripe payment processing
├── others/                  # Watchlist, reviews, social features
├── fcm/                     # Firebase Cloud Messaging (Push Notifications)
│
├── k8s/                     # Kubernetes manifests
│   ├── config.yml           # Kind cluster configuration
│   └── popn/                # Helm chart
│       ├── Chart.yaml       # Chart metadata
│       ├── values.yaml      # Default Helm values
│       └── templates/       # K8s resource templates
│           ├── deployment.yaml
│           ├── service.yaml
│           ├── ingress.yaml
│           ├── hpa.yaml
│           └── ...
│
├── nginx.conf               # Nginx config for Docker Compose
├── Dockerfile               # Application Dockerfile
├── docker-compose.yml       # Full stack local/prod compose
├── requirements.txt         # Python dependencies
└── .env                     # Environment variables (not committed)
```

---

## 🔌 API Endpoints

| Prefix                | App             | Description                        |
|-----------------------|-----------------|------------------------------------|
| `/admin/`             | Django Admin    | Unfold-powered admin panel         |
| `/api-auth/`          | DRF Session     | Session-based auth (for Swagger)   |
| `/auth/api/v1/`       | authentication  | Register, Login, Profile, JWT      |
| `/tmdb/api/v1/`       | tmdb            | Movies, Search, Genres, Trending   |
| `/subscription/api/v1/` | subscription  | Plans, User subscriptions          |
| `/payment/api/v1/`    | payment         | Stripe checkout, Webhooks          |
| `/other/api/v1/`      | others          | Watchlist, Reviews, Ratings, Social|
| `/fcm/api/v1/`        | fcm             | FCM device token registration      |
| `/token/refresh/`     | simplejwt       | Refresh JWT access token           |
| `/token/verify/`      | simplejwt       | Verify JWT token                   |
| `/docs/`              | drf-yasg        | Swagger UI interactive docs        |
| `/redoc/`             | drf-yasg        | ReDoc API documentation            |

---

## 🔐 Environment Variables

Create a `.env` file in the project root. Use `.env.demo` as a reference template.

```env
# Django Core
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=api.popnpicks.com,localhost

# CORS & CSRF
CORS_ALLOW_ORIGINS=https://popnpicks.com,https://www.popnpicks.com
CSRF_TRUSTED_ORIGINS=https://api.popnpicks.com

# Database (PostgreSQL)
USE_PSQL=True
DB_NAME=popn_db
DB_USER=popn_user
DB_PASSWORD=your_db_password
DB_HOST=db
DB_PORT=5432

# Redis
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Email (Gmail SMTP)
EMAIL_HOST_USER=your@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=PopnPicks <your@gmail.com>

# Stripe
STRIPE_PUBLIC_KEY=pk_live_...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# TMDB
TMDB_ACCESS_TOKEN=your-tmdb-bearer-token

# OpenAI (Optional)
OPENAI_API_KEY=sk-...
```

> **Firebase:** Place your `firebase-key.json` file in the project root. This file is **not** stored in version control.

---

## 💻 Local Development Setup

### Prerequisites
- Python 3.12+
- PostgreSQL (or use SQLite by setting `USE_PSQL=False`)
- Redis

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/mhraju069/popn-backend.git
cd popn-backend

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and configure environment variables
cp .env.demo .env
# Edit .env with your values

# 5. Run database migrations
python manage.py migrate

# 6. Create a superuser
python manage.py createsuperuser

# 7. Run the development server
python manage.py runserver

# 8. (Optional) Start Celery worker in a separate terminal
celery -A config worker -l info --pool=solo

# 9. (Optional) Start Celery beat scheduler in a separate terminal
celery -A config beat -l info
```

The API will be available at: **`http://127.0.0.1:8000`**

---

## 🐳 Docker Compose Deployment

This is the recommended approach for production on a standard VPS.

### Services Included

| Service         | Image              | Port (Host→Container)  |
|-----------------|--------------------|------------------------|
| `web`           | Custom (Dockerfile)| Internal (8000)        |
| `nginx`         | nginx:stable       | `8080:80`              |
| `db`            | postgres:15        | `5435:5432`            |
| `redis`         | redis:7            | `6378:6379`            |
| `celery_worker` | Custom (Dockerfile)| —                      |
| `celery_beat`   | Custom (Dockerfile)| —                      |

### Commands

```bash
# Build and start all services in background
docker compose up -d --build

# View logs
docker compose logs -f web
docker compose logs -f celery_worker

# Run migrations inside container
docker compose exec web python manage.py migrate

# Create superuser
docker compose exec web python manage.py createsuperuser

# Collect static files
docker compose exec web python manage.py collectstatic --noinput

# Stop all services
docker compose down

# Stop and remove volumes (WARNING: deletes database data)
docker compose down -v
```

The application will be accessible at: **`http://your-vps-ip:8080`**

> Configure your VPS Nginx to reverse proxy from port 80/443 to port 8080.

---

## ☸️ Kubernetes (K8s) Deployment

The application is packaged as a **Helm chart** located in `k8s/popn/`. The cluster is managed using **Kind (Kubernetes in Docker)** on a self-hosted VPS.

### Prerequisites

Ensure the following tools are installed on your VPS:

```bash
# Docker
docker --version          # v29.x+

# Kind (Kubernetes in Docker)
kind version              # v0.24+

# kubectl
kubectl version --client  # v1.31+

# Helm
helm version              # v3.x+
```

### Kind Cluster Setup

The cluster configuration is stored in `k8s/config.yml`. It creates a 3-node cluster (1 control-plane + 2 workers) with port mappings on the control-plane node.

```bash
cd k8s/

# Create the cluster
kind create cluster --config config.yml

# Verify cluster is running
kubectl cluster-info --context kind-kind
kubectl get nodes
```

**Expected output:**
```
NAME                 STATUS   ROLES           AGE   VERSION
kind-control-plane   Ready    control-plane   ...   v1.31.2
kind-worker          Ready    <none>          ...   v1.31.2
kind-worker2         Ready    <none>          ...   v1.31.2
```

**Port Mappings (defined in `k8s/config.yml`):**

| VPS Host Port | Kind Container Port | Protocol | Usage         |
|---------------|---------------------|----------|---------------|
| `8888`        | `80`                | TCP      | HTTP Traffic  |
| `8443`        | `443`               | TCP      | HTTPS Traffic |

> ⚠️ The `kubeadmConfigPatches` in `config.yml` automatically labels the control-plane node with `ingress-ready=true` so that the Nginx Ingress Controller is scheduled to the correct node.

### Ingress Controller Setup

Install the **Nginx Ingress Controller** using the official Kind-compatible manifest:

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
```

Wait for the controller to be ready (takes ~30-60 seconds):
```bash
kubectl get pods -n ingress-nginx --watch
```

Ensure the controller pod is scheduled on `kind-control-plane`:
```bash
kubectl get pods -n ingress-nginx -o wide
```

If the Ingress Controller pod is on a worker node, patch it to move it to control-plane:
```bash
kubectl patch deployment ingress-nginx-controller -n ingress-nginx \
  -p '{"spec":{"template":{"spec":{"nodeSelector":{"ingress-ready":"true"}}}}}'
```

### Helm Chart Deployment

```bash
# Navigate to k8s directory
cd ~/popn-backend/k8s

# Install the chart for the first time
helm install popn popn/

# Check deployment status
kubectl get all

# View pod logs
kubectl logs -l app.kubernetes.io/name=popn --tail=50

# Describe a pod (for debugging)
kubectl describe pod -l app.kubernetes.io/name=popn
```

**Verify deployment:**
```bash
# Check pods are running
kubectl get pods
# Expected: popn-<hash>   1/1   Running   0   ...

# Check service
kubectl get svc popn
# Expected: popn   ClusterIP   10.x.x.x   <none>   8000/TCP

# Check ingress
kubectl get ingress
# Expected: popn   nginx   k8s.popnpicks.com   ...   80

# Test API via curl (from VPS terminal)
curl -H "Host: k8s.popnpicks.com" http://127.0.0.1:8888/admin/login/
```

### Helm Values Reference

Key configurable values in `k8s/popn/values.yaml`:

```yaml
# Docker image
image:
  repository: mhraju069/popn-backend
  tag: "latest"
  pullPolicy: IfNotPresent

# Kubernetes Service
service:
  type: ClusterIP
  port: 8000        # Service port
  targetPort: 8000  # Container port (must match Gunicorn --bind port)

# Ingress
ingress:
  enabled: true
  className: "nginx"
  annotations:
    nginx.ingress.kubernetes.io/proxy-body-size: "10G"
  hosts:
    - host: k8s.popnpicks.com
      paths:
        - path: /
          pathType: Prefix
  tls: []           # Add TLS config here for HTTPS

# Health Checks
livenessProbe:
  httpGet:
    path: /admin/login/  # Must return 2xx/3xx
    port: http
readinessProbe:
  httpGet:
    path: /admin/login/
    port: http

# Horizontal Pod Autoscaler
autoscaling:
  enabled: true
  minReplicas: 1
  maxReplicas: 5
  targetCPUUtilizationPercentage: 80
  targetMemoryUtilizationPercentage: 80
```

### Upgrading & Rollback

```bash
# After making changes to chart or values, upgrade
helm upgrade popn popn/

# View release history
helm history popn

# Rollback to a previous revision (e.g., revision 2)
helm rollback popn 2

# Uninstall the release
helm uninstall popn

# Install fresh after uninstall
helm install popn popn/
```

> **Important:** Never run `helm install` if a release already exists. Use `helm upgrade` instead. The recommended idempotent approach is:
> ```bash
> helm upgrade --install popn popn/
> ```

### Production VPS Setup with Nginx & SSL

The VPS has a system-level Nginx acting as the main reverse proxy. It forwards traffic to the Kind cluster's exposed port.

**File:** `/etc/nginx/sites-available/api.popnpicks.com`

```nginx
server {
    listen 80;
    server_name api.popnpicks.com;

    # Redirect all HTTP to HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name api.popnpicks.com;

    # SSL certificates managed by Certbot
    ssl_certificate /etc/letsencrypt/live/api.popnpicks.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.popnpicks.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    location / {
        # Forward to Kind cluster Ingress port
        proxy_pass http://127.0.0.1:8888;

        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

**Enable and reload Nginx:**
```bash
sudo ln -s /etc/nginx/sites-available/api.popnpicks.com /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

**Obtain SSL certificate with Certbot:**
```bash
sudo certbot --nginx -d api.popnpicks.com
```

---

## 🗄 Database

The application supports both **PostgreSQL** (production) and **SQLite** (development).

| Setting       | Value                                  |
|---------------|----------------------------------------|
| **Engine**    | PostgreSQL 15 / SQLite 3              |
| **Auth**      | Configured via `.env`                  |
| **Migrations**| `python manage.py migrate`             |

**Switch between databases:**
```env
USE_PSQL=True    # Use PostgreSQL
USE_PSQL=False   # Use SQLite (default for local dev)
```

---

## ⚙️ Background Tasks (Celery)

The application uses **Celery** with **Redis** as the message broker for background task processing.

| Component       | Command                                                |
|-----------------|--------------------------------------------------------|
| **Worker**      | `celery -A config worker -l info --pool=solo`          |
| **Beat Scheduler** | `celery -A config beat -l info`                   |
| **Broker**      | Redis (`redis://redis:6379/0`)                         |
| **Result Backend** | Redis (`redis://redis:6379/0`)                     |

In Docker Compose, both `celery_worker` and `celery_beat` containers start automatically.

---

## 🔔 Push Notifications (Firebase)

Firebase Cloud Messaging (FCM) is used for mobile push notifications.

**Setup:**
1. Download your Firebase service account key from the Firebase Console.
2. Place the file at: `firebase-key.json` in the project root.
3. The file is **auto-detected** by `config/settings.py` at startup.

> ⚠️ **Never commit `firebase-key.json` to version control.** It is listed in `.gitignore`.

**Notification triggers:**
- New follower
- Review like / comment
- Post like / comment

---

## 💳 Payments (Stripe)

Stripe is integrated for subscription-based payment processing.

| Variable                | Description                               |
|-------------------------|-------------------------------------------|
| `STRIPE_PUBLIC_KEY`     | Stripe publishable key (frontend use)     |
| `STRIPE_SECRET_KEY`     | Stripe secret key (backend only)          |
| `STRIPE_WEBHOOK_SECRET` | Webhook signing secret for verification   |

**Webhook endpoint:** `/payment/api/v1/webhook/`

Configure this URL in your Stripe Dashboard → Webhooks section.

---

## 📖 API Documentation

Interactive API documentation is auto-generated by `drf-yasg`.

| URL       | Interface | Description                    |
|-----------|-----------|--------------------------------|
| `/docs/`  | Swagger UI | Full interactive API explorer  |
| `/redoc/` | ReDoc      | Clean readable API reference   |

**Authentication in Swagger:**
1. Obtain a JWT token via `/auth/api/v1/login/`
2. Click **Authorize** in Swagger UI
3. Enter: `Bearer <your_access_token>`

---

## 🚀 Deployment Checklist

- [ ] `.env` file configured with production values
- [ ] `firebase-key.json` placed in project root
- [ ] `DEBUG=False` in production
- [ ] `ALLOWED_HOSTS` set to your domain
- [ ] PostgreSQL database created and migrated
- [ ] Static files collected (`collectstatic`)
- [ ] SSL certificate obtained via Certbot
- [ ] Nginx configured and reloaded
- [ ] Docker image built and pushed to Docker Hub
- [ ] Kind cluster created with `k8s/config.yml`
- [ ] Nginx Ingress Controller installed and on `kind-control-plane` node
- [ ] Helm chart deployed with `helm install popn popn/`
- [ ] Health checks passing (`kubectl get pods`)
- [ ] DNS A record pointing to VPS IP

---

## 🐛 Common Issues & Debugging

### Pod in `CrashLoopBackOff`
```bash
# View logs of the crashing pod
kubectl logs -l app.kubernetes.io/name=popn --tail=100

# Check events for more detail
kubectl describe pod -l app.kubernetes.io/name=popn
```
**Common causes:** Missing env variables, database connection failure, health check path returning 404.

### `Connection reset by peer` on curl test
The Ingress Controller pod is not on the `kind-control-plane` node. Fix:
```bash
kubectl patch deployment ingress-nginx-controller -n ingress-nginx \
  -p '{"spec":{"template":{"spec":{"nodeSelector":{"ingress-ready":"true"}}}}}'
```

### `INSTALLATION FAILED: cannot reuse a name`
The release already exists. Use upgrade instead:
```bash
helm upgrade popn popn/
# or
helm uninstall popn && helm install popn popn/
```

### `Service popn does not have a service port X`
The service port in the cluster does not match what you're forwarding. Check actual port:
```bash
kubectl get svc popn
# Then use the correct port:
kubectl port-forward svc/popn <local-port>:<service-port>
```

---

## 📦 Building & Pushing Docker Image

```bash
# Build the image
docker build -t mhraju069/popn-backend:latest .

# Push to Docker Hub
docker push mhraju069/popn-backend:latest

# After pushing, upgrade the Helm release to pull the new image
kubectl rollout restart deployment/popn
```

---

## 📄 License

This project is proprietary software. All rights reserved © 2026 Popn Picks.
