"""Topic of the document: one of the categories in config/modules/category.yaml."""
from ...core.kits.label import LabelModule


class CategoryModule(LabelModule):
    name = "category"
    title = "Topic"
    description = "Main topic of the document, from a configurable taxonomy."
