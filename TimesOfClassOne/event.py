from enum import Enum, auto
from typing import List, Dict, Any, Callable
from inspect import iscoroutinefunction

class Trigger(Enum):
    """
    事件触发器类型枚举。
    定义了游戏生命周期中所有可拦截的关键节点。
    """
    # --- 属性计算类 (Modifiers) ---
    CALC_ATTACK = "CALC_ATTACK"                 # 计算攻击力时
    CALC_ATTACK_RANGE = "CALC_ATTACK_RANGE"     # 计算攻击范围时
    CALC_ATTACK_TARGET = "CALC_ATTACK_TARGET"   # 计算可攻击目标时
    CALC_MOVE_RANGE = "CALC_MOVE_RANGE"         # 计算移动范围时
    CALC_DAMAGE = "CALC_DAMAGE"                 # 计算受到的伤害 (减伤, 护甲)
    CALC_COST = "CALC_COST"                     # 计算价格
    CALC_HEAL = "CALC_HEAL"                     # 计算治疗量

    # --- 流程事件类 (Flow Events) ---
    ON_GAME_START = "ON_GAME_START"      # 游戏开始
    ON_TURN_START = "ON_TURN_START"      # 回合开始
    ON_INPUT_REQUEST = "ON_INPUT_REQUEST" # 请求输入时
    ON_TURN_END = "ON_TURN_END"        # 回合结束
    
    # --- 动作前后钩子 (Action Hooks) ---
    ON_SPAWN = "ON_SPAWN"          # 单位生成时
    ON_BUILD = "ON_BUILD"          # 建筑建造时

    BEFORE_MOVE = "BEFORE_MOVE"        # 移动指令执行前
    ON_MOVE = "ON_MOVE"            # 移动完成后
    
    BEFORE_ATTACK = "BEFORE_ATTACK"      # 攻击前 (如: 检查是否可以攻击)
    ON_ATTACK = "ON_ATTACK"          # 攻击结算后 (如: 溅射, 位移)
    ON_DAMAGE_TAKEN = "ON_DAMAGE_TAKEN"    # 受到伤害时 (如: 反伤)
    
    ON_KILL = "ON_KILL"            # 击杀实体时 (如: 连击, 晋升)
    ON_DEATH = "ON_DEATH"           # 实体死亡时 (如: 亡语)
    
    ON_HEAL = "ON_HEAL"            # 治疗时
    ON_PROMOTE = "ON_PROMOTE"         # 单位晋升时


class Context:
    """
    事件上下文对象。
    在事件传播过程中携带所有必要的数据，可以在Handler通过修改该对象
    来影响后续的计算结果 (如修改 value 值)。
    """
    def __init__(self, engine, source=None, target=None, value=0, **kwargs):
        self.engine = engine  # 这里的 engine 就是 Engine 实例
        self.source = source  # 触发事件的主体 (Attacker)
        self.target = target  # 事件的目标 (Defender/Target Pos)
        self.value = value    # 传递的数值 (如伤害值, 治疗量, 属性值)
        self.data = kwargs    # 额外的元数据 (如 'skill_name', 'hit_pos')
        self.is_stopped = False


class EventBus:
    """
    简单的同步事件总线。
    负责管理监听器并在特定时机触发事件。
    """
    def __init__(self):
        # 监听器字典: Trigger -> List[Callable]
        self._listeners: Dict[Trigger, List[Callable]] = {t: [] for t in Trigger}

    def subscribe(self, trigger: Trigger, handler: Callable, priority: int = 0):
        """
        订阅事件
        :param trigger: 触发时机
        :param handler: 处理函数 function(context)
        """
        self._listeners[trigger].append((handler, priority))
        self._listeners[trigger].sort(key=lambda x: x[1], reverse=True)
        
    def emit(self, trigger: Trigger, context: Context) -> Context:
        """
        触发同步事件 (用于数值计算, 不能包含 await)。
        """
        for handler, _ in self._listeners[trigger]:
            if iscoroutinefunction(handler):
                raise RuntimeError("Cannot call async handler in sync emit")
            handler(context)
            if context.is_stopped:
                break
        return context

    async def async_emit(self, trigger: Trigger, context: Context) -> Context:
        """
        触发异步事件 (用于游戏流程, 支持等待 UI 输入)。
        """
        for handler, _ in self._listeners[trigger]:
            if iscoroutinefunction(handler):
                await handler(context)
            else:
                handler(context)
            
            if context.is_stopped:
                break
        return context