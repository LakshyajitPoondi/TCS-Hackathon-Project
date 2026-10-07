"""Loads and validates config/cause_categories.yaml (categories, subcauses, display names, rule weights).

Validation runs at import time, so the API and every CLI fail fast with a readable message when the file is
wrong. Rule *conditions* stay in engine/scoring.py; this file supplies their weights, the thresholds and texts.
Override the path with CAUSE_CONFIG_PATH (tests use this to check validation).
"""
import os
from pathlib import Path
from typing import Literal
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / 'config' / 'cause_categories.yaml'
# Fixed by code: the API schema's Category literal and the rule tables in engine/scoring.py.
SCHEMA_CATEGORIES = ('machine', 'material', 'method', 'measurement', 'people', 'environment')
RULE_KEYS = ('cooling', 'mechanical', 'material', 'method', 'people', 'measurement', 'environment')
MACHINE_SUBCAUSES = ('cooling', 'mechanical')


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Weights(Strict):
    strong: int = Field(gt=0)
    moderate: int = Field(gt=0)
    weak: int = Field(gt=0)
    note: int = Field(gt=0)
    health: int = Field(gt=0)
    contra_strong: int = Field(lt=0)
    contra: int = Field(lt=0)


class Thresholds(Strict):
    min_score: int = Field(gt=0)
    medium_score: int
    high_score: int
    max_hypotheses: int = Field(ge=1, le=3)

    @model_validator(mode='after')
    def _ordered(self):
        if not self.min_score <= self.medium_score <= self.high_score:
            raise ValueError('thresholds must satisfy min_score <= medium_score <= high_score')
        return self


class Category(Strict):
    key: Literal[SCHEMA_CATEGORIES]
    display_name: str = Field(min_length=1, max_length=60)


class Candidate(Strict):
    key: Literal[RULE_KEYS]
    category: Literal[SCHEMA_CATEGORIES]
    subcause: Literal[MACHINE_SUBCAUSES] | None = None
    label: str = Field(min_length=1, max_length=80)
    display_name: str = Field(min_length=1, max_length=80)
    verify_sentence: str = Field(min_length=1, max_length=400)
    missing_checks: list[str] = Field(min_length=1, max_length=6)

    @model_validator(mode='after')
    def _subcause(self):
        if (self.category == 'machine') != (self.subcause is not None):
            raise ValueError(f'{self.key}: a subcause is required for machine candidates and forbidden otherwise')
        return self


class CauseConfig(Strict):
    version: Literal[1]
    weights: Weights
    thresholds: Thresholds
    categories: list[Category]
    candidates: list[Candidate]

    @model_validator(mode='after')
    def _complete(self):
        cats = [c.key for c in self.categories]
        if sorted(cats) != sorted(SCHEMA_CATEGORIES) or len(set(cats)) != len(cats):
            raise ValueError('categories must list each of ' + ', '.join(SCHEMA_CATEGORIES) + ' exactly once')
        keys = [c.key for c in self.candidates]
        if sorted(keys) != sorted(RULE_KEYS) or len(set(keys)) != len(keys):
            raise ValueError('candidates must list each rule key exactly once: ' + ', '.join(RULE_KEYS))
        return self

    def category_names(self):
        return {c.key: c.display_name for c in self.categories}


class CauseConfigError(RuntimeError):
    pass


def load(path=None) -> CauseConfig:
    path = Path(path or os.getenv('CAUSE_CONFIG_PATH') or DEFAULT_PATH)
    try:
        raw = yaml.safe_load(path.read_text(encoding='utf-8'))
        return CauseConfig.model_validate(raw)
    except FileNotFoundError as exc:
        raise CauseConfigError(f'Cause config not found: {path}') from exc
    except (yaml.YAMLError, ValidationError) as exc:
        raise CauseConfigError(f'Invalid cause config {path}:\n{exc}') from exc


CONFIG = load()
