# 🚀 Django & PostgreSQL Kubernetes Production Guide
### *A Production-Ready Blueprint for Helm, Kind, Ingress Nginx, and HPA*

This guide provides a comprehensive, step-by-step production playbook to configure, deploy, scale, and manage any Django application integrated with a persistent PostgreSQL database, Ingress Nginx, and Horizontal Pod Autoscaler (HPA) using Kubernetes (K8s) in a Kind cluster.

> [!IMPORTANT]
> **Configuration placeholders:**  
> Before applying these configurations, make sure to replace all placeholders like `<project-name>`, `<domain-name>`, `<db-service-name>`, and `<docker-image>` with your actual project values.

---

## 📋 Table of Contents
1. [Prerequisites & Tool Installation](#1-prerequisites--tool-installation)
2. [Kubernetes Cluster Setup (Kind)](#2-kubernetes-cluster-setup-kind)
3. [Ingress Nginx Setup](#3-ingress-nginx-setup)
4. [Helm Chart Setup & Configuration](#4-helm-chart-setup--configuration)
5. [PostgreSQL Database Deployment](#5-postgresql-database-deployment-helm-templates)
6. [Configuring `values.yaml`](#6-configuring-valuesyaml)
7. [Cluster Operations & Management](#7-cluster-operations--management)
8. [HPA Setup & Verification (Metrics Server)](#8-hpa-setup--verification-metrics-server)

---

## 🛠️ 1. Prerequisites & Tool Installation

### Install Docker
```bash
# Update package repositories
sudo apt update

# Install Docker
sudo apt install -y docker.io

# Enable and start Docker service
sudo systemctl enable docker
sudo systemctl start docker

# Add your current user to the Docker group
sudo usermod -aG docker $USER
newgrp docker

# Verify installation
docker --version
docker run hello-world
```

### Install kubectl
```bash
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/
kubectl version --client
```

### Install Helm
```bash
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-4
chmod 700 get_helm.sh
./get_helm.sh && rm get_helm.sh
```

### Install Kind
```bash
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.25.0/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind
```

---

## ☸️ 2. Kubernetes Cluster Setup (Kind)

### Create a Config File (`config.yaml`)
Create a `config.yaml` file to configure Kind to map host ports `80` and `443` to the Ingress controller on the control plane node:

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
        hostPort: 80
        protocol: TCP
      - containerPort: 443
        hostPort: 443
        protocol: TCP
  - role: worker
    image: kindest/node:v1.31.2
  - role: worker
    image: kindest/node:v1.31.2
```

### Create Cluster
```bash
kind create cluster --name <project-name>-cluster --config config.yaml
```

### Delete Cluster (If needed)
```bash
kind delete cluster --name <project-name>-cluster
```

---

## 🌐 3. Ingress Nginx Setup
Deploy the Nginx Ingress Controller specifically patched for Kind port forwards:
```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.10.4/deploy/static/provider/kind/deploy.yaml
```

Wait until the ingress controller pods are fully running and ready:
```bash
kubectl get pods -n ingress-nginx --watch
```

---

## 📦 4. Helm Chart Setup & Configuration

### Create Helm Chart (If creating a new one)
```bash
helm create <project-name>
```

### Define Secret Template (`templates/secret.yaml`)
Create `templates/secret.yaml` to dynamically build base64-encoded Kubernetes Secrets from the variables defined in `values.yaml`:
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

### Inject Secrets Into Application Deployment (`templates/deployment.yaml`)
Add `envFrom` under `spec.template.spec.containers` to load the database credentials and Django environment variables dynamically:
```yaml
envFrom:
  - secretRef:
      name: {{ include "<project-name>.fullname" . }}-env
```

---

## 🗄️ 5. PostgreSQL Database Deployment (Helm Templates)

To deploy PostgreSQL inside the cluster, add the following templates in your Helm chart directory:

### PVC Configuration (`templates/db-pvc.yaml`)
Reserves persistent storage for the database:
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
      storage: 1Gi
```

### Database Deployment (`templates/db-deployment.yaml`)
Configures the PostgreSQL container and mounts the PVC:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "<project-name>.fullname" . }}-db
  labels:
    {{- include "<project-name>.labels" . | nindent 4 }}
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: {{ include "<project-name>.name" . }}-db
      app.kubernetes.io/instance: {{ .Release.Name }}
  template:
    metadata:
      labels:
        app.kubernetes.io/name: {{ include "<project-name>.name" . }}-db
        app.kubernetes.io/instance: {{ .Release.Name }}
    spec:
      containers:
        - name: db
          image: postgres:15
          envFrom:
            - secretRef:
                name: {{ include "<project-name>.fullname" . }}-env
          ports:
            - containerPort: 5432
          volumeMounts:
            - name: db-data
              mountPath: /var/lib/postgresql/data
      volumes:
        - name: db-data
          persistentVolumeClaim:
            claimName: {{ include "<project-name>.fullname" . }}-db-pvc
```

### Database Service (`templates/db-service.yaml`)
Exposes the database dynamically to the application. The name of the service uses a variable from `values.yaml` so changing the host automatically syncs the DNS record:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ .Values.env.DB_HOST }}
  labels:
    {{- include "<project-name>.labels" . | nindent 4 }}
spec:
  ports:
    - port: 5432
      targetPort: 5432
      name: postgres
  selector:
    app.kubernetes.io/name: {{ include "<project-name>.name" . }}-db
    app.kubernetes.io/instance: {{ .Release.Name }}
```

---

## ⚙️ 6. Configuring `values.yaml`

Configure resource allocations, database connection, and auto-scaling limits:

```yaml
# PullPolicy ensures that updated docker images are always pulled
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
    - host: <domain-name>
      paths:
        - path: /
          pathType: Prefix

# Define Resources to prevent OOMKilled errors (essential for Gunicorn/Uvicorn multi-workers)
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

# Auto-scaling Configuration (HPA)
autoscaling:
  enabled: true
  minReplicas: 1
  maxReplicas: 5
  targetCPUUtilizationPercentage: 80
  targetMemoryUtilizationPercentage: 80

# Environment variables matching your secret template
env:
  SECRET_KEY: "your-django-secret-key"
  DEBUG: "False"
  ALLOWED_HOSTS: "*"
  USE_PSQL: "True"
  DB_NAME: "<db-name>"
  DB_USER: "<db-user>"
  DB_PASSWORD: "your_password"
  DB_HOST: "<db-service-name>"  # Must match the DB Service Name
  DB_PORT: "5432"
  CORS_ALLOW_ORIGINS: "http://localhost:8000,http://<domain-name>"
  CSRF_TRUSTED_ORIGINS: "http://localhost:8000,http://<domain-name>"
```

---

## 🚀 7. Cluster Operations & Management

### Deploy the Chart
```bash
helm install <project-name> <project-name>/
```

### Upgrade the Chart
Reset the Helm cached variables and deploy updates:
```bash
helm upgrade <project-name> <project-name>/ --reset-values
```

### Rolling Restart of Pods
Required to force the pods to pick up updated Secrets/ConfigMaps:
```bash
kubectl rollout restart deployment/<project-name>
```

### Run Django Commands Inside Kubernetes
Execute commands directly inside the running pod using the Deployment selector (no pod name changes needed):
```bash
# Apply migrations
kubectl exec -it deployment/<project-name> -- python manage.py migrate

# Create django superuser
kubectl exec -it deployment/<project-name> -- python manage.py createsuperuser

# Enter django shell
kubectl exec -it deployment/<project-name> -- python manage.py shell

# Enter pod's bash shell
kubectl exec -it deployment/<project-name> -- bash
```

---

## 📈 8. HPA Setup & Verification (Metrics Server)

HPA requires **Metrics Server** to fetch CPU and memory metrics.

### Install Metrics Server
```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

### Patch Metrics Server (Insecure TLS Bypass for Kind)
Because Kind uses self-signed certificates, patch the Metrics Server deployment to add the `--kubelet-insecure-tls` flag:
```bash
kubectl patch deployment metrics-server -n kube-system --type='json' -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"}]'
```

Wait ~60 seconds for metrics to start collecting, then verify:
```bash
# Check metrics-server pod status (Must be 1/1 Ready)
kubectl get pods -n kube-system -l k8s-app=metrics-server

# Check HPA status (Targets must show actual percentages, not <unknown>)
kubectl get hpa
```

### Perform Load Test & Verify Autoscaling

1. Create a script named `load_test.py` on your local computer. You can adjust the following configuration parameters at the top of the script:

```python
URL = "https://<domain-name>/admin"
DURATION = 60      # Duration in seconds
CONCURRENCY = 20   # Number of concurrent request threads
```

<details>
<summary>📄 <b>Click to see the full load_test.py code</b></summary>

```python
import time
import urllib.request
import urllib.error
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

URL = "https://<domain-name>/admin"
DURATION = 60  # Run for 60 seconds to allow metrics to collect
CONCURRENCY = 20  # Number of concurrent threads to generate high load

def ensure_localhost(url):
    host = urlparse(url).hostname
    if host not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("This script only allows localhost URLs.")

def send_request(url):
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            response.read()
            return response.getcode()
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return "ERROR"

def worker(url, stop_time):
    success = 0
    errors = 0
    while time.perf_counter() < stop_time:
        status = send_request(url)
        if status == 200:
            success += 1
        else:
            errors += 1
        time.sleep(0.001)  # small pause to yield execution
    return success, errors

def main():
    # ensure_localhost(URL)
    print(f"Generating load on {URL} for {DURATION} seconds with concurrency {CONCURRENCY}...")
    
    start_time = time.perf_counter()
    stop_time = start_time + DURATION
    
    # Run workers in ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = [executor.submit(worker, URL, stop_time) for _ in range(CONCURRENCY)]
        results = [f.result() for f in futures]
        
    total_success = sum(success for success, _ in results)
    total_errors = sum(errors for _, errors in results)
    actual_duration = time.perf_counter() - start_time
    total_requests = total_success + total_errors
    
    print(f"\n--- Load Test Finished ---")
    print(f"Total requests: {total_requests}")
    print(f"Duration: {actual_duration:.2f}s")
    print(f"Requests/sec: {total_requests / actual_duration:.2f}")
    print(f"200 OK: {total_success}")
    print(f"Errors: {total_errors}")

if __name__ == "__main__":
    main()
```

</details>


2. Run the load test on your local computer to generate traffic on the Django application:
```bash
python3 load_test.py
```

3. While the load test is running, run this command on the VPS to watch the pod replica count increase live as CPU utilization spikes:
```bash
watch -n 1 "kubectl get hpa && echo '' && kubectl get pods"
```
