import os
import time
import io
import requests
import numpy as np
from PIL import Image
import folder_paths


class GenerateImageNode:
    """
    Calls the Creaturia backend Midjourney API to generate an image,
    polls until the job completes, downloads the result, and outputs it
    as an IMAGE tensor for downstream ComfyUI processing.

    Flow:
      1. POST /v1/midjourney/imagine  → creates a Midjourney job
      2. GET  /v1/midjourney/jobs/:id → poll until status == "completed"
      3. Download image from storageUrl (S3) or imageUri (Discord CDN)
      4. Output as IMAGE tensor + save preview for ComfyUI UI
    """

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "image_url")
    FUNCTION = "generate"
    CATEGORY = "Creaturia"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"default": "", "multiline": True}),
            },
            "optional": {
                "character_id": ("STRING", {"default": ""}),
                "api_base_url": ("STRING", {"default": ""}),
                "api_token": ("STRING", {"default": ""}),
                "poll_interval": (
                    "INT",
                    {"default": 10, "min": 2, "max": 60},
                ),
                "max_wait": (
                    "INT",
                    {"default": 600, "min": 30, "max": 1800},
                ),
            },
        }

    def generate(
        self,
        prompt,
        character_id="",
        api_base_url="",
        api_token="",
        poll_interval=10,
        max_wait=600,
    ):
        base_url = (
            api_base_url
            or os.environ.get("CREATURIA_API_URL", "http://host.docker.internal:3000")
        ).rstrip("/")
        token = api_token or os.environ.get("CREATURIA_API_TOKEN", "")

        if not prompt:
            raise ValueError("prompt is required")

        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        # ── Step 1: Trigger Midjourney generation ────────────────────────
        payload = {"prompt": prompt}
        if character_id:
            payload["characterId"] = character_id

        url = f"{base_url}/v1/midjourney/imagine"
        print(f"[GenerateImageNode] POST {url}")
        print(f"[GenerateImageNode] Payload: {payload}")

        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        job = resp.json()
        job_id = job["_id"]
        print(f"[GenerateImageNode] Job created: {job_id} (status: {job.get('status')})")

        # ── Step 2: Poll for completion ──────────────────────────────────
        elapsed = 0
        image_url = None

        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval

            poll_resp = requests.get(
                f"{base_url}/v1/midjourney/jobs/{job_id}",
                headers=headers,
                timeout=30,
            )
            poll_resp.raise_for_status()
            job = poll_resp.json()

            status = job.get("status", "")
            progress = job.get("progress", "")
            print(
                f"[GenerateImageNode] Poll {elapsed}s/{max_wait}s — "
                f"status: {status}, progress: {progress}"
            )

            if status == "completed":
                # Prefer permanent S3 URL, fall back to Discord CDN
                image_url = job.get("storageUrl") or job.get("imageUri")
                if not image_url:
                    raise RuntimeError(
                        f"Job {job_id} completed but no image URL found"
                    )
                print(f"[GenerateImageNode] Completed! URL: {image_url}")
                break

            if status == "failed":
                error = job.get("error", "unknown error")
                raise RuntimeError(f"Midjourney job {job_id} failed: {error}")

        if image_url is None:
            raise TimeoutError(
                f"Midjourney job {job_id} did not complete within {max_wait}s"
            )

        # ── Step 3: Download image ───────────────────────────────────────
        print(f"[GenerateImageNode] Downloading: {image_url}")
        img_resp = requests.get(image_url, timeout=120)
        img_resp.raise_for_status()

        pil_image = Image.open(io.BytesIO(img_resp.content)).convert("RGB")
        print(f"[GenerateImageNode] Image size: {pil_image.size[0]}x{pil_image.size[1]}")

        # Convert to ComfyUI IMAGE tensor: (batch, H, W, C) float32 0-1
        np_image = np.array(pil_image).astype(np.float32) / 255.0
        tensor = np_image[np.newaxis, :, :, :]

        # ── Step 4: Save preview for ComfyUI UI ─────────────────────────
        preview_result = self._save_preview(pil_image)

        return {
            "ui": preview_result,
            "result": (tensor, image_url),
        }

    @staticmethod
    def _save_preview(pil_image):
        """Save a temp PNG so the ComfyUI UI can display a preview."""
        output_dir = folder_paths.get_temp_directory()
        os.makedirs(output_dir, exist_ok=True)

        filename = f"creaturia_preview_{int(time.time())}.png"
        filepath = os.path.join(output_dir, filename)
        pil_image.save(filepath, format="PNG")

        return {
            "images": [
                {
                    "filename": filename,
                    "subfolder": "",
                    "type": "temp",
                }
            ]
        }
