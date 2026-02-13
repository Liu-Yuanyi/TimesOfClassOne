from typing import Optional, List, Any, Dict
# 这里为了避免循环引用，使用 TYPE_CHECKING
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from engine import GameEngine

from engine import UIRequest

# --- 通用交互辅助函数 ---
# 这些函数只是对 engine.request_input 的包装，方便技能编写者使用。

async def ask_confirm(engine: "GameEngine", player_id: int, message: str) -> bool:
    """
    通用询问: 是/否
    返回 True 表示玩家选择了 Yes
    """
    # 构造唯一 request_id (简单起见)
    req_uid = getattr(engine, "_next_uid", 0) 
    
    resp = await engine.request_input(UIRequest(
        request_id=f"conf_{engine.turn_count}_{req_uid}",
        player_id=player_id,
        type="CONFIRMATION",
        message=message,
        validation={"options": ["yes", "no"]}
    ))
    return resp.get("choice") == "yes"

async def select_location(engine: "GameEngine", player_id: int, valid_positions: List[tuple], message: str = "请选择位置") -> Optional[tuple]:
    """
    通用询问: 选择地图格子
    """
    req_uid = getattr(engine, "_next_uid", 0) 

    resp = await engine.request_input(UIRequest(
        request_id=f"loc_{engine.turn_count}_{req_uid}",
        player_id=player_id,
        type="SELECT_LOCATION",
        message=message,
        validation={"valid_positions": valid_positions},
        allow_cancel=True
    ))
    
    if resp.get("action") == "cancel":
        return None
        
    pos = resp.get("position") # 假设返回 [x, y]
    return tuple(pos) if pos else None

async def select_unit_type(engine: "GameEngine", player_id: int, available_types: List[str], message: str = "请选择兵种") -> Optional[str]:
    """
    通用询问: 从左侧兵种列表中选择一个
    """
    req_uid = getattr(engine, "_next_uid", 0) 

    resp = await engine.request_input(UIRequest(
        request_id=f"type_{engine.turn_count}_{req_uid}",
        player_id=player_id,
        type="SELECT_UNIT_TYPE",
        message=message,
        validation={"options": available_types},
        allow_cancel=True
    ))
    
    if resp.get("action") == "cancel":
        return None
    return resp.get("selection")

async def select_direction(engine: "GameEngine", player_id: int, message: str = "请选择方向") -> Optional[tuple]:
    """
    通用询问: 选择方向 (上下左右)
    """
    req_uid = getattr(engine, "_next_uid", 0) 
    
    resp = await engine.request_input(UIRequest(
        request_id=f"dir_{engine.turn_count}_{req_uid}",
        player_id=player_id,
        type="SELECT_DIRECTION",
        message=message,
        allow_cancel=True
    ))
    if resp.get("action") == "cancel":
        return None
    # 假设返回的是 (dx, dy)
    return tuple(resp.get("direction")) if resp.get("direction") else None
