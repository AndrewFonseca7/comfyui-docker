#!/usr/bin/env python3
"""
Test workflow for ComfyUI API
Generates a simple text-to-image using SD 1.5 model

Usage:
  python test_workflow.py                          # Direct to ComfyUI (port 8188)
  python test_workflow.py --url http://localhost    # Via Caddy proxy (port 80)
  python test_workflow.py --api-key YOUR_KEY        # Via Caddy with Bearer auth
  python test_workflow.py --skip-generation         # Only test system info
"""

import requests
import json
import time
import sys
import os

# ComfyUI API base URL (direct by default, use --url for Caddy proxy)
API_URL = os.environ.get("COMFYUI_URL", "http://localhost:8188")
API_KEY = os.environ.get("COMFYUI_API_KEY", "")

# Parse CLI args
for i, arg in enumerate(sys.argv[1:], 1):
    if arg == "--url" and i < len(sys.argv) - 1:
        API_URL = sys.argv[i + 1]
    elif arg == "--api-key" and i < len(sys.argv) - 1:
        API_KEY = sys.argv[i + 1]


def get_headers():
    """Return auth headers if API key is configured."""
    if API_KEY:
        return {"Authorization": f"Bearer {API_KEY}"}
    return {}

def test_basic_workflow():
    """Test basic text-to-image generation workflow"""
    
    # Basic workflow for SD 1.5 text-to-image
    workflow = {
        "3": {
            "inputs": {
                "seed": 42,
                "steps": 10,  # Reduced for faster CPU generation
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
                "ckpt_name": "v1-5-pruned-emaonly.ckpt"
            },
            "class_type": "CheckpointLoaderSimple"
        },
        "5": {
            "inputs": {
                "width": 512,
                "height": 512,
                "batch_size": 1
            },
            "class_type": "EmptyLatentImage"
        },
        "6": {
            "inputs": {
                "text": "a beautiful mountain landscape at sunset, photorealistic",
                "clip": ["4", 1]
            },
            "class_type": "CLIPTextEncode"
        },
        "7": {
            "inputs": {
                "text": "blurry, low quality, distorted",
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
                "filename_prefix": "ComfyUI_API_test",
                "images": ["8", 0]
            },
            "class_type": "SaveImage"
        }
    }
    
    print("🚀 Sending workflow to ComfyUI...")
    print(f"📝 Prompt: {workflow['6']['inputs']['text']}")
    
    try:
        # Send the workflow
        response = requests.post(
            f"{API_URL}/prompt",
            json={"prompt": workflow},
            headers=get_headers(),
            timeout=300  # 5 minute timeout
        )
        
        if response.status_code == 200:
            result = response.json()
            prompt_id = result.get("prompt_id")
            print(f"✅ Workflow submitted successfully! Prompt ID: {prompt_id}")
            
            # Monitor progress
            print("⏳ Generating image (this may take several minutes on CPU)...")
            monitor_progress(prompt_id)
            
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")

def monitor_progress(prompt_id):
    """Monitor the progress of image generation"""
    start_time = time.time()
    
    while True:
        try:
            # Check history
            response = requests.get(f"{API_URL}/history/{prompt_id}", headers=get_headers())
            
            if response.status_code == 200:
                history = response.json()
                
                if prompt_id in history:
                    # Generation completed
                    elapsed = time.time() - start_time
                    print(f"✅ Image generated successfully in {elapsed:.1f} seconds!")
                    
                    # Get the generated image info
                    outputs = history[prompt_id].get("outputs", {})
                    if "9" in outputs and "images" in outputs["9"]:
                        image_info = outputs["9"]["images"][0]
                        filename = image_info["filename"]
                        print(f"📸 Image saved as: {filename}")
                        print(f"🌐 View at: {API_URL}/view?filename={filename}")
                    break
            
            # Wait before next check
            time.sleep(2)
            
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Monitoring error: {e}")
            time.sleep(5)

def test_system_info():
    """Test system information endpoints"""
    print("🔍 Testing system endpoints...")
    
    try:
        # System stats
        response = requests.get(f"{API_URL}/system_stats", headers=get_headers())
        if response.status_code == 200:
            stats = response.json()
            print("📊 System Stats:")
            print(f"   Python: {stats['system']['python_version']}")
            print(f"   Device: {stats['devices'][0]['name']}")
            print(f"   VRAM: {stats['devices'][0]['vram_total'] / 1024**3:.1f} GB")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ System info failed: {e}")

if __name__ == "__main__":
    print("🎨 ComfyUI API Test Script")
    print("=" * 40)
    
    # Test system info first
    test_system_info()
    print()
    
    # Test workflow
    if len(sys.argv) > 1 and sys.argv[1] == "--skip-generation":
        print("⏭️ Skipping image generation (--skip-generation flag)")
    else:
        test_basic_workflow()

