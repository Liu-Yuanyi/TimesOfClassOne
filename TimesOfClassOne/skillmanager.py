from typing import TYPE_CHECKING, List, Callable
from .event import Trigger, Context
from .skills import SKILL_REGISTRY
import inspect

if TYPE_CHECKING:
    from .engine import GameEngine

class SkillManager:
    """
    负责管理技能的注册和触发。
    它将 skills.py 中定义的装饰器函数绑定到 EventBus。
    """
    def __init__(self, engine: "GameEngine"):
        self.engine = engine
        self._register_all_skills()

    def _register_all_skills(self):
        """
        遍历 SKILL_REGISTRY，将所有技能处理函数注册到 EventBus。
        """
        print(f"[SkillManager] Registering {len(SKILL_REGISTRY)} skills...")
        
        for skill_name, handlers in SKILL_REGISTRY.items():
            for trigger, func in handlers:
                # 我们注册原始函数 func
                # 注意：func 内部包含了具体的逻辑 (如检查 source 是否有该技能)
                # 但为了保险和性能，我们也可以在这里 wrap 一层通用的检查
                
                # 由于 skills.py 中的函数是针对 specific skill 的，
                # 但 EventBus 的 trigger 是全局的 (所有 ON_DEATH 都会触发所有 ON_DEATH handler)
                # 所以必须确保 handler 内部检查了 "Trigger Source/Target has this skill".
                # 我们在 skills.py 的实现中已经加上了这种检查。
                
                self.engine.event_bus.subscribe(trigger, func)

    # 如果有主动技能(Active Skills)，可以在这里提供查询接口
    def get_active_skills(self, unit) -> List[str]:
        """返回单位当前可用的主动技能列表"""
        # 简单过滤以 @ 结尾的技能名
        return [s for s in unit.skills if s.endswith("@")]