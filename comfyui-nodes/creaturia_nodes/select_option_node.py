import os
import time
import io
import requests
import numpy as np
import torch
from PIL import Image
import folder_paths


class SelectMidjourneyOptionNode:
    """
    Selects one of the 4 quadrants (U1-U4) from a completed Midjourney
    imagine job by calling the Creaturia backend upscale endpoint, polling
    until the new job completes, and returning the upscaled IMAGE tensor.

    Flow:
      1. POST /v1/midjourney/upscale  body: { jobId, label: "U1".."U4" }
      2. GET  /v1/midjourney/jobs/:id → poll until status == "completed"
      3. Download image from storageUrl (S3) or imageUri (Discord CDN)
      4. Output IMAGE tensor + URL + new job id; save preview for UI
    """

    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("image", "image_url", "job_id")
    FUNCTION = "select"
    CATEGORY = "Creaturia"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "job_id": ("STRING", {"default": "", "forceInput": True}),
                "quadrant": (
                    "INT",
                    {"default": 1, "min": 1, "max": 4},
                ),
            },
            "optional": {
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

    def select(
        self,
        job_id,
        quadrant=1,
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

        if not job_id:
            raise ValueError("job_id is required")
        if quadrant not in (1, 2, 3, 4):
            raise ValueError(f"quadrant must be 1-4, got {quadrant}")

        label = f"U{quadrant}"

        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        # ── Step 1: Trigger upscale ──────────────────────────────────────
        payload = {"jobId": job_id, "label": label}
        url = f"{base_url}/v1/midjourney/upscale"
        print(f"[SelectMidjourneyOptionNode] POST {url}")
        print(f"[SelectMidjourneyOptionNode] Payload: {payload}")

        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        upscale_job = resp.json()
        upscale_job_id = upscale_job["_id"]
        print(
            f"[SelectMidjourneyOptionNode] Upscale job: {upscale_job_id} "
            f"(status: {upscale_job.get('status')})"
        )

        # ── Step 2: Poll for completion ──────────────────────────────────
        elapsed = 0
        image_url = None

        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval

            poll_resp = requests.get(
                f"{base_url}/v1/midjourney/jobs/{upscale_job_id}",
                headers=headers,
                timeout=30,
            )
            poll_resp.raise_for_status()
            upscale_job = poll_resp.json()

            status = upscale_job.get("status", "")
            progress = upscale_job.get("progress", "")
            print(
                f"[SelectMidjourneyOptionNode] Poll {elapsed}s/{max_wait}s — "
                f"status: {status}, progress: {progress}"
            )

            if status == "completed":
                image_url = upscale_job.get("storageUrl") or upscale_job.get("imageUri")
                if not image_url:
                    raise RuntimeError(
                        f"Upscale job {upscale_job_id} completed but no image URL found"
                    )
                print(f"[SelectMidjourneyOptionNode] Completed! URL: {image_url}")
                break

            if status == "failed":
                error = upscale_job.get("error", "unknown error")
                raise RuntimeError(
                    f"Upscale job {upscale_job_id} failed: {error}"
                )

        if image_url is None:
            raise TimeoutError(
                f"Upscale job {upscale_job_id} did not complete within {max_wait}s"
            )

        # ── Step 3: Download image ───────────────────────────────────────
        print(f"[SelectMidjourneyOptionNode] Downloading: {image_url}")
        img_resp = requests.get(image_url, timeout=120)
        img_resp.raise_for_status()

        pil_image = Image.open(io.BytesIO(img_resp.content)).convert("RGB")
        print(
            f"[SelectMidjourneyOptionNode] Image size: "
            f"{pil_image.size[0]}x{pil_image.size[1]}"
        )

        np_image = np.array(pil_image).astype(np.float32) / 255.0
        tensor = torch.from_numpy(np_image).unsqueeze(0)

        # ── Step 4: Save preview for ComfyUI UI ─────────────────────────
        preview_result = self._save_preview(pil_image)

        return {
            "ui": preview_result,
            "result": (tensor, image_url, str(upscale_job_id)),
        }

    @staticmethod
    def _save_preview(pil_image):
        output_dir = folder_paths.get_temp_directory()
        os.makedirs(output_dir, exist_ok=True)

        filename = f"creaturia_select_{int(time.time())}.png"
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
