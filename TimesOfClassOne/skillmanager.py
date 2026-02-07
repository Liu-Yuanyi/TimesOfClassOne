from typing import TYPE_CHECKING, List, Callable
from .event import Trigger, Context
from .skills import SKILL_REGISTRY
import inspect
from .entities import GameObject, Unit, Building
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
    
    def skill_trigger(self, trigger: Trigger, ctx: Context):
        """遍历所有技能和buff, 找到对应触发器的技能并执行"""
        L = self._collect_skills_and_buffs(trigger, ctx)
        
        # 依次执行
        for _, _, _, func in L:
            if inspect.iscoroutinefunction(func):
                raise RuntimeError("Cannot call async skill in sync trigger")
            func(ctx)
            if ctx.is_stopped:
                break
    
    async def async_skill_trigger(self, trigger: Trigger, ctx: Context):
        """遍历所有技能, 找到对应触发器的技能并执行 (异步版本)"""
        L = self._collect_skills_and_buffs(trigger, ctx)

        # 依次执行
        for _, _, _, func in L:
            # 兼容同步和异步函数
            if inspect.iscoroutinefunction(func):
                await func(ctx)
            else:
                func(ctx)
            if ctx.is_stopped:
                break


    def _collect_skills_and_buffs(self, trigger: Trigger, ctx: Context) -> List:
        """核心逻辑提取: 收集并排序所有需要触发的技能/buff"""
        entities_to_check = []
        
        # 1. 收集来源
        for ent in self.engine.entities.values():
            entities_to_check.append((ent, "GLOBAL"))
        if isinstance(ctx.source, GameObject):
            entities_to_check.append((ctx.source, "SOURCE"))
        if isinstance(ctx.target, GameObject):
            entities_to_check.append((ctx.target, "TARGET"))

        L: List[(int, int, str, Callable)] = []

        # 2. 遍历收集
        for ent, role in entities_to_check:
            # 兼容有些对象可能没有 Skills/Buffs 属性（防Crash）
            skills = ent.skills
            buffs = ent.buffs
            
            for name, info in skills.items():
                self._collect_filter(L, trigger, role, ent, name, info)
            for name, info in buffs.items():
                self._collect_filter(L, trigger, role, ent, name, info)

        # 3. 排序 (Priority降序 -> UID升序 -> Name升序)
        L.sort(key=lambda x: (-x[0], x[1], x[2]))
        return L

    def _collect_filter(self, result_list: list, trigger: Trigger, role: str, ent, name: str, info: dict):
        """辅助函数：过滤并收集"""
        if info.get("Type") not in ("PassiveSkill", "Buff"): return
        if info.get("Trigger") != trigger: return
        if info.get("Role") != role: return

        func_name = info.get("Effect")
        func = self.loader.funcdict.get(func_name)
        if func is None:
            # 可以选择 log warning 而不是 crash
            print(f"[Warning] Function {func_name} not found for {name}")
            return
            
        priority = info.get("Priority", 0)
        result_list.append((priority, ent.uid, name, func))