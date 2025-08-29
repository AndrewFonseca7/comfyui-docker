# ComfyUI AWS GPU Deployment Guide

## 🚀 Instance Launch Setup

### 1. EC2 Instance Configuration
- **Instance Type**: `g4dn.xlarge`
- **AMI**: Deep Learning AMI (Ubuntu 22.04) - `ami-0c02fb55956c7d316` (us-east-1)
- **Storage**: 50GB gp3 (para modelos + outputs)
- **Security Group**: 
  - SSH (22): Tu IP
  - Custom TCP (7860): 0.0.0.0/0 (para acceso web)
  - Custom TCP (8080): 0.0.0.0/0 (alternativo)

### 2. Launch Commands
```bash
# 1. Launch instance (reemplaza YOUR_KEY_NAME y YOUR_IP)
aws ec2 run-instances \
  --image-id ami-0c02fb55956c7d316 \
  --instance-type g4dn.xlarge \
  --key-name YOUR_KEY_NAME \
  --security-group-ids sg-YOUR_SECURITY_GROUP \
  --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=50,VolumeType=gp3}' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=ComfyUI-GPU-Test}]'

# 2. Get instance IP
aws ec2 describe-instances --filters "Name=tag:Name,Values=ComfyUI-GPU-Test" --query 'Reservations[].Instances[].PublicIpAddress' --output text
```

## 📦 Instance Setup Script

### Archivo: `setup-aws-instance.sh`
```bash
#!/bin/bash
echo "🚀 Setting up ComfyUI on AWS GPU instance..."

# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker ubuntu
fi

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update && sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker

# Clone the repository
git clone https://github.com/YOUR_USERNAME/comfyui-docker.git || echo "Usando código local"
cd comfyui-docker

# Test NVIDIA setup
nvidia-smi
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi

echo "✅ Setup complete! Ready to run ComfyUI GPU version."
```

## 🐳 Docker Files para AWS

### Modified docker-compose-aws.yaml
```yaml
version: "3.8"

services:
  comfyui-gpu:
    build: .
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - CUDA_VISIBLE_DEVICES=0
    ports:
      - "7860:7860"
      - "8080:7860"  # Alternative port
    volumes:
      - ./aws-outputs:/home/user/app/output
      - ./aws-inputs:/home/user/app/input
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: unless-stopped
```

## 📊 Performance Testing Script

### Archivo: `aws-performance-test.py`
```python
#!/usr/bin/env python3
"""
AWS GPU Performance Testing Script
Tests ComfyUI performance and tracks costs
"""

import requests
import json
import time
import datetime
from typing import Dict, List

class ComfyUITester:
    def __init__(self, base_url: str = "http://localhost:7860"):
        self.base_url = base_url
        self.results = []
    
    def test_workflow(self, prompt: str, steps: int = 20) -> Dict:
        """Test a workflow and measure performance"""
        
        workflow = {
            "3": {
                "inputs": {
                    "seed": int(time.time()),
                    "steps": steps,
                    "cfg": 7.0,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0]
                },
                "class_type": "KSampler"
            },
            "4": {
                "inputs": {
                    "ckpt_name": "sd_xl_base_1.0.safetensors"  # GPU version uses SDXL
                },
                "class_type": "CheckpointLoaderSimple"
            },
            "5": {
                "inputs": {
                    "width": 1024,  # Higher resolution for GPU
                    "height": 1024,
                    "batch_size": 1
                },
                "class_type": "EmptyLatentImage"
            },
            "6": {
                "inputs": {
                    "text": prompt,
                    "clip": ["4", 1]
                },
                "class_type": "CLIPTextEncode"
            },
            "7": {
                "inputs": {
                    "text": "blurry, low quality, distorted, deformed, worst quality",
                    "clip": ["4", 1]
                },
                "class_type": "CLIPTextEncode"
            },
            "8": {
                "inputs": {
                    "samples": ["3", 0],
                    "vae": ["4", 2]
                },
                "class_type": "VAEDecode"
            },
            "9": {
                "inputs": {
                    "filename_prefix": f"AWS_GPU_test_{int(time.time())}",
                    "images": ["8", 0]
                },
                "class_type": "SaveImage"
            }
        }
        
        print(f"🎨 Testing: '{prompt}' ({steps} steps, 1024x1024)")
        start_time = time.time()
        
        # Send workflow
        response = requests.post(
            f"{self.base_url}/prompt",
            json={"prompt": workflow}
        )
        
        if response.status_code != 200:
            return {"error": f"Failed to submit: {response.status_code}"}
        
        prompt_id = response.json()["prompt_id"]
        
        # Monitor completion
        while True:
            history_response = requests.get(f"{self.base_url}/history/{prompt_id}")
            if history_response.status_code == 200 and prompt_id in history_response.json():
                break
            time.sleep(1)
        
        end_time = time.time()
        duration = end_time - start_time
        
        result = {
            "prompt": prompt,
            "steps": steps,
            "resolution": "1024x1024",
            "duration": duration,
            "timestamp": datetime.datetime.now().isoformat(),
            "prompt_id": prompt_id
        }
        
        self.results.append(result)
        print(f"✅ Completed in {duration:.1f}s")
        return result
    
    def run_benchmark_suite(self):
        """Run comprehensive benchmark tests"""
        
        test_cases = [
            ("a majestic dragon flying over mountains, fantasy art", 20),
            ("portrait of a wise old wizard, detailed, photorealistic", 25),
            ("futuristic cityscape at night, cyberpunk, neon lights", 20),
            ("beautiful landscape with waterfalls, nature photography", 15),
            ("abstract geometric patterns, colorful, digital art", 15)
        ]
        
        print("🚀 Starting AWS GPU Benchmark Suite")
        print("=" * 50)
        
        for prompt, steps in test_cases:
            self.test_workflow(prompt, steps)
            time.sleep(2)  # Brief pause between tests
        
        self.generate_report()
    
    def generate_report(self):
        """Generate performance report"""
        
        if not self.results:
            return
        
        total_time = sum(r["duration"] for r in self.results)
        avg_time = total_time / len(self.results)
        
        print("\n📊 AWS GPU Performance Report")
        print("=" * 50)
        print(f"Total tests: {len(self.results)}")
        print(f"Total time: {total_time:.1f}s")
        print(f"Average time per image: {avg_time:.1f}s")
        print(f"Images per minute: {60/avg_time:.1f}")
        
        # Cost estimation (g4dn.xlarge = $0.526/hour)
        cost_per_hour = 0.526
        cost_per_second = cost_per_hour / 3600
        estimated_cost = total_time * cost_per_second
        
        print(f"\n💰 Cost Analysis:")
        print(f"Test duration: {total_time/60:.1f} minutes")
        print(f"Estimated cost: ${estimated_cost:.4f}")
        print(f"Cost per image: ${estimated_cost/len(self.results):.4f}")
        
        # Save results
        with open(f"aws_gpu_results_{int(time.time())}.json", "w") as f:
            json.dump({
                "results": self.results,
                "summary": {
                    "total_tests": len(self.results),
                    "total_time": total_time,
                    "avg_time": avg_time,
                    "estimated_cost": estimated_cost
                }
            }, f, indent=2)
        
        print(f"📁 Results saved to aws_gpu_results_{int(time.time())}.json")

if __name__ == "__main__":
    tester = ComfyUITester()
    tester.run_benchmark_suite()
```

## 🔧 Quick Deploy Commands

```bash
# 1. Upload files to AWS instance
scp -i ~/.ssh/YOUR_KEY.pem setup-aws-instance.sh ubuntu@YOUR_EC2_IP:~/
scp -i ~/.ssh/YOUR_KEY.pem docker-compose-aws.yaml ubuntu@YOUR_EC2_IP:~/
scp -i ~/.ssh/YOUR_KEY.pem aws-performance-test.py ubuntu@YOUR_EC2_IP:~/

# 2. SSH and setup
ssh -i ~/.ssh/YOUR_KEY.pem ubuntu@YOUR_EC2_IP
chmod +x setup-aws-instance.sh
./setup-aws-instance.sh

# 3. Run ComfyUI GPU
docker-compose -f docker-compose-aws.yaml up --build

# 4. Run performance tests (in another terminal)
python3 aws-performance-test.py
```

## 📈 Expected Performance vs Cost

### GPU (g4dn.xlarge) vs M3 Pro CPU
- **Speed improvement**: 15-25x faster
- **Quality**: SDXL models (vs SD 1.5 on CPU)
- **Resolution**: 1024x1024 (vs 512x512 on CPU)
- **Time per image**: ~20-30 seconds (vs 1-2 minutes CPU)
- **Cost**: $0.526/hour (~$0.004 per image)

### 4-Hour Testing Budget
- **Total cost**: ~$2.10
- **Expected images**: 400-500 images
- **Testing scenarios**: Multiple models, resolutions, styles
- **ROI**: Comprehensive performance baseline for production decisions