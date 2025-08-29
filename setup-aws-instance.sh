#!/bin/bash
echo "🚀 Setting up ComfyUI on AWS GPU instance..."

# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker ubuntu
    echo "Docker installed ✅"
fi

# Install Docker Compose
echo "Installing Docker Compose..."
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Install NVIDIA Container Toolkit
echo "Installing NVIDIA Container Toolkit..."
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Create project directory
mkdir -p ~/comfyui-docker
cd ~/comfyui-docker

# Create directories for volumes
mkdir -p aws-outputs aws-inputs

# Test NVIDIA setup
echo "Testing NVIDIA setup..."
nvidia-smi
echo "Testing NVIDIA Docker integration..."
docker run --rm --gpus all nvidia/cuda:12.1.1-base-ubuntu22.04 nvidia-smi

echo ""
echo "✅ Setup complete! Ready to run ComfyUI GPU version."
echo "📁 Working directory: ~/comfyui-docker"
echo "🚀 Next steps:"
echo "  1. Upload your docker files to this directory"
echo "  2. Run: docker-compose -f docker-compose-aws.yaml up --build"
echo "  3. Access ComfyUI at http://$(curl -s ifconfig.me):7860"