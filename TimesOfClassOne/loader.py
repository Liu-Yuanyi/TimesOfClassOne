# 用于导入兵种和建筑的stats

from typing import Dict, Any
import json5
import os

from .entities import Unit, Building

class loader:
    """负责加载文件, 并作为蓝图生成兵种和建筑实例"""
    def __init__(self):
        self.unit_stats: Dict[str, Dict[str, Any]] = {}
        self.building_stats: Dict[str, Dict[str, Any]] = {}
        self.buff_stats: Dict[str, Dict[str, Any]] = {}
        self.mode_stats: Dict[str, Dict[str, Any]] = {}
        self.map_stats: Dict[str, Dict[str, Any]] = {}

    def append_stats(self, filepath: str, stat_type: str):
        """加载指定类型的stats文件"""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Stats file not found: {filepath}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json5.load(f)
        
        if stat_type == "unit":
            self.unit_stats.update(data)
        elif stat_type == "building":
            self.building_stats.update(data)
        elif stat_type == "buff":
            self.buff_stats.update(data)
        elif stat_type == "mode":
            self.mode_stats.update(data)
        elif stat_type == "map":
            self.map_stats.update(data)
        else:
            raise ValueError(f"Unknown stat type: {stat_type}")
        
    def create_unit(self, name: str, uid: int, owner_id: int, promoted: bool=False) -> Unit:
        """根据名称创建Unit实例"""
        if name not in self.unit_stats:
            raise ValueError(f"Unit stats not found for: {name}")
        
        stats = self.unit_stats[name]
        u=Unit(uid, owner_id, stats, promoted)
        
        u.skills = stats.get("Skills", {})
        u.vars = stats.get("Variables", {}).copy()

        # 给每个主动技能增加每回合使用次数变量, 如果已有(比如使用次数可能不为1)则不覆盖
        for skill_id, skill_info in u.skills.items():
            if skill_info.get("Type") == "ActiveSkill":
                if skill_id not in u.vars:
                    u.vars[skill_id] = {
                            "Type":"Turn",
                            "DefaultValue":1,
                            "Value":1
                        }

        return u
    
    def create_building(self, name: str, uid: int, owner_id: int, vertical: bool) -> Building:
        #raise NotImplementedError("Building creation not implemented yet.")
        """根据名称创建Building实例"""
        if name not in self.building_stats:
            raise ValueError(f"Building stats not found for: {name}")
        
        stats = self.building_stats[name]
        b=Building(uid, owner_id, stats, vertical)

        b.skills = stats.get("Skills", {})
        b.vars = stats.get("Variables", {}).copy()

        for skill_id, skill_info in b.skills.items():
            if skill_info.get("Type") == "ActiveSkill":
                if skill_id not in b.vars:
                    b.vars[skill_id] = {
                            "Type":"Turn",
                            "DefaultValue":1,
                            "Value":1
                        }

        return b
