# ComfyUI Docker Modernization Plan

## Context

The current repo has two divergent Dockerfiles (GPU/CPU) with models baked into the image (~10GB), ComfyUI pinned to a year-old commit, and zero authentication. The goal is to create a single, modern Docker setup that:
- Runs locally for development (CPU on Mac)
- Deploys to an NVIDIA VM for production (GPU)
- Exposes the UI with authentication for users and M2M API access
- Sets the foundation for custom nodes and Tripio3D integration

---

## Phase 1: Unified Docker Setup + Latest ComfyUI

### 1.1 Single Dockerfile with multi-stage build args

**File: `Dockerfile`** (rewrite)

Replace both `Dockerfile` and `Dockerfile.cpu` with one file:

```dockerfile
ARG TARGET=gpu

FROM nvidia/cuda:12.6.3-cudnn-devel-ubuntu24.04 AS base-gpu
FROM ubuntu:24.04 AS base-cpu
FROM base-${TARGET} AS main

# System deps (shared)
RUN apt-get update && apt-get install -y \
    git python3 python3-pip python3-venv wget curl ffmpeg \
    libsm6 libxext6 libgl1-mesa-glx git-lfs \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd -m -u 1000 comfyui
USER comfyui
WORKDIR /app

# Clone ComfyUI (latest master by default, or pin via build arg)
ARG COMFYUI_VERSION=master
RUN git clone https://github.com/comfyanonymous/ComfyUI . && \
    git checkout ${COMFYUI_VERSION}

# Python deps (conditional on TARGET)
ARG TARGET=gpu
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"
RUN pip install --upgrade pip && \
    if [ "$TARGET" = "gpu" ]; then \
      pip install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu126 && \
      pip install xformers; \
    else \
      pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu; \
    fi && \
    pip install -r requirements.txt

# Custom nodes (no models downloaded)
RUN cd custom_nodes && \
    git clone https://github.com/Fannovel16/comfyui_controlnet_aux && \
    cd comfyui_controlnet_aux && pip install -r requirements.txt
RUN cd custom_nodes && git clone https://github.com/ltdrdata/ComfyUI-Manager.git
RUN cd custom_nodes && git clone https://github.com/EllangoK/ComfyUI-post-processing-nodes

EXPOSE 8188
COPY --chown=comfyui:comfyui scripts/entrypoint.sh /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]
```

Key changes:
- **Drop pyenv** - use system Python 3 (Ubuntu 24.04 ships 3.12), saves build time and image size
- **No model downloads** in Dockerfile - all models via volume mounts
- **Single port 8188** (ComfyUI default) for both targets
- **CUDA 12.6** (current stable, matches latest PyTorch)
- **Ubuntu 24.04** (LTS, latest)
- **ComfyUI-Manager** included for both (makes node management easier via UI)

### 1.2 Entrypoint script

**File: `scripts/entrypoint.sh`** (new)

Auto-detects GPU availability:
```bash
#!/bin/bash
EXTRA_ARGS=""
if ! command -v nvidia-smi &>/dev/null || ! nvidia-smi &>/dev/null; then
  EXTRA_ARGS="--cpu"
fi
exec python3 main.py --listen 0.0.0.0 --port 8188 $EXTRA_ARGS "$@"
```

### 1.3 Unified docker-compose with profiles

**File: `docker-compose.yaml`** (rewrite)

```yaml
services:
  comfyui:
    build:
      context: .
      args:
        TARGET: gpu
    ports:
      - "8188:8188"
    volumes:
      - ./models:/app/models
      - ./output:/app/output
      - ./input:/app/input
    profiles: ["gpu"]
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: unless-stopped

  comfyui-cpu:
    build:
      context: .
      args:
        TARGET: cpu
    ports:
      - "8188:8188"
    volumes:
      - ./models:/app/models
      - ./output:/app/output
      - ./input:/app/input
    profiles: ["cpu"]
    restart: unless-stopped
```

Usage:
- **Local dev**: `docker compose --profile cpu up --build`
- **NVIDIA VM**: `docker compose --profile gpu up --build`

### 1.4 Model download script

**File: `scripts/download-models.sh`** (new)

Takes a profile arg (`minimal`, `standard`, `full`):
- `minimal`: SD1.5 + VAE (~4.5GB) - for local CPU dev
- `standard`: SDXL base + refiner + VAE + ESRGAN (~7GB) - default for GPU
- `full`: standard + ControlNet + GLIGEN + Control-LoRAs (~12GB)

Uses `wget -c` for resume support. Downloads to `./models/`.

### 1.5 Build optimization files

**File: `.dockerignore`** (new)
```
models/
output/
input/
.git
*.md
aws-*
```
Critical - without this, Docker sends 4GB+ models as build context.

**File: `.gitignore`** (update)
```
models/**/*.ckpt
models/**/*.safetensors
models/**/*.pth
models/**/*.bin
output/
.env
```

### 1.6 Cleanup

**Delete**: `Dockerfile.cpu`, `docker-compose.cpu.yaml`, `docker-compose-aws.yaml`
**Update**: `test_workflow.py` (point to port 8188, adjust model paths)
**Keep**: AWS scripts as reference (or move to `scripts/aws/`)

---

## Phase 2: Authentication (Caddy + Auth Sidecar)

### Architecture

ComfyUI has no built-in auth. Add **Caddy** as reverse proxy with:
- **Basic auth** for browser/UI users
- **Bearer token validation** for M2M API access via a small auth sidecar
- Automatic WebSocket proxying (Caddy handles this natively)

### 2.1 Caddy configuration

**File: `proxy/Caddyfile`** (new)

```
{$DOMAIN:localhost} {
    # M2M: requests with Bearer token -> validate via sidecar
    @has_bearer header Authorization Bearer*
    handle @has_bearer {
        forward_auth auth-sidecar:8080 {
            uri /validate
            copy_headers X-User
        }
        reverse_proxy comfyui:8188
    }

    # Browser users: basic auth
    handle {
        basicauth {
            {$AUTH_USER} {$AUTH_HASH}
        }
        reverse_proxy comfyui:8188
    }
}
```

### 2.2 Auth sidecar

**File: `proxy/auth-sidecar/main.py`** (new, ~80 lines)

Minimal Python HTTP server that:
- Reads API keys from `/config/api-keys.json`
- Validates `Authorization: Bearer <key>` headers
- Returns 200 + `X-User` header on success, 401 on failure

**File: `proxy/auth-sidecar/Dockerfile`** (new)

### 2.3 Updated docker-compose

Add to `docker-compose.yaml`:
```yaml
  caddy:
    image: caddy:2-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./proxy/Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
    env_file: .env
    depends_on: [comfyui]  # or comfyui-cpu
    profiles: ["gpu", "cpu"]

  auth-sidecar:
    build: ./proxy/auth-sidecar
    volumes:
      - ./config/api-keys.json:/config/api-keys.json:ro
    profiles: ["gpu", "cpu"]
```

ComfyUI changes from `ports` to `expose` (only accessible via Caddy).

### 2.4 Config files

- **`.env.example`**: `DOMAIN`, `AUTH_USER`, `AUTH_HASH`
- **`config/api-keys.json.example`**: template for API keys
- **`scripts/generate-api-key.sh`**: helper to generate keys

### 2.5 Local dev vs Production

- `DOMAIN=localhost` -> Caddy serves HTTP on port 80, basic auth works
- `DOMAIN=comfyui.yourdomain.com` -> auto-HTTPS via Let's Encrypt

---

## Phase 3: Custom HTTP Request Node (Future)

**Directory: `custom_nodes/comfyui-http-request/`**

Two ComfyUI nodes:
- **HTTPImageFetchNode**: GET/POST to URL -> returns IMAGE tensor
- **HTTPRequestNode**: generic HTTP request -> returns STRING response

Volume-mounted for live development. Needs ComfyUI restart to register new nodes.

---

## Phase 4: Tripio3D Integration (Future)

**Directory: `custom_nodes/comfyui-tripio3d/`**

Nodes that call Tripio3D API:
- **Tripio3DTextTo3D**: text prompt -> 3D model file
- **Tripio3DImageTo3D**: IMAGE input -> 3D model file

API-based initially (uses Tripio3D cloud). Local inference later if needed.

---

## Files Summary

### Phase 1 - Create
| File | Purpose |
|------|---------|
| `scripts/entrypoint.sh` | Auto-detect GPU/CPU |
| `scripts/download-models.sh` | Download models by profile |
| `.dockerignore` | Exclude models from build context |

### Phase 1 - Rewrite
| File | Purpose |
|------|---------|
| `Dockerfile` | Unified GPU/CPU with build args |
| `docker-compose.yaml` | Profiles for gpu/cpu |
| `.gitignore` | Exclude model binaries |

### Phase 1 - Delete
| File | Reason |
|------|--------|
| `Dockerfile.cpu` | Merged into unified Dockerfile |
| `docker-compose.cpu.yaml` | Merged into docker-compose.yaml |
| `docker-compose-aws.yaml` | Merged into docker-compose.yaml |

### Phase 2 - Create
| File | Purpose |
|------|---------|
| `proxy/Caddyfile` | Reverse proxy + auth config |
| `proxy/auth-sidecar/main.py` | API key validation service |
| `proxy/auth-sidecar/Dockerfile` | Auth sidecar container |
| `.env.example` | Environment template |
| `config/api-keys.json.example` | API keys template |
| `scripts/generate-api-key.sh` | Key generation helper |

---

## Decisions Made
- **Scope**: Phase 1 only first, then Phase 2 in follow-up
- **Models**: Minimal (SD1.5 + VAE) - add more later via ComfyUI-Manager or download script
- **Auth**: Basic auth + API keys (Caddy) - simple, no SSO needed

## Implementation Order (Phase 1)
1. Create `.dockerignore`
2. Create `scripts/entrypoint.sh`
3. Create `scripts/download-models.sh` (minimal profile: SD1.5 + VAE)
4. Rewrite `Dockerfile` (unified GPU/CPU)
5. Rewrite `docker-compose.yaml` (profiles)
6. Update `.gitignore`
7. Delete `Dockerfile.cpu`, `docker-compose.cpu.yaml`, `docker-compose-aws.yaml`
8. Update `test_workflow.py` for new setup

## Verification (Phase 1)
1. `docker compose --profile cpu up --build` - should start ComfyUI on port 8188
2. `curl http://localhost:8188/system_stats` - should return system info
3. UI accessible at `http://localhost:8188` in browser
4. `scripts/download-models.sh minimal` downloads SD1.5 + VAE to ./models/
5. `python test_workflow.py` generates an image successfully
