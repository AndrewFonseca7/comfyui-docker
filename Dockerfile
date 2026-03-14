ARG TARGET=gpu

FROM nvidia/cuda:12.6.3-cudnn-devel-ubuntu24.04 AS base-gpu
FROM ubuntu:24.04 AS base-cpu
FROM base-${TARGET} AS main

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=America/Los_Angeles

# System deps (shared)
RUN apt-get update && apt-get install -y \
    git python3 python3-pip python3-venv wget curl ffmpeg \
    libsm6 libxext6 libgl1-mesa-dev git-lfs \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd -m -o -u 1000 comfyui
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

# Custom nodes
RUN cd custom_nodes && \
    git clone https://github.com/Fannovel16/comfyui_controlnet_aux && \
    cd comfyui_controlnet_aux && pip install -r requirements.txt
RUN cd custom_nodes && git clone https://github.com/ltdrdata/ComfyUI-Manager.git
RUN cd custom_nodes && git clone https://github.com/EllangoK/ComfyUI-post-processing-nodes

EXPOSE 8188
COPY --chown=comfyui:comfyui scripts/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]
