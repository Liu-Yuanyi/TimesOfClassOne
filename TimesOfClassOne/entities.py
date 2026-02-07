from dataclasses import dataclass
from typing import List, Dict, Any, Optional

@dataclass
class ActionState:
    """单位或建筑的行动状态"""
    Movable: bool = False             # 本回合是否还能移动
    Attackable: bool = False          # 本回合是否还能攻击
    MovingPoints: int = 0              # 剩余移动点数

class GameObject:
    """所有游戏实体的基类"""
    # 预留接口供自动补全，具体实现由子类负责
    name: str
    movable: bool
    attackable: bool
    size: Dict[str, int]
    vertical: bool
    action_state: ActionState

    def __init__(self, uid: int, owner_id: int):
        self.uid = uid
        self.owner_id = owner_id
        self.hp: int = 0
        self.x: int = 0
        self.y: int = 0
        self.prev_x: int = 0
        self.prev_y: int = 0
        self.skills: Dict[str, Any] = {} # 技能实例
        self.buffs: Dict[str, Any] = {} # 临时属性增益/减益
        self.vars: Dict[str, Any] = {}  # 临时变量存储

    @property
    def pos(self):
        return (self.x, self.y)
    @pos.setter
    def pos(self, value):
        self.x, self.y = value

    @property
    def nowoperable(self) -> bool:
        """当前是否还能进行操作 (移动/攻击/使用技能)"""
        if self.action_state.Attackable and self.attackable:
            return True
        if self.action_state.Movable and self.movable:
            return True
        for skill_name, skill_info in self.skills.items():
            if skill_info.get("Type") == "ActiveSkill":
                if self.vars.get(skill_name, {}).get("Value", 0) > 0:
                    return True
        return False
    @property
    def nowmovable(self) -> bool:
        """当前是否还能移动"""
        return self.action_state.Movable and self.movable
    @property
    def nowattackable(self) -> bool:
        """当前是否还能攻击"""
        return self.action_state.Attackable and self.attackable
    @property
    def nowskillable(self) -> bool:
        """当前是否还能使用技能"""
        for skill_name, skill_info in self.skills.items():
            if skill_info.get("Type") == "ActiveSkill":
                if self.vars.get(skill_name, {}).get("Value", 0) > 0:
                    return True
    # name @property removed as requested

        raise NotImplementedError

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

        self.vertical : bool = False  # 兵种没有朝向，但为了统一接口，预留这个属性
        self.size = {"Width": 1, "Height": 1}  # 兵种默认大小为1x1

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
    def attackable(self) -> bool: # 是否可以攻击
        # self.attackble 和 self.action_state.Attackable 的区别为: 前者说的是这个实体本身具不具备攻击能力, 后者说的是这个实体本回合还能不能攻击
        return self._s.get("Attackable", True)
    @property
    def movable(self) -> bool: # 是否可以移动
        return self._s.get("Movable", True)

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
    def movable(self) -> bool:
        return False  # 建筑物不可移动
    @property
    def attack(self) -> int:
        return self.basic_stats.get("Attack", 0)
    @property
    def attack_range(self) -> Dict[str, Any]:
        return self.basic_stats.get("AttackRange", {"Type": "+", "Min": 1, "Max": 1})
    @property
    def cost(self) -> Dict[str, Dict[str, int]]:
        return self.basic_stats.get("Cost", {"Gold": 0, "Wood": 0})