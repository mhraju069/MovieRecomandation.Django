# 🚀 Django Kubernetes Production Guide
### *A Production-Ready Blueprint for Helm, Kind, Ingress Nginx, PostgreSQL, Redis, Celery & HPA*

> **How to use this guide:**
> Replace all `<placeholders>` with your actual project values before applying any configuration.
> Key placeholders: `<project-name>`, `<domain>`, `<docker-image>`, `<db-host>`

---

## 📋 Table of Contents
1. [Prerequisites & Tool Installation](#1-prerequisites--tool-installation)
2. [Kubernetes Cluster Setup (Kind)](#2-kubernetes-cluster-setup-kind)
3. [Ingress Nginx Setup](#3-ingress-nginx-setup)
4. [Helm Chart Structure](#4-helm-chart-structure)
5. [Secret Template](#5-secret-template)
6. [Django Deployment](#6-django-deployment)
7. [PostgreSQL Deployment](#7-postgresql-deployment)
8. [Redis Deployment](#8-redis-deployment)
9. [Celery Worker Deployment](#9-celery-worker-deployment)
10. [values.yaml Configuration](#10-valuesyaml-configuration)
11. [Static Files — WhiteNoise](#11-static-files--whitenoise)
12. [External Secret Files (Firebase, GCP, etc.)](#12-external-secret-files-firebase-gcp-etc)
13. [VPS Nginx Config](#13-vps-nginx-config)
14. [Cluster Operations & Management](#14-cluster-operations--management)
15. [HPA Setup & Verification](#15-hpa-setup--verification-metrics-server)

---

## 🛠️ 1. Prerequisites & Tool Installation

### Docker
```bash
sudo apt update
sudo apt install -y docker.io
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
newgrp docker
docker --version
```

### kubectl
```bash
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/
kubectl version --client
```

### Helm
```bash
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
chmod 700 get_helm.sh
./get_helm.sh && rm get_helm.sh
helm version
```

### Kind
```bash
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.25.0/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind
kind version
```

---

## ☸️ 2. Kubernetes Cluster Setup (Kind)

### `config.yaml`

```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    image: kindest/node:v1.31.2
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
    extraPortMappings:
      - containerPort: 80
        hostPort: 80        # Change it if there is port 80 conflict
        protocol: TCP
      - containerPort: 443
        hostPort: 443        # Change it if there is port 443 conflict
        protocol: TCP
  - role: worker
    image: kindest/node:v1.31.2
  - role: worker
    image: kindest/node:v1.31.2
```

### Create / Delete Cluster
```bash
# Create
kind create cluster --name <project-name> --config config.yaml

# Delete
kind delete cluster --name <project-name>

# List clusters
kind get clusters
```

---

## 🌐 3. Ingress Nginx Setup

Install via Helm so it automatically runs on the control-plane node — no manual patching needed.

### `ingress-values.yaml`
```yaml
controller:
  nodeSelector:
    ingress-ready: "true"
  tolerations:
    - key: "node-role.kubernetes.io/control-plane"
      operator: "Exists"
      effect: "NoSchedule"
  resources:
    requests:
      cpu: 50m
      memory: 50Mi
```

### Install
```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update

helm install ingress-nginx ingress-nginx/ingress-nginx \
  -n ingress-nginx \
  --create-namespace \
  -f ingress-values.yaml

# Wait until ready
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s
```

### Verify — should be on control-plane
```bash
kubectl get pods -n ingress-nginx -o wide
# NODE column should show: <project-name>-control-plane
```

> ⚠️ **If ingress controller lands on a worker node instead**, run this patch:
> ```bash
> kubectl patch deployment ingress-nginx-controller -n ingress-nginx \
>   --type=json \
>   -p='[
>     {"op":"add","path":"/spec/template/spec/nodeSelector","value":{"ingress-ready":"true"}},
>     {"op":"add","path":"/spec/template/spec/tolerations","value":[{"key":"node-role.kubernetes.io/control-plane","operator":"Exists","effect":"NoSchedule"}]},
>     {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/cpu","value":"50m"},
>     {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/memory","value":"50Mi"}
>   ]'
> ```

---

## 📦 4. Helm Chart Structure

```bash
helm create <project-name>

# Clear default templates
rm -rf <project-name>/templates/*
```

Final structure:
```
<project-name>/
├── Chart.yaml
├── values.yaml
└── templates/
    ├── _helpers.tpl          ← auto-generated, keep it
    ├── secret.yaml           ← all ENV variables
    ├── deployment.yaml       ← Django app
    ├── service.yaml          ← Django service
    ├── ingress.yaml          ← Ingress rule
    ├── hpa.yaml              ← Auto scaling
    ├── serviceaccount.yaml
    ├── db-pvc.yaml           ← Postgres storage
    ├── db-deployment.yaml    ← Postgres StatefulSet
    ├── db-service.yaml       ← Postgres service
    ├── redis.yaml            ← Redis deployment + service
    └── celery.yaml           ← Celery worker
```

---

## 🔐 5. Secret Template

All ENV variables from `values.yaml` are automatically base64-encoded and injected as a Kubernetes Secret.

### `templates/secret.yaml`
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: {{ include "<project-name>.fullname" . }}-env
  labels:
    {{- include "<project-name>.labels" . | nindent 4 }}
type: Opaque
data:
  {{- range $key, $value := .Values.env }}
  {{ $key }}: {{ $value | toString | b64enc | quote }}
  {{- end }}
```

---

## 🐍 6. Django Deployment

### `templates/deployment.yaml`
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "<project-name>.fullname" . }}
  labels:
    {{- include "<project-name>.labels" . | nindent 4 }}
spec:
  {{- if not .Values.autoscaling.enabled }}
  replicas: {{ .Values.replicaCount }}
  {{- end }}
  selector:
    matchLabels:
      {{- include "<project-name>.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "<project-name>.selectorLabels" . | nindent 8 }}
    spec:
      serviceAccountName: {{ include "<project-name>.serviceAccountName" . }}
      containers:
        - name: {{ .Chart.Name }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - name: http
              containerPort: {{ .Values.service.targetPort }}
              protocol: TCP
          envFrom:
            - secretRef:
                name: {{ include "<project-name>.fullname" . }}-env
          {{- with .Values.livenessProbe }}
          livenessProbe:
            {{- toYaml . | nindent 12 }}
          {{- end }}
          {{- with .Values.readinessProbe }}
          readinessProbe:
            {{- toYaml . | nindent 12 }}
          {{- end }}
          {{- with .Values.resources }}
          resources:
            {{- toYaml . | nindent 12 }}
          {{- end }}
          # Optional: mount external secret files (e.g. firebase-key.json)
          # volumeMounts:
          #   - name: firebase-key
          #     mountPath: /app/firebase-key.json
          #     subPath: firebase-key.json
          #     readOnly: true
      # volumes:
      #   - name: firebase-key
      #     secret:
      #       secretName: firebase-key
```

### `templates/service.yaml`
```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ include "<project-name>.fullname" . }}
  labels:
    {{- include "<project-name>.labels" . | nindent 4 }}
spec:
  type: {{ .Values.service.type }}
  ports:
    - port: {{ .Values.service.port }}
      targetPort: {{ .Values.service.targetPort }}
      protocol: TCP
      name: http
  selector:
    {{- include "<project-name>.selectorLabels" . | nindent 4 }}
```

### `templates/ingress.yaml`
```yaml
{{- if .Values.ingress.enabled }}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ include "<project-name>.fullname" . }}
  labels:
    {{- include "<project-name>.labels" . | nindent 4 }}
  {{- with .Values.ingress.annotations }}
  annotations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
spec:
  ingressClassName: {{ .Values.ingress.className }}
  rules:
    {{- range .Values.ingress.hosts }}
    - host: {{ .host }}
      http:
        paths:
          {{- range .paths }}
          - path: {{ .path }}
            pathType: {{ .pathType }}
            backend:
              service:
                name: {{ include "<project-name>.fullname" $ }}
                port:
                  number: {{ $.Values.service.port }}
          {{- end }}
    {{- end }}
{{- end }}
```

### `templates/hpa.yaml`
```yaml
{{- if .Values.autoscaling.enabled }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ include "<project-name>.fullname" . }}
  labels:
    {{- include "<project-name>.labels" . | nindent 4 }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{ include "<project-name>.fullname" . }}
  minReplicas: {{ .Values.autoscaling.minReplicas }}
  maxReplicas: {{ .Values.autoscaling.maxReplicas }}
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: {{ .Values.autoscaling.targetCPUUtilizationPercentage }}
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: {{ .Values.autoscaling.targetMemoryUtilizationPercentage }}
{{- end }}
```

---

## 🗄️ 7. PostgreSQL Deployment

Using StatefulSet instead of Deployment for data safety.

### `templates/db-pvc.yaml`
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {{ include "<project-name>.fullname" . }}-db-pvc
  labels:
    {{- include "<project-name>.labels" . | nindent 4 }}
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: {{ .Values.postgres.storage }}
```

### `templates/db-deployment.yaml`
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: {{ include "<project-name>.fullname" . }}-db
  labels:
    {{- include "<project-name>.labels" . | nindent 4 }}
spec:
  serviceName: {{ .Values.env.DB_HOST }}
  replicas: 1
  selector:
    matchLabels:
      app: {{ include "<project-name>.name" . }}-db
  template:
    metadata:
      labels:
        app: {{ include "<project-name>.name" . }}-db
    spec:
      containers:
        - name: postgres
          image: postgres:16
          ports:
            - containerPort: 5432
          env:
            - name: POSTGRES_DB
              valueFrom:
                secretKeyRef:
                  name: {{ include "<project-name>.fullname" . }}-env
                  key: DB_NAME
            - name: POSTGRES_USER
              valueFrom:
                secretKeyRef:
                  name: {{ include "<project-name>.fullname" . }}-env
                  key: DB_USER
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: {{ include "<project-name>.fullname" . }}-env
                  key: DB_PASSWORD
          volumeMounts:
            - name: db-data
              mountPath: /var/lib/postgresql/data
              subPath: pgdata
          readinessProbe:
            exec:
              command: ["pg_isready", "-U", "postgres"]
            initialDelaySeconds: 5
            periodSeconds: 5
      volumes:
        - name: db-data
          persistentVolumeClaim:
            claimName: {{ include "<project-name>.fullname" . }}-db-pvc
```

### `templates/db-service.yaml`

> The service name matches `DB_HOST` in `values.yaml` so Django can reach Postgres by hostname.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ .Values.env.DB_HOST }}
  labels:
    {{- include "<project-name>.labels" . | nindent 4 }}
spec:
  clusterIP: None
  ports:
    - port: 5432
      targetPort: 5432
      name: postgres
  selector:
    app: {{ include "<project-name>.name" . }}-db
```

---

## 🟥 8. Redis Deployment

### `templates/redis.yaml`
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "<project-name>.fullname" . }}-redis
  labels:
    {{- include "<project-name>.labels" . | nindent 4 }}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: {{ include "<project-name>.name" . }}-redis
  template:
    metadata:
      labels:
        app: {{ include "<project-name>.name" . }}-redis
    spec:
      containers:
        - name: redis
          image: redis:7-alpine
          ports:
            - containerPort: 6379
---
apiVersion: v1
kind: Service
metadata:
  name: {{ .Values.redis.host }}
  labels:
    {{- include "<project-name>.labels" . | nindent 4 }}
spec:
  selector:
    app: {{ include "<project-name>.name" . }}-redis
  ports:
    - port: 6379
      targetPort: 6379
```

---

## 🌿 9. Celery Worker Deployment

### `templates/celery.yaml`
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "<project-name>.fullname" . }}-celery
  labels:
    {{- include "<project-name>.labels" . | nindent 4 }}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: {{ include "<project-name>.name" . }}-celery
  template:
    metadata:
      labels:
        app: {{ include "<project-name>.name" . }}-celery
    spec:
      containers:
        - name: celery
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          command: ["celery", "-A", "<django-app-name>", "worker", "--loglevel=info"]
          envFrom:
            - secretRef:
                name: {{ include "<project-name>.fullname" . }}-env
          # Optional: mount external secret files
          # volumeMounts:
          #   - name: firebase-key
          #     mountPath: /app/firebase-key.json
          #     subPath: firebase-key.json
          #     readOnly: true
      # volumes:
      #   - name: firebase-key
      #     secret:
      #       secretName: firebase-key
```

---

## ⚙️ 10. `values.yaml` Configuration

> ⚠️ **Never commit real secrets to git.**
> Add `<project-name>/values.yaml` to `.gitignore`.

```yaml
replicaCount: 1

image:
  repository: <docker-username>/<image-name>
  pullPolicy: Always
  tag: "latest"

service:
  type: ClusterIP
  port: 8000
  targetPort: 8000

ingress:
  enabled: true
  className: "nginx"
  annotations:
    nginx.ingress.kubernetes.io/proxy-body-size: "10G"
  hosts:
    - host: <domain>
      paths:
        - path: /
          pathType: Prefix
  tls: []

resources:
  limits:
    cpu: 1000m
    memory: 512Mi
  requests:
    cpu: 200m
    memory: 256Mi

livenessProbe:
  httpGet:
    path: /admin/login/
    port: http

readinessProbe:
  httpGet:
    path: /admin/login/
    port: http

autoscaling:
  enabled: true
  minReplicas: 1
  maxReplicas: 5
  targetCPUUtilizationPercentage: 80
  targetMemoryUtilizationPercentage: 80

# Postgres config
postgres:
  storage: 5Gi

# Redis host — must match the Service name in redis.yaml
redis:
  host: <project-name>-redis

# All Django ENV variables — automatically become a K8s Secret
env:
  # Django Core
  SECRET_KEY: "your-django-secret-key"
  DEBUG: "False"
  ALLOWED_HOSTS: "<domain>,localhost,127.0.0.1"
  CORS_ALLOW_ORIGINS: "https://<domain>,http://localhost:3000"
  CSRF_TRUSTED_ORIGINS: "https://<domain>,http://localhost:3000"

  # Postgres — DB_HOST must match db-service.yaml Service name
  USE_PSQL: "True"
  DB_NAME: "<db-name>"
  DB_USER: "<db-user>"
  DB_PASSWORD: "your-db-password"
  DB_HOST: "<project-name>-db"
  DB_PORT: "5432"

  # Redis + Celery
  CELERY_BROKER_URL: "redis://<project-name>-redis:6379/0"
  CELERY_RESULT_BACKEND: "redis://<project-name>-redis:6379/0"

  # Email
  EMAIL_HOST_USER: "your-email@gmail.com"
  EMAIL_HOST_PASSWORD: "your-app-password"
  DEFAULT_FROM_EMAIL: "your-email@gmail.com"

  # Add any other ENV variables your project needs below
  # STRIPE_PUBLIC_KEY: ""
  # STRIPE_SECRET_KEY: ""
  # OPENAI_API_KEY: ""
```

---

## 🎨 11. Static Files — WhiteNoise

WhiteNoise lets Django serve its own static files — no separate nginx or volume needed inside K8s.

### Install
```bash
pip install whitenoise
echo "whitenoise" >> requirements.txt
```

### `settings.py`
```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Add as 2nd middleware
    ...
]

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
```

Your `Dockerfile` already runs `collectstatic` — WhiteNoise will serve those files automatically.

---

## 🔑 12. External Secret Files (Firebase, GCP, etc.)

For JSON key files that cannot go in environment variables:

```bash
# Create secret from file
kubectl create secret generic firebase-key \
  --from-file=firebase-key.json=./firebase-key.json

# Create secret from any file
kubectl create secret generic <secret-name> \
  --from-file=<filename>=./<filename>
```

Then uncomment the `volumeMounts` and `volumes` sections in `deployment.yaml` and `celery.yaml` (Section 6 and 9).

### Update on key rotation
```bash
kubectl create secret generic firebase-key \
  --from-file=firebase-key.json=./firebase-key.json \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl rollout restart deployment/<project-name>
```

---

## 🌍 13. VPS Nginx Config

Routes public traffic from VPS nginx into the kind cluster.

### `/etc/nginx/sites-available/<domain>`
```nginx
server {
    listen 80;
    server_name <domain>;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name <domain>;

    ssl_certificate /etc/letsencrypt/live/<domain>/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/<domain>/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8888;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
# Get SSL certificate
sudo certbot --nginx -d <domain>

# Enable site
sudo ln -s /etc/nginx/sites-available/<domain> /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## 🚀 14. Cluster Operations & Management

### Full Setup from Scratch
```bash
# 1. Create cluster
kind create cluster --name <project-name> --config config.yaml

# 2. Install ingress nginx
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
helm install ingress-nginx ingress-nginx/ingress-nginx \
  -n ingress-nginx --create-namespace -f ingress-values.yaml

kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s

# 3. Mount any external key files (optional)
kubectl create secret generic firebase-key \
  --from-file=firebase-key.json=./firebase-key.json

# 4. Deploy the app
helm install <project-name> ./<project-name>

# 5. Run migrations
kubectl exec -it deployment/<project-name> -- python manage.py migrate
```

### Day-to-Day Commands
```bash
# Deploy new image
helm upgrade <project-name> ./<project-name>

# Restart pods to pick up new ENV or secrets
kubectl rollout restart deployment/<project-name>
kubectl rollout restart deployment/<project-name>-celery

# Run Django management commands
kubectl exec -it deployment/<project-name> -- python manage.py migrate
kubectl exec -it deployment/<project-name> -- python manage.py createsuperuser
kubectl exec -it deployment/<project-name> -- python manage.py shell
kubectl exec -it deployment/<project-name> -- bash

# View logs
kubectl logs -f deployment/<project-name>
kubectl logs -f deployment/<project-name>-celery

# Check status
kubectl get pods
kubectl get ingress
kubectl get hpa
kubectl get pvc
```

### Update ENV Variables
```bash
# Edit values.yaml, then:
helm upgrade <project-name> ./<project-name>
kubectl rollout restart deployment/<project-name>
kubectl rollout restart deployment/<project-name>-celery
```

### Test Ingress Locally on VPS
```bash
curl -H "Host: <domain>" http://127.0.0.1:8888/admin/login/
```

---

## 📈 15. HPA Setup & Verification (Metrics Server)

HPA requires Metrics Server to read CPU and memory usage.

### Install Metrics Server
```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

### Patch for Kind (bypasses self-signed TLS)
```bash
kubectl patch deployment metrics-server -n kube-system \
  --type='json' \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
```

### Verify
```bash
# Metrics server pod should be 1/1 Ready
kubectl get pods -n kube-system -l k8s-app=metrics-server

# HPA targets should show actual percentages, not <unknown>
kubectl get hpa

# Watch live scaling
watch -n 1 "kubectl get hpa && echo '' && kubectl get pods"
```

### Load Test Script
```python
# load_test.py — run from your local machine
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor

URL = "https://<domain>/admin"
DURATION = 60       # seconds
CONCURRENCY = 20    # concurrent threads

def send_request(url):
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            r.read()
            return r.getcode()
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return "ERROR"

def worker(url, stop_time):
    success = errors = 0
    while time.perf_counter() < stop_time:
        status = send_request(url)
        if status == 200:
            success += 1
        else:
            errors += 1
        time.sleep(0.001)
    return success, errors

def main():
    print(f"Load testing {URL} for {DURATION}s with {CONCURRENCY} threads...")
    stop_time = time.perf_counter() + DURATION
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = [executor.submit(worker, URL, stop_time) for _ in range(CONCURRENCY)]
        results = [f.result() for f in futures]
    total_ok = sum(s for s, _ in results)
    total_err = sum(e for _, e in results)
    total = total_ok + total_err
    print(f"Total: {total} | OK: {total_ok} | Errors: {total_err}")

if __name__ == "__main__":
    main()
```

```bash
# Run on local machine
python3 load_test.py

# Watch scaling on VPS simultaneously
watch -n 1 "kubectl get hpa && echo '' && kubectl get pods"
```