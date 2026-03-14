class CreaturiaShowTextNode:
    """Displays a string value in the ComfyUI UI."""

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "show"
    CATEGORY = "Creaturia"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"forceInput": True}),
            },
        }

    def show(self, text):
        return {"ui": {"text": [text]}, "result": (text,)}
