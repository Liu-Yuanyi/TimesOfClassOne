from typing import TYPE_CHECKING, List, Callable
from .event import Trigger, Context
from .skills import SKILL_REGISTRY
import inspect

if TYPE_CHECKING:
    from .engine import GameEngine

class SkillManager:
    """
    负责管理(被动)技能的触发, 
    engine会负责将其实例化, 并将这个类的方法绑定到事件总线上
    这样技能就能在游戏过程中响应各种事件
    """
    def __init__(self, engine: "GameEngine"):
        self.engine = engine
        self.loader = engine.loader
    
    def 