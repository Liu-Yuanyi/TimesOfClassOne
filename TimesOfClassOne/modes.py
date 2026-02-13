from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any, TYPE_CHECKING
from event import Trigger, Context

if TYPE_CHECKING:
    from engine import GameEngine

class GameOver(Exception):
    """当游戏结束时抛出此异常, 用于立即中断当前堆栈"""
    def __init__(self, winner_id: int, reason: str):
        self.winner_id = winner_id
        self.reason = reason
        super().__init__(f"Game Over! Winner: {winner_id}, Reason: {reason}")

class baseMode:

    def __init__(self, name: str):
        self.name = name
        self.engine: Optional['GameEngine'] = None

    def initialize(self, engine: 'GameEngine'):
        """初始化模式: 绑定事件监听器"""
        self.engine = engine
        # 子类需在此注册监听器, 例如:
        # engine.event_bus.subscribe(Trigger.ON_DEATH, self.check_victory_on_death)

    def get_player_count(self) -> int:
        raise NotImplementedError

    def check_victory(self, game_state: Dict) -> int:
        """
        [已弃用] 用于轮询检查胜利条件. 
        推荐使用 initialize 注册事件监听器并抛出 GameOver 异常来实现即时胜利判定.
        """
        raise NotImplementedError
    
    # 第i号玩家需要选择几个法术/兵种/建筑
    def get_selection_counts(self, player_index: int) -> Dict[str, int]:
        raise NotImplementedError
    
    # 第i号玩家禁用的法术/兵种/建筑列表
    def get_banned_list(self, player_index: int) -> Dict[str, List[str]]:
        raise NotImplementedError
    
    # 第i号玩家强制使用的法术/兵种/建筑列表
    def get_forced_list(self, player_index: int) -> Dict[str, List[str]]:
        raise NotImplementedError
    
    # 第i号玩家的法术/兵种/建筑的特殊标签: 

    def get_special_tags(self, player_index: int) -> Dict[str, Dict[str, int]]:
        raise NotImplementedError

    def get_initial_resources(self, player_index: int) -> Dict[str, int]:
        raise NotImplementedError
    
    # 模式自带的特殊技能
    def get_special_abilities(self) -> List[Dict[str, Any]]:
        raise NotImplementedError
    
class ClassicMode(baseMode):

    def __init__(self):
        super().__init__("Classic")

    def get_player_count(self) -> int:
        return 2

    def initialize(self, engine: 'GameEngine'):
        super().initialize(engine)
        # 监听死亡事件，即时判定胜负
        engine.event_bus.subscribe(Trigger.ON_DEATH, self.on_entity_death,100)

    def on_entity_death(self, ctx: Context):
        """当实体死亡时触发"""
        dead_entity = ctx.source
        if not dead_entity:
            return
        # 检查是否是基地
        if "基地" == dead_entity.name:
            # 获取死亡实体所属玩家
            owner_id = dead_entity.owner_id
            # 另一个玩家获胜
            winner_id = 1 if owner_id == 2 else 2
            raise GameOver(winner_id, reason="Base Destroyed")

    def check_victory(self, game_state: Dict) -> int:
        # 保留旧接口或者直接 pass
        return 0
    
    def get_selection_counts(self, player_index: int) -> Dict[str, int]:
        return {"units": 8, "buildings": 5, "spells": 1}
    
    def get_banned_list(self, player_index: int) -> Dict[str, List[str]]:
        return {"units": [], "buildings": [], "spells": []}
    
    def get_forced_list(self, player_index: int) -> Dict[str, List[str]]:
        return {"units": [], "buildings": ["兵营", "金矿", "伐木场"], "spells": []}
    
    def get_special_tags(self, player_index: int) -> Dict[str, Dict[str, int]]:
        return {"units": {}, "buildings": {"优势":2}, "spells": {}}
    
    def get_initial_resources(self, player_index: int) -> Dict[str, int]:
        if player_index == 1:
            return {"Gold": 0, "Wood": 0}
        return {"Gold": 180, "Wood": 6}

    def get_special_abilities(self) -> List[Dict[str, Any]]:
        return []