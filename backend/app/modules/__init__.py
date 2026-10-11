"""The module catalog. Each package here is one self-contained capability.

To add a module: create `app/modules/<name>/` with a `Module` subclass, add a
`config/modules/<name>.yaml` (with `engine:` if it needs a model), and list the class
below. Order here is the UI order. A module is switched off by `enabled: false` in its
YAML (dependents must be off too). Which model runs it: `engine:` -> config/engines.yaml.
"""
from ..core.modules import Module
from .category import CategoryModule
from .entity_resolution import EntityResolutionModule
from .event import EventModule
from .event_coreference import EventCoreferenceModule
from .fields import FieldsModule
from .intent import IntentModule
from .language import LanguageModule
from .ner import NerModule
from .propaganda import PropagandaModule
from .relations import RelationsModule
from .relevance import RelevanceModule
from .risk import RiskModule
from .routing import RoutingModule
from .sentiment import SentimentModule
from .toxicity import ToxicityModule

CATALOG: list[type[Module]] = [
    LanguageModule,
    CategoryModule,
    RelevanceModule,
    RoutingModule,
    RiskModule,
    NerModule,
    EntityResolutionModule,
    RelationsModule,
    FieldsModule,
    EventModule,
    EventCoreferenceModule,
    SentimentModule,
    IntentModule,
    ToxicityModule,
    PropagandaModule,
]
