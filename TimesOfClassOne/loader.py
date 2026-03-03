# 用于导入兵种和建筑的stats

from typing import Dict, Any
import json5
import os
import importlib

from entities import Unit, Building

def default_true(*args, **kwargs):
    return True

class loader:
    """负责加载文件, 并作为蓝图生成兵种和建筑实例"""
    """mode貌似不需要在这里加载, 直接在mode模块里写死就行了, 但是还是预留了接口, 方便以后扩展"""
    def __init__(self):
        self.unit_stats: Dict[str, Dict[str, Any]] = {}
        self.building_stats: Dict[str, Dict[str, Any]] = {}
        self.buff_stats: Dict[str, Dict[str, Any]] = {}
        self.mode_stats: Dict[str, Dict[str, Any]] = {}
        self.map_stats: Dict[str, Dict[str, Any]] = {}
        
        self.funcdict: Dict[str, Any] = {}

    def append_one(self, name:str, info:Dict[str, Any], stat_type: str, skill_module: str = "skills"):
        """加载一个东西, 并把effect注册到技能字典里, 这样方便直接用字符串调用技能"""
        """这个接口提供给append_stats使用, 也可以直接用来加载单个实体"""
        s : Dict[str, Any]
        if stat_type == "unit":
            self.unit_stats[name] = info
            s= info.get("Skills", {})
        elif stat_type == "building":
            self.building_stats[name] = info
            s= info.get("Skills", {})
        elif stat_type == "buff":
            self.buff_stats[name] = info
            s= {name: info}
        elif stat_type == "mode":
            self.mode_stats[name] = info
            s= {}
        elif stat_type == "map":
            self.map_stats[name] = info
            s= {}
        else:
            raise ValueError(f"Unknown stat type: {stat_type}")

        # 注册技能
        for skill_name, skill_info in s.items():
            if skill_info.get("Type") not in ["static","Static"]:  # 静态技能不需要注册
                if skill_name in self.funcdict:
                    print(f"[Loader] Warning: Skill {skill_name} already exists in funcdict. Overwriting.")
                try:
                    func = getattr(importlib.import_module(f"{skill_module}"), skill_info["Effect"])

                    self.funcdict[skill_info["Effect"]] = func
                    print(f"[Loader] Registered skill effect: {skill_info['Effect']} from {skill_name}")

                except (ImportError, AttributeError) as e:
                    print(f"[Loader] Error loading skill effect: {skill_info['Effect']} for skill {skill_name}. Error: {e}")

                
                # 所有主动技能都有一个默认的条件函数, 如果JSON里没有指定的话就用这个
                # 条件函数的名字(key)是这个Effect后面加上"_check", 例如 "ThankYou" 的条件函数就是 "ThankYou_check"
                if skill_info.get("Type") == "ActiveSkill":
                    check_func_name = skill_info["Effect"] + "_check"
                    if check_func_name in self.funcdict:
                        print(f"[Loader] Warning: Check function {check_func_name} already exists in funcdict. Overwriting.")
                    try:
                        check_func = getattr(importlib.import_module(f"{skill_module}"), check_func_name)
                        self.funcdict[check_func_name] = check_func
                        print(f"[Loader] Registered skill check function: {check_func_name} for skill {skill_name}")
                    except (ImportError, AttributeError) as e:
                        print(f"[Loader] No check function found for {check_func_name}. Using default_true. Error: {e}")
                        self.funcdict[check_func_name] = default_true
                
    def append_stats(self, filepath: str, stat_type: str):
        """加载指定类型的stats文件"""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Stats file not found: {filepath}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json5.load(f)
        
        if stat_type not in ["unit", "building", "buff", "mode", "map"]:
            raise ValueError(f"Unknown stat type: {stat_type}")
        for name, info in data.items():
            self.append_one(name, info, stat_type)
        
    def create_unit(self, name: str, uid: int, owner_id: int, promoted: bool=False) -> Unit:
        """根据名称创建Unit实例"""
        if name not in self.unit_stats:
            raise ValueError(f"Unit stats not found for: {name}")
        
        stats = self.unit_stats[name]
        u=Unit(uid, owner_id, stats, promoted)
        
        u.skills = stats.get("Skills", {})
        u.vars = stats.get("Variables", {}).copy()

        # 给每个主动技能增加每回合使用次数变量, 如果已有(比如使用次数可能不为1)则不覆盖
        for skill_name, skill_info in u.skills.items():
            if skill_info.get("Type") == "ActiveSkill":
                if skill_name not in u.vars:
                    u.vars[skill_name] = {
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

    def info(self , name:str) -> Dict[str, Any]:
        """获取某类实体的详细信息"""
        if name in self.unit_stats:
            return self.unit_stats[name]
        elif name in self.building_stats:
            return self.building_stats[name]
        elif name in self.buff_stats:
            return self.buff_stats[name]
        elif name in self.mode_stats:
            return self.mode_stats[name]
        elif name in self.map_stats:
            return self.map_stats[name]
        else:
            raise ValueError(f"Stats not found for: {name}")