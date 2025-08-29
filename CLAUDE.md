# ComfyUI Docker - Context y Notas

## Proyecto Overview
Aplicación ComfyUI Dockerizada para generación de imágenes con IA, configurada para ejecutarse como API.

## Estado Actual
- **Repositorio**: Configurado con Docker para GPU (CUDA) y CPU
- **Problema actual**: Error GPU en Docker Desktop (driver nvidia no disponible)
- **Solución implementada**: Usar versión CPU para testing local

## Configuraciones Disponibles

### GPU Version (Producción)
- **Archivo**: `docker-compose.yaml` + `Dockerfile`
- **Puerto**: 7860
- **Base**: `nvidia/cuda:12.1.1-cudnn8-devel-ubuntu22.04`
- **Modelos**: SDXL, SD2.1, ControlNet, ESRGAN (~10GB)
- **Comando**: `docker-compose up`
- **Velocidad**: ~30 segundos por imagen

### CPU Version (Testing local)
- **Archivo**: `docker-compose.cpu.yaml` + `Dockerfile.cpu`
- **Puerto**: 8188
- **Base**: `ubuntu:22.04`
- **Modelos**: SD 1.5, modelos más pequeños (~2GB)
- **Comando**: `docker-compose -f docker-compose.cpu.yaml up --build`
- **Velocidad**: ~5-30 minutos por imagen

## API Endpoints (ComfyUI)

### Básicos
- `GET /system_stats` - Estado del sistema
- `POST /prompt` - Enviar workflow para generar imagen
- `GET /history` - Historial de generaciones
- `GET /view?filename=imagen.png` - Obtener imagen generada
- `WS /ws` - WebSocket para seguimiento tiempo real

### Ejemplo Workflow Básico
```python
import requests

workflow = {
    "3": {
        "inputs": {
            "seed": 156680208700286,
            "steps": 20,
            "cfg": 8,
            "sampler_name": "euler",
            "scheduler": "normal",
            "denoise": 1,
            "model": ["4", 0],
            "positive": ["6", 0],
            "negative": ["7", 0],
            "latent_image": ["5", 0]
        },
        "class_type": "KSampler"
    }
    # ... más nodos
}

response = requests.post(
    "http://localhost:8188/prompt", 
    json={"prompt": workflow}
)
```

## Plan AWS Testing

### Estrategia de Testing
1. **Fase 1**: Testing local CPU (sin costo AWS)
   - Familiarización con API ComfyUI
   - Desarrollo de workflows básicos
   - Pruebas de integración

2. **Fase 2**: Testing AWS GPU (4 horas, ~$2-3 total)
   - Validación rendimiento real
   - Testing carga/stress
   - Medición costos operativos

### Instancias AWS Recomendadas

#### Para Testing GPU (4 horas)
- **g4dn.xlarge**: $0.526/hora = $2.10 total
  - GPU: NVIDIA Tesla T4 (16GB VRAM)
  - CPU: 4 vCPUs, 16GB RAM
  - Capacidad: SDXL, modelos grandes

#### Para Producción (si escalas)
- **g5.xlarge**: $1.006/hora 
  - GPU: A10G (24GB VRAM)
  - Mejor rendimiento para modelos grandes

#### Para CPU (desarrollo barato)
- **c5.2xlarge**: $0.34/hora
  - 8 vCPUs, 16GB RAM
  - Solo para testing sin GPU

## Comandos Útiles

### Local Development
```bash
# CPU version (testing)
docker-compose -f docker-compose.cpu.yaml up --build

# GPU version (si tienes NVIDIA configurado)
docker-compose up --build

# Verificar estado Docker
docker ps
docker logs comfyui-docker-comfyui-cpu-1
```

### API Testing
```bash
# Test básico
curl http://localhost:8188/system_stats

# Ver modelos disponibles
curl http://localhost:8188/object_info
```

## Resultados Testing M3 Pro (CPU)

### Workflow Básico Probado ✅
- **Modelo**: SD 1.5 (v1-5-pruned-emaonly.ckpt)
- **Resolución**: 512x512
- **Pasos**: 8 (optimizado para CPU)
- **Tiempo aproximado**: 1-2 minutos
- **Prompt**: "a beautiful cat sitting in a garden, photorealistic"
- **Resultado**: ComfyUI_test_00001_.png

### Rendimiento M3 Pro
- **VRAM simulada**: ~7.6GB (RAM unificada)
- **Device**: CPU (sin Metal GPU support en Docker)
- **Velocidad**: Significativamente mejor que CPU Intel estándar
- **Estabilidad**: Excelente, sin errores

### API Endpoints Verificados ✅
- `GET /system_stats` - Funcionando
- `POST /prompt` - Funcionando (workflow ejecutado exitosamente)
- `GET /history` - Funcionando
- `GET /view?filename=` - Disponible para ver imágenes

## AWS GPU Deployment Ready ✅

### Archivos Creados para AWS
- `aws-deploy.md` - Guía completa de deployment
- `setup-aws-instance.sh` - Script de configuración automática  
- `docker-compose-aws.yaml` - Docker config para GPU
- `aws-performance-test.py` - Suite de benchmarks
- `aws-launch.sh` - Launcher automático de instancia EC2

### Quick Start AWS GPU (Estimado: $2.10 para 4 horas)

```bash
# 1. Lanzar instancia (reemplazar your-key-name)
./aws-launch.sh us-east-1 your-key-name

# 2. Subir archivos (usar IP de output)
scp -i ~/.ssh/your-key-name.pem *.sh *.yaml *.py ubuntu@EC2_IP:~/

# 3. SSH y configurar
ssh -i ~/.ssh/your-key-name.pem ubuntu@EC2_IP
./setup-aws-instance.sh

# 4. Subir código Docker y ejecutar
# ... subir Dockerfile, requirements.txt
docker-compose -f docker-compose-aws.yaml up --build

# 5. Ejecutar benchmark
python3 aws-performance-test.py http://localhost:7860 full
```

### Performance Esperado vs M3 Pro CPU
- **Velocidad**: 15-25x más rápido
- **Calidad**: SDXL (vs SD 1.5)
- **Resolución**: 1024x1024 (vs 512x512)
- **Tiempo por imagen**: ~20-30s (vs 90s)
- **Costo por imagen**: ~$0.004

## Próximos Pasos
1. [x] Ejecutar versión CPU local para familiarización
2. [x] Desarrollar/probar workflows básicos
3. [x] Preparar configuración para AWS GPU
4. [ ] Testing 4 horas en AWS g4dn.xlarge
5. [ ] Evaluación costos vs rendimiento

## Notas Técnicas
- Primera ejecución tarda 15-30 min (descarga modelos)
- CPU version: modelos más pequeños para testing
- GPU version: full capacity, modelos pesados
- API compatible entre ambas versiones (solo cambia velocidad)