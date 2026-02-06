from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class ActionState:
    """单位或建筑的行动状态"""
    Movable: bool = False             # 本回合是否还能移动
    Attackable: bool = False          # 本回合是否还能攻击
    MovingPoints: int = 0              # 剩余移动点数

@dataclass
class GameObject:
    """所有游戏实体的基类"""
    uid: int # 每个实例的唯一ID
    owner_id: int # 0=Neutral, 1=Player1, 2=Player2...
    hp : int = 0 # 当前生命值
    x: int = 0 # 地图上的X坐标
    y: int = 0 # 地图上的Y坐标
    prev_x: int = 0 # 回合开始时的X坐标
    prev_y: int = 0 # 回合开始时的Y坐标
    skills: Dict[str, Any] = field(default_factory = dict) # 技能实例
    buffs: Dict[str, Any] = field(default_factory = dict) # 临时属性增益/减益
    vars: Dict[str, Any] = field(default_factory = dict)  # 临时变量存储

    @property
    def pos(self):
        return (self.x, self.y)
    
    @property # 虚函数接口: 可被操作的
    def operable(self) -> bool:
        pass

class Unit(GameObject):
    """兵种单位"""
    def __init__ (self, uid: int, owner_id: int, config_data: Dict[str, Any], promoted: bool = False):
        super().__init__(uid,  owner_id)
        # 基础属性 (从JSON加载)
        self._data = config_data
        """
        stats 示例:
        {
            "Name": "小土豆",
            "Char": "豆",
            "Normal": {
                "Attack": 4,
                "AttackRange": {
                    "Type": "+",
                    "Min": 1,
                    "Max": 1
                },
                "MaxHP": 7,
                "MoveRange": {
                    "Type": "*",
                    "Min": 1,
                    "Max": 2
                }
            },
            "Promoted": {
                "Attack": 6,
                "AttackRange": {
                    "Type": "+",
                    "Min": 1,
                    "Max": 1
                },
                "MaxHP": 10,
                "MoveRange": {
                    "Type": "*",
                    "Min": 1,
                    "Max": 2
                }
            },
            "Cost": {
                "Gold": 130,
                "Wood": 3
            },
            "Description": "脆皮：受伤+1",
            "Skills": {
                "脆皮": {
                    "Type": "PassiveSkill",
                    "Trigger": "CALC_DAMAGE",
                    "Effect": "Crispy",
                    "Role": "TARGET"
                }
            }
        },
        """
        self.promoted: bool = promoted  # 是否晋升过
        self.hp : int = self._s.get("MaxHP", 1)  # 当前生命值
        # 行动状态管理
        self.action_state : ActionState = ActionState()
        @property
        def _p(self)->str:
            return "Promoted" if self.promoted else "Normal"
        @property
        def _s(self)->Dict[str, Any]:
            return self._data.get(self._p, {})
        @property
        def name(self) -> str:
            return self._data.get("Name", "Unknown Name")
        @property
        def char(self) -> str:
            return self._data.get("Char", "?")
        @property
        def attack(self) -> int:
            return self._s.get("Attack", 0)
        @property
        def attack_range(self) -> Dict[str, Any]:
            return self._s.get("AttackRange", {"Type": "+", "Min": 1, "Max": 1})
        @property
        def max_hp(self) -> int:
            return self._s.get("MaxHP", 1)
        @property
        def move_range(self) -> Dict[str, Any]:
            return self._s.get("MoveRange", {"Type": "*", "Min": 1, "Max": 1})
        @property
        def cost(self) -> Dict[str, Dict[str, int]]:
            return self._data.get("Cost", {"Gold": 0, "Wood": 0})
        @property
        def operable(self) -> bool:
            if self.action_state.Movable or self.action_state.Attackable:
                return True
            for skill_name, skill_info in self.skills.items():
                if skill_info.get("Type") == "ActiveSkill":
                    if self.vars.get(skill_name, {}).get("Value", 0) > 0:
                        return True
            return False
        @property
        def attackable(self) -> bool: # 是否可以攻击
            # self.attackble 和 self.action_state.Attackable 的区别为: 前者说的是这个实体本身具不具备攻击能力, 后者说的是这个实体本回合还能不能攻击
            return self._s.get("Attackable", True)

class Building(GameObject):
    """建筑物"""
    def __init__ (self, uid: int, owner_id: int, stats: Dict[str, Any], vertical: bool = False):
        super().__init__(uid,  owner_id)
        # 基础属性 (从JSON加载)
        self.basic_stats = stats
        """
        stats 示例:
        "导弹井":{
            "Name": "导弹井",
            "Char": "导",
            "HP": 10,
            "Size": {
                "Width": 2,
                "Height": 2
            },
            "Attackable": false,
            "Cost":{
                "Gold": 650,
                "Wood": 45
            },
            "Skills":{
                "导弹攻击":{
                    "Type":"ActiveSkill",
                    "Effect":"MissileAttack",
                    "Cost":{
                        "Gold":500,
                        "Wood":30
                    }
                }
            },
            "Description":"对一格造成30真实伤害，并对此格周围八格造成10溅射真实伤害(可以空打) (不分敌我，自己也受)"
        },
        "炮台":{
            "Name": "炮台",
            "Char": "炮",
            "HP": 15,
            "Size": {
                "Width": 2,
                "Height": 2
            },
            "Attackable": true,
            "Attack": 7,
            "AttackRange": {
                "Type": "*",
                "Min": 1,
                "Max": 3
            },
            "Cost":{
                "Gold": 350,
                "Wood": 25
            }
        },
        """
        self.hp = stats["MaxHP"]
        self.vertical : bool = vertical  # 建筑物朝向，false=水平，true=垂直
        self.action_state : ActionState = ActionState()
        @property
        def name(self) -> str:
            return self.basic_stats.get("Name", "Unknown Building")
        @property
        def char(self) -> str:
            return self.basic_stats.get("Char", "?")
        @property
        def size(self) -> Dict[str, int]:
            return self.basic_stats.get("Size", {"Width": 1, "Height": 1})
        @property
        def attackable(self) -> bool:
            return self.basic_stats.get("Attackable", False)
        @property
        def attack(self) -> int:
            return self.basic_stats.get("Attack", 0)
        @property
        def attack_range(self) -> Dict[str, Any]:
            return self.basic_stats.get("AttackRange", {"Type": "+", "Min": 1, "Max": 1})
        @property
        def cost(self) -> Dict[str, Dict[str, int]]:
            return self.basic_stats.get("Cost", {"Gold": 0, "Wood": 0})
        @property
        def operable(self) -> bool:
            if self.action_state["Attackable"] and self.attackable:
                return True
            for skill_name, skill_info in self.skills.items():
                if skill_info.get("Type") == "ActiveSkill":
                    if self.vars.get(skill_name, {}).get("Value", 0) > 0:
                        return True
            return False
            