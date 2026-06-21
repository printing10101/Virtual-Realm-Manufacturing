"""灵境制造 - 产品轨与研究轨的桥接层。

设计原则：
- 产品轨代码（python/app/**）禁止 import research/** 下的研究模块
- 产品轨通过 research_bridge 提供的稳定 API 与研究模块通信
- 研究模块不直接修改产品数据，只能通过桥接层的 API 反馈
- 桥接层是产品与研究之间的唯一通道
"""
from .feature_flags import (
    ResearchFeature,
    ROLLOUT_CONFIG,
    is_feature_enabled,
    get_rollout_config,
    register_feature,
)
from .data_collector import UsageDataCollector
from .data_anonymizer import DataAnonymizer
from .experiment_runner import ExperimentRunner
from .research_api_client import ResearchApiClient
from .feedback_to_research import FeedbackToResearch
from .problem_intake import ProblemIntake
from .shadow_runner import ShadowRunner

__all__ = [
    "ResearchFeature",
    "ROLLOUT_CONFIG",
    "is_feature_enabled",
    "get_rollout_config",
    "register_feature",
    "UsageDataCollector",
    "DataAnonymizer",
    "ExperimentRunner",
    "ResearchApiClient",
    "FeedbackToResearch",
    "ProblemIntake",
    "ShadowRunner",
]
