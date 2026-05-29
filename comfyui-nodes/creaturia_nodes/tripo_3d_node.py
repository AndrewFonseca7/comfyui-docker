import os
import time
import io
import requests
import numpy as np
from PIL import Image


class CreaturiaTripoImageToModelNode:
    """
    Sends an image to the Creaturia backend image-to-model endpoint, which
    drives Tripo3D's image_to_model task. Modular by design:

      * If `image_url` is provided, it's forwarded as-is (chains directly off
        SelectMidjourneyOptionNode or any node that produces a URL).
      * If only `image` (IMAGE tensor) is provided, the node POSTs the PNG to
        the backend's /v1/uploads endpoint to obtain a public S3 URL first.

    Flow:
      1. (If tensor only) POST /v1/uploads (multipart) → public image URL
      2. POST /v1/model-3d/image-to-model { imageUrl, prompt?, characterId? }
      3. GET  /v1/model-3d/:id → poll until status in (completed, failed)
      4. Output model_url (GLB), thumbnail_url, model_id
    """

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("model_url", "thumbnail_url", "model_id")
    FUNCTION = "generate"
    CATEGORY = "Creaturia"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": {
                "image": ("IMAGE",),
                "image_url": ("STRING", {"default": "", "forceInput": True}),
                "prompt": ("STRING", {"default": "", "multiline": True}),
                "character_id": ("STRING", {"default": ""}),
                "api_base_url": ("STRING", {"default": ""}),
                "api_token": ("STRING", {"default": ""}),
                "poll_interval": ("INT", {"default": 10, "min": 2, "max": 60}),
                "max_wait": ("INT", {"default": 1200, "min": 60, "max": 3600}),
            },
        }

    def generate(
        self,
        image=None,
        image_url="",
        prompt="",
        character_id="",
        api_base_url="",
        api_token="",
        poll_interval=10,
        max_wait=1200,
    ):
        base_url = (
            api_base_url
            or os.environ.get("CREATURIA_API_URL", "http://host.docker.internal:3000")
        ).rstrip("/")
        token = api_token or os.environ.get("CREATURIA_API_TOKEN", "")

        if not image_url and image is None:
            raise ValueError("Provide either `image` (IMAGE) or `image_url` (STRING)")

        headers_json = {"Content-Type": "application/json"}
        headers_auth = {}
        if token:
            headers_auth["Authorization"] = f"Bearer {token}"
        headers_json.update(headers_auth)

        # ── Step 1: If tensor was provided (and no URL), upload it ───────
        if not image_url:
            image_url = self._upload_tensor(image, base_url, headers_auth)
            print(f"[TripoImageToModelNode] Uploaded image: {image_url}")

        # ── Step 2: Kick off image-to-model ──────────────────────────────
        payload = {"imageUrl": image_url}
        if prompt:
            payload["prompt"] = prompt
        if character_id:
            payload["characterId"] = character_id

        url = f"{base_url}/v1/model-3d/image-to-model"
        print(f"[TripoImageToModelNode] POST {url}")
        print(f"[TripoImageToModelNode] Payload: {payload}")
        resp = requests.post(url, json=payload, headers=headers_json, timeout=60)
        resp.raise_for_status()
        doc = resp.json()
        model_id = doc.get("_id") or doc.get("id")
        if not model_id:
            raise RuntimeError(f"Backend did not return a model id: {doc}")
        print(f"[TripoImageToModelNode] Model3d doc: {model_id} (status: {doc.get('status')})")

        # ── Step 3: Poll until terminal state ────────────────────────────
        elapsed = 0
        final = None
        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval
            poll = requests.get(
                f"{base_url}/v1/model-3d/{model_id}",
                headers=headers_auth,
                timeout=30,
            )
            poll.raise_for_status()
            final = poll.json()
            status = final.get("status", "")
            progress = final.get("progress", 0)
            print(
                f"[TripoImageToModelNode] Poll {elapsed}s/{max_wait}s — "
                f"status: {status}, progress: {progress}%"
            )
            if status == "completed":
                break
            if status == "failed":
                raise RuntimeError(
                    f"Tripo job {model_id} failed: {final.get('error', 'unknown')}"
                )

        if not final or final.get("status") != "completed":
            raise TimeoutError(
                f"Model {model_id} did not complete within {max_wait}s"
            )

        model_url = final.get("modelUrl", "")
        thumb_url = final.get("thumbnailUrl", "")
        print(f"[TripoImageToModelNode] Completed! model={model_url} thumb={thumb_url}")

        return (model_url, thumb_url, str(model_id))

    # ──────────────────────────────────────────────────────────────────
    @staticmethod
    def _upload_tensor(image_tensor, base_url, headers_auth):
        """Save the first frame of an IMAGE batch as PNG and POST to /v1/uploads."""
        if hasattr(image_tensor, "cpu"):
            arr = image_tensor.cpu().numpy()
        else:
            arr = np.asarray(image_tensor)

        if arr.ndim == 4:
            arr = arr[0]
        arr = (np.clip(arr, 0.0, 1.0) * 255.0).astype(np.uint8)
        pil = Image.fromarray(arr)

        buf = io.BytesIO()
        pil.save(buf, format="PNG")
        buf.seek(0)

        files = {"file": (f"comfy_{int(time.time())}.png", buf, "image/png")}
        data = {"context": "comfyui-image", "makePublic": "true"}

        resp = requests.post(
            f"{base_url}/v1/uploads",
            files=files,
            data=data,
            headers=headers_auth,
            timeout=120,
        )
        resp.raise_for_status()
        body = resp.json()
        url = body.get("url")
        if not url:
            raise RuntimeError(f"Upload response missing url: {body}")
        return url
