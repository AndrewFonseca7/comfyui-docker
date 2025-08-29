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
    
    def test_system_info(self):
        """Test system information"""
        try:
            response = requests.get(f"{self.base_url}/system_stats")
            if response.status_code == 200:
                stats = response.json()
                print("📊 System Information:")
                print(f"   Device: {stats['devices'][0]['name']}")
                print(f"   VRAM: {stats['devices'][0]['vram_total'] / 1024**3:.1f} GB")
                print(f"   Python: {stats['system']['python_version']}")
                return stats
        except Exception as e:
            print(f"❌ System info error: {e}")
        return None
    
    def test_workflow(self, prompt: str, steps: int = 20, resolution: int = 1024) -> Dict:
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
                    "width": resolution,
                    "height": resolution,
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
        
        print(f"🎨 Testing: '{prompt[:50]}...' ({steps} steps, {resolution}x{resolution})")
        start_time = time.time()
        
        try:
            # Send workflow
            response = requests.post(
                f"{self.base_url}/prompt",
                json={"prompt": workflow},
                timeout=300
            )
            
            if response.status_code != 200:
                return {"error": f"Failed to submit: {response.status_code}"}
            
            prompt_id = response.json()["prompt_id"]
            print(f"   Submitted with ID: {prompt_id}")
            
            # Monitor completion
            while True:
                history_response = requests.get(f"{self.base_url}/history/{prompt_id}")
                if history_response.status_code == 200:
                    history = history_response.json()
                    if prompt_id in history:
                        # Check if completed
                        if "outputs" in history[prompt_id]:
                            break
                time.sleep(0.5)
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Get image filename
            outputs = history[prompt_id].get("outputs", {})
            filename = None
            if "9" in outputs and "images" in outputs["9"]:
                filename = outputs["9"]["images"][0]["filename"]
            
            result = {
                "prompt": prompt,
                "steps": steps,
                "resolution": f"{resolution}x{resolution}",
                "duration": duration,
                "timestamp": datetime.datetime.now().isoformat(),
                "prompt_id": prompt_id,
                "filename": filename,
                "status": "success"
            }
            
            self.results.append(result)
            print(f"✅ Completed in {duration:.1f}s - {filename}")
            return result
            
        except Exception as e:
            error_result = {
                "prompt": prompt,
                "steps": steps,
                "resolution": f"{resolution}x{resolution}",
                "duration": 0,
                "timestamp": datetime.datetime.now().isoformat(),
                "error": str(e),
                "status": "failed"
            }
            self.results.append(error_result)
            print(f"❌ Failed: {e}")
            return error_result
    
    def run_quick_test(self):
        """Run a quick single test"""
        print("🚀 Running Quick AWS GPU Test")
        print("=" * 40)
        
        self.test_system_info()
        print()
        
        self.test_workflow(
            "a beautiful sunset over the ocean, photorealistic, high quality", 
            steps=15, 
            resolution=1024
        )
        
        self.generate_report()
    
    def run_benchmark_suite(self):
        """Run comprehensive benchmark tests"""
        
        test_cases = [
            ("a majestic dragon flying over mountains, fantasy art, detailed", 20, 1024),
            ("portrait of a wise old wizard, photorealistic, studio lighting", 25, 1024), 
            ("futuristic cityscape at night, cyberpunk, neon lights, 8k", 20, 1024),
            ("beautiful landscape with waterfalls, nature photography", 15, 512),
            ("abstract geometric patterns, colorful, digital art", 15, 512),
            ("cute cat sitting in garden, professional photography", 10, 768)
        ]
        
        print("🚀 Starting AWS GPU Comprehensive Benchmark")
        print("=" * 50)
        
        self.test_system_info()
        print()
        
        for i, (prompt, steps, resolution) in enumerate(test_cases, 1):
            print(f"\n[{i}/{len(test_cases)}]")
            self.test_workflow(prompt, steps, resolution)
            if i < len(test_cases):
                time.sleep(2)  # Brief pause between tests
        
        self.generate_report()
    
    def generate_report(self):
        """Generate performance report"""
        
        if not self.results:
            print("No results to report")
            return
        
        successful_results = [r for r in self.results if r.get("status") == "success"]
        
        if not successful_results:
            print("❌ No successful tests")
            return
        
        total_time = sum(r["duration"] for r in successful_results)
        avg_time = total_time / len(successful_results)
        
        print("\n📊 AWS GPU Performance Report")
        print("=" * 50)
        print(f"Total tests: {len(self.results)}")
        print(f"Successful: {len(successful_results)}")
        print(f"Failed: {len(self.results) - len(successful_results)}")
        print(f"Total generation time: {total_time:.1f}s")
        print(f"Average time per image: {avg_time:.1f}s")
        print(f"Images per minute: {60/avg_time:.1f}")
        
        # Cost estimation (g4dn.xlarge = $0.526/hour)
        cost_per_hour = 0.526
        cost_per_second = cost_per_hour / 3600
        estimated_cost = total_time * cost_per_second
        
        print(f"\n💰 Cost Analysis (g4dn.xlarge):")
        print(f"Generation time: {total_time/60:.1f} minutes")
        print(f"Hourly rate: ${cost_per_hour}")
        print(f"Estimated generation cost: ${estimated_cost:.4f}")
        print(f"Cost per successful image: ${estimated_cost/len(successful_results):.4f}")
        
        # Performance comparison
        if avg_time > 0:
            vs_m3_speedup = 90 / avg_time  # Assuming M3 Pro takes ~90s average
            print(f"\n⚡ Performance vs M3 Pro CPU:")
            print(f"Speed improvement: ~{vs_m3_speedup:.1f}x faster")
            print(f"Quality improvement: SDXL vs SD 1.5")
            print(f"Resolution improvement: 1024px vs 512px")
        
        # Save results
        timestamp = int(time.time())
        filename = f"aws_gpu_results_{timestamp}.json"
        
        report_data = {
            "metadata": {
                "test_date": datetime.datetime.now().isoformat(),
                "instance_type": "g4dn.xlarge",
                "base_url": self.base_url
            },
            "results": self.results,
            "summary": {
                "total_tests": len(self.results),
                "successful_tests": len(successful_results),
                "total_time": total_time,
                "avg_time": avg_time,
                "estimated_cost": estimated_cost,
                "cost_per_image": estimated_cost/len(successful_results) if successful_results else 0,
                "images_per_minute": 60/avg_time if avg_time > 0 else 0
            }
        }
        
        with open(filename, "w") as f:
            json.dump(report_data, f, indent=2)
        
        print(f"\n📁 Results saved to: {filename}")
        print(f"🌐 View images at: {self.base_url}/view?filename=IMAGE_NAME")

if __name__ == "__main__":
    import sys
    
    # Default to localhost, but allow override
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:7860"
    
    tester = ComfyUITester(url)
    
    # Check for test type
    test_type = sys.argv[2] if len(sys.argv) > 2 else "quick"
    
    if test_type == "full":
        tester.run_benchmark_suite()
    else:
        tester.run_quick_test()