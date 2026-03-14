from .show_text_node import CreaturiaShowTextNode
from .generate_image_node import GenerateImageNode

NODE_CLASS_MAPPINGS = {
    "CreaturiaShowTextNode": CreaturiaShowTextNode,
    "GenerateImageNode": GenerateImageNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CreaturiaShowTextNode": "Creaturia - Show Text",
    "GenerateImageNode": "Creaturia - Generate Image",
}
