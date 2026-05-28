from .show_text_node import CreaturiaShowTextNode
from .generate_image_node import GenerateImageNode
from .select_option_node import SelectMidjourneyOptionNode

NODE_CLASS_MAPPINGS = {
    "CreaturiaShowTextNode": CreaturiaShowTextNode,
    "GenerateImageNode": GenerateImageNode,
    "SelectMidjourneyOptionNode": SelectMidjourneyOptionNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CreaturiaShowTextNode": "Creaturia - Show Text",
    "GenerateImageNode": "Creaturia - Generate Image",
    "SelectMidjourneyOptionNode": "Creaturia - Select Midjourney Option",
}
