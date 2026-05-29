from .show_text_node import CreaturiaShowTextNode
from .generate_image_node import GenerateImageNode
from .select_option_node import SelectMidjourneyOptionNode
from .tripo_3d_node import CreaturiaTripoImageToModelNode

NODE_CLASS_MAPPINGS = {
    "CreaturiaShowTextNode": CreaturiaShowTextNode,
    "GenerateImageNode": GenerateImageNode,
    "SelectMidjourneyOptionNode": SelectMidjourneyOptionNode,
    "CreaturiaTripoImageToModelNode": CreaturiaTripoImageToModelNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CreaturiaShowTextNode": "Creaturia - Show Text",
    "GenerateImageNode": "Creaturia - Generate Image",
    "SelectMidjourneyOptionNode": "Creaturia - Select Midjourney Option",
    "CreaturiaTripoImageToModelNode": "Creaturia - Tripo Image to 3D",
}
