# ComfyUI Docker

## What is this project

Dockerized ComfyUI for Creaturia -- an AI character creation platform. Runs as an image generation API behind Caddy reverse proxy with authentication. Deployed to NVIDIA Cloud GPU instances (not AWS). The NestJS backend at `api.andrewfonseca.dev` sends workflows via SQS, and users interact with ComfyUI through the frontend (embedded iframe or separate tab).

## Architecture

```
Internet
   |
[Caddy :80/:443] -- forward_auth --> [Auth Sidecar :8080]
   |
   |-- /auth/session      -> token exchange, sets cookie, redirects to /
   |-- Bearer token path   -> M2M (backend -> ComfyUI via API key)
   |-- Cookie session path -> Browser (iframe / new tab)
   |
   └── reverse_proxy -> [ComfyUI :8188]
```

## Services (docker-compose.yaml)

| Service | Image | Purpose | Profiles |
|---------|-------|---------|----------|
| `comfyui` | nvidia/cuda:12.6.3 + ComfyUI | GPU inference, port 8188 (internal) | gpu |
| `comfyui-cpu` | ubuntu:24.04 + ComfyUI | CPU fallback for local dev, port 8188 (published) | cpu, dev |
| `caddy` | caddy:2-alpine | Reverse proxy, TLS, auth routing | gpu, cpu, dev |
| `auth-sidecar` | python:3.12-slim + PyJWT | Token/cookie/API-key validation | gpu, cpu, dev |

## Authentication (proxy/)

Three auth paths, all routed by Caddy via `forward_auth` to the auth sidecar:

### 1. Token exchange (`/auth/session?token=...`)
- Frontend calls `POST api.andrewfonseca.dev/v1/comfyui/session` (JWT auth) to get a signed token
- Frontend loads `https://comfy.andrewfonseca.dev/auth/session?token=<signed_token>` as iframe src or new tab
- Auth sidecar validates the JWT (HS256, checks `iss=creaturia-api`, single-use `jti` nonce)
- Sets `comfy_session` HttpOnly cookie, redirects to `/`
- All subsequent requests use the cookie

### 2. Bearer API key (`Authorization: Bearer <key>`)
- M2M path for backend SQS workers calling ComfyUI
- Keys stored in `config/api-keys.json`
- Sidecar endpoint: `/validate`

### 3. Cookie session (default)
- Browser/iframe requests after token exchange
- Sidecar endpoint: `/validate-cookie`
- Validates JWT from `comfy_session` cookie (no nonce check -- cookies are reused)

### Auth sidecar (`proxy/auth-sidecar/main.py`)
- Single-file Python HTTP server with PyJWT
- Endpoints: `/validate`, `/exchange`, `/validate-cookie`
- In-memory nonce tracking with TTL cleanup
- Config via env vars: `COMFY_SESSION_SECRET`, `COOKIE_DOMAIN`, `COOKIE_SECURE`

### Caddyfile (`proxy/Caddyfile`)
- Security headers: `Content-Security-Policy frame-ancestors`, CORS
- CORS preflight handler for OPTIONS
- Three route blocks: `/auth/session`, `@has_bearer`, default cookie

## Environment Variables (`.env`)

| Variable | Local default | Production |
|----------|--------------|------------|
| `DOMAIN` | `localhost` | `comfy.andrewfonseca.dev` |
| `COMFY_SESSION_SECRET` | same as backend `JWT_SECRET` | same as backend `JWT_SECRET` |
| `ALLOWED_ORIGIN` | `http://localhost:5173` | `https://creator.andrewfonseca.dev` |
| `COOKIE_DOMAIN` | _(empty)_ | `.andrewfonseca.dev` |
| `COOKIE_SECURE` | `false` | `true` |
| `AUTH_USER` | `admin` | _(legacy, being replaced)_ |
| `AUTH_HASH` | hashed password | _(legacy, being replaced)_ |

## Custom Nodes (`comfyui-nodes/creaturia_nodes/`)

- **GenerateImageNode**: Calls backend Midjourney API, polls for completion, downloads from S3/Discord CDN
- **CreaturiaShowTextNode**: Displays text in ComfyUI UI
- Env vars: `CREATURIA_API_URL` (default: `http://host.docker.internal:3000`), `CREATURIA_API_TOKEN`

## Models

Download profiles via `scripts/download-models.sh`:

| Profile | Size | Contents |
|---------|------|----------|
| minimal | ~4.5GB | SD 1.5 + VAE |
| standard | ~11.5GB | + SDXL base/refiner + ESRGAN upscalers |
| full | ~23.5GB | + ControlNet + Control-LoRAs + GLIGEN |

Currently downloaded: SD 1.5 (`v1-5-pruned-emaonly.ckpt`) + VAE (~4.3GB).

## Local Development

```bash
# Full stack with auth (CPU + Caddy + sidecar)
docker compose --profile dev up --build

# Direct ComfyUI only (no auth, no proxy)
docker compose --profile dev up comfyui-cpu --build

# Test auth flow
curl http://localhost/system_stats                    # 401 (no auth)
curl -H "Authorization: Bearer <api-key>" http://localhost/system_stats  # 200

# GPU version (requires NVIDIA runtime)
docker compose --profile gpu up --build
```

## Volume Mounts

```
./models/           -> /app/models          (checkpoints, VAE, controlnet)
./output/           -> /app/output          (generated images)
./input/            -> /app/input           (source images)
./comfyui-nodes/    -> /app/custom_nodes/   (Creaturia nodes)
./config/           -> /config/             (api-keys.json, read-only in sidecar)
./proxy/Caddyfile   -> /etc/caddy/Caddyfile
```

## Related Projects

- **Terraform**: `creaturia-tf` -- DNS (`comfy.andrewfonseca.dev`), SSM params, certs
- **Backend**: `creaturia-backend` -- `POST /v1/comfyui/session` issues signed tokens, SQS workers call ComfyUI via Bearer API key
- **Frontend**: `creator` -- embeds ComfyUI in iframe via session URL, "Open in new tab" button