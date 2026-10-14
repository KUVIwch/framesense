"""调色教学引擎：基于客观差异生成可解释的仿色指导。"""

from framesense.guidance.engine import generate_guidance
from framesense.guidance.models import GradingGuidance, GuidanceStep, Observation

__all__ = ["GradingGuidance", "GuidanceStep", "Observation", "generate_guidance"]
