#!/bin/bash
set -e

PROFILE="${1:-minimal}"
MODELS_DIR="${2:-./models}"

echo "Downloading models (profile: $PROFILE) to $MODELS_DIR"

mkdir -p "$MODELS_DIR"/{checkpoints,vae,upscale_models,controlnet,gligen}

# Download helper: curl with resume support, saves to directory with original filename
download() {
  local url="$1"
  local dir="$2"
  local filename
  filename=$(basename "$url")
  curl -L -C - -o "$dir/$filename" "$url"
}

# Minimal: SD1.5 + VAE (~4.5GB)
if [ "$PROFILE" = "minimal" ] || [ "$PROFILE" = "standard" ] || [ "$PROFILE" = "full" ]; then
  echo "==> Downloading SD 1.5 checkpoint..."
  download https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.ckpt \
    "$MODELS_DIR/checkpoints"

  echo "==> Downloading VAE..."
  download https://huggingface.co/stabilityai/sd-vae-ft-mse-original/resolve/main/vae-ft-mse-840000-ema-pruned.safetensors \
    "$MODELS_DIR/vae"
fi

# Standard: + SDXL base/refiner + ESRGAN (~7GB additional)
if [ "$PROFILE" = "standard" ] || [ "$PROFILE" = "full" ]; then
  echo "==> Downloading SDXL base..."
  download https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors \
    "$MODELS_DIR/checkpoints"

  echo "==> Downloading SDXL refiner..."
  download https://huggingface.co/stabilityai/stable-diffusion-xl-refiner-1.0/resolve/main/sd_xl_refiner_1.0.safetensors \
    "$MODELS_DIR/checkpoints"

  echo "==> Downloading ESRGAN upscale models..."
  download https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth \
    "$MODELS_DIR/upscale_models"
  download https://huggingface.co/sberbank-ai/Real-ESRGAN/resolve/main/RealESRGAN_x2.pth \
    "$MODELS_DIR/upscale_models"
  download https://huggingface.co/sberbank-ai/Real-ESRGAN/resolve/main/RealESRGAN_x4.pth \
    "$MODELS_DIR/upscale_models"
fi

# Full: + ControlNet + GLIGEN + Control-LoRAs (~12GB additional)
if [ "$PROFILE" = "full" ]; then
  echo "==> Downloading ControlNet models..."
  download https://huggingface.co/thibaud/controlnet-sd21/resolve/main/control_v11p_sd21_lineart.safetensors \
    "$MODELS_DIR/controlnet"
  download https://huggingface.co/thibaud/controlnet-openpose-sdxl-1.0/resolve/main/OpenPoseXL2.safetensors \
    "$MODELS_DIR/controlnet"

  echo "==> Downloading Control-LoRAs (rank256)..."
  download https://huggingface.co/stabilityai/control-lora/resolve/main/control-LoRAs-rank256/control-lora-canny-rank256.safetensors \
    "$MODELS_DIR/controlnet"
  download https://huggingface.co/stabilityai/control-lora/resolve/main/control-LoRAs-rank256/control-lora-depth-rank256.safetensors \
    "$MODELS_DIR/controlnet"
  download https://huggingface.co/stabilityai/control-lora/resolve/main/control-LoRAs-rank256/control-lora-recolor-rank256.safetensors \
    "$MODELS_DIR/controlnet"
  download https://huggingface.co/stabilityai/control-lora/resolve/main/control-LoRAs-rank256/control-lora-sketch-rank256.safetensors \
    "$MODELS_DIR/controlnet"

  echo "==> Downloading Control-LoRAs (rank128)..."
  download https://huggingface.co/stabilityai/control-lora/resolve/main/control-LoRAs-rank128/control-lora-canny-rank128.safetensors \
    "$MODELS_DIR/controlnet"
  download https://huggingface.co/stabilityai/control-lora/resolve/main/control-LoRAs-rank128/control-lora-depth-rank128.safetensors \
    "$MODELS_DIR/controlnet"
  download https://huggingface.co/stabilityai/control-lora/resolve/main/control-LoRAs-rank128/control-lora-recolor-rank128.safetensors \
    "$MODELS_DIR/controlnet"
  download https://huggingface.co/stabilityai/control-lora/resolve/main/control-LoRAs-rank128/control-lora-sketch-rank128-metadata.safetensors \
    "$MODELS_DIR/controlnet"

  echo "==> Downloading GLIGEN..."
  download https://huggingface.co/comfyanonymous/GLIGEN_pruned_safetensors/resolve/main/gligen_sd14_textbox_pruned_fp16.safetensors \
    "$MODELS_DIR/gligen"
fi

echo "Done! Models downloaded to $MODELS_DIR"
