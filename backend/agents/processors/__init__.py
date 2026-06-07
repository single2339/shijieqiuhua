"""Processing agents — pipeline steps that can be composed or called independently."""

from backend.agents.processors.bayesian_scoring import BayesianScoringAgent
from backend.agents.processors.classification import ClassificationAgent
from backend.agents.processors.location_extraction import LocationExtractionAgent
from backend.agents.processors.pipeline import CollectionPipelineAgent
from backend.agents.processors.summarization import SummarizationAgent
from backend.agents.processors.translation import TranslationAgent

__all__ = [
    "CollectionPipelineAgent",
    "BayesianScoringAgent",
    "ClassificationAgent",
    "LocationExtractionAgent",
    "SummarizationAgent",
    "TranslationAgent",
]
