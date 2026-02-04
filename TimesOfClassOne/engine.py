from enum import Enum, auto
from typing import List, Dict, Any, Optional, Tuple, Callable
import asyncio
from dataclasses import dataclass, field
from json5 import load as json5_load

from .event import EventBus, Trigger, Context
from .entities import Unit, Building, GameObject
from .modes import baseMode 
from .loader import loader
from .maps import GameMap 
from .skillmanager import SkillManager

# --- UI 交互协议定义 ---

@dataclass
class UIRequest:
    """发送给 UI 层的请求包"""
    request_id: str
    player_id: int
    type: str
    message: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    validation: Dict[str, Any] = field(default_factory=dict)
    allow_cancel: bool = True
    presentation: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PlayerState:
    """玩家资源状态"""
    player_id: int
    _name: Optional[str] = None
    gold: int = 0
    wood: int = 0
    is_active: bool = False
    banned_units: List[str] = field(default_factory=list)
    chosen_units: List[str] = field(default_factory=list)
    banned_constructions: List[str] = field(default_factory=list)
    chosen_constructions: List[str] = field(default_factory=list)
    banned_spells: List[str] = field(default_factory=list)
    chosen_spells: List[str] = field(default_factory=list)
    spells_casts_left: Dict[int, int] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self._name if self._name else f"Player {self.player_id}"

# --- 游戏核心引擎 ---

class GameEngine:
    def __init__(self, mode: baseMode, PlayerStates: Dict[int, PlayerState], map_name: str="default_map", event_bus: Optional[EventBus]=None):
        # 核心组件
        self.event_bus = event_bus if event_bus is not None else EventBus()
        self.mode = mode
        self.game_map: GameMap # 假设有一个 GameMap 类
        
        # 游戏状态数据
        self.turn_count: int = 1
        self.current_player_id: int = 1 # 1=P1, 2=P2, etc
        self.players_num: int = mode.get_player_count()
        self.players: Dict[int, PlayerState] = PlayerStates
        self.player_vars: Dict[int, Dict[str, Any]] = {pid: {} for pid in PlayerStates.keys()}

        # 数据载入
        self.loader = loader()
        self.loader.append_stats("./stats/units.json5", "unit")
        self.loader.append_stats("./stats/buildings.json5", "building")
        self.loader.append_stats("./stats/buffs.json5", "buff")
        self.loader.append_stats("./stats/modes.json5", "mode")
        self.loader.append_stats("./stats/maps.json5", "map")
        
        # 实体管理
        self.entities: Dict[int, GameObject] = {}
        self._next_uid: int = 1000

        self._init_map_entities()
        
        # 交互状态管理
        self._current_request: Optional[UIRequest] = None
        self._input_future: Optional[asyncio.Future] = None
        self._running: bool = False
        self._request_listeners: List[Callable[[UIRequest], None]] = []
        self._player_input_mode: Dict[int, str] = {pid: "interactive" for pid in PlayerStates.keys()}

        # 初始化系统
        self._init_systems()

    def _init_map_entities(self):
        """从./map.json读取初始实体"""
        """map_stats 示例:
        {
            "Width": 20,
            "Height": 20,
            "Entities": [
                {"Type": "Building", "Name": "基地", "uid": 100, "owner_id":1, "x":1, "y":1},
                {"Type": "Building", "Name": "金矿", "uid": 101, "owner_id":1, "x":1, "y":3},
                {"Type": "Unit", "Name": "工兵", "uid": 150, "owner_id":1, "x":2, "y":3},
                {"Type": "Building", "Name": "基地", "uid": 200, "owner_id":2, "x":19, "y":19},
                {"Type": "Building", "Name": "金矿", "uid": 201, "owner_id":2, "x":20, "y":18},
                {"Type": "Unit", "Name": "工兵", "uid": 250, "owner_id":2, "x":19, "y":18},
                {"Type": "Building", "Name": "总矿", "uid": 300, "owner_id":0, "x":3, "y":17},
                {"Type": "Building", "Name": "总矿", "uid": 301, "owner_id":0, "x":17, "y":3}
            ],
        }"""
        map_stats = self.loader.map_stats.get("default_map", {})
        self.game_map = GameMap(map_stats.get("width",20), map_stats.get("height",20))
        for ent in map_stats.get("entities", []):
            # 这里不调用 spawn_unit, 因为不触发事件
            if ent["Type"] == "Unit":
                unit = self.loader.create_unit(ent["Name"], ent["uid"], ent["owner_id"])
                unit.x = ent["x"]
                unit.y = ent["y"]
                unit.buffs = ent.get("buffs", {})
                unit.vars = ent.get("vars", {})
                self.entities[ent["uid"]] = unit
                self.game_map.place_entity(unit, ent["x"], ent["y"])
            elif ent["Type"] == "Building":
                building = self.loader.create_building(ent["Name"], ent["uid"], ent["owner_id"], ent.get("vertical", False))
                building.x = ent["x"]
                building.y = ent["y"]
                building.buffs = ent.get("buffs", {})
                building.vars = ent.get("vars", {})
                self.entities[ent["uid"]] = building
                self.game_map.place_entity(building, ent["x"], ent["y"])
            else:
                raise ValueError(f"Unknown entity type in map: {ent['Type']}")

    def _init_systems(self):
        """初始化技能管理器、规则系统等"""
        self.skill_manager = SkillManager(self)



    # --- 数据接口 ---

    def get_GLOBAL_var(self, player_id: int, key: str, default=None) -> Any:
        if key in self.player_vars[player_id]:
            return self.player_vars[player_id][key]
        self.player_vars[player_id][key] = default
        return default
    
    def set_GLOBAL_var(self, player_id: int, key: str, value: Any):
        self.player_vars[player_id][key] = value
    
    def get_object(self, uid: int) -> Optional[GameObject]:
        return self.entities.get(uid)

    # --- 流程控制 (协程驱动) ---

    async def start_game(self):
        """游戏主循环入口"""
        self._running = True
        self.turn_count = 1
        self.current_player_id = 1
        
        # 触发游戏开始事件
        self.event_bus.emit(Trigger.ON_GAME_START, Context(self))
        
        while self._running:
            await self.run_turn()
            self._switch_turn()

    def _switch_turn(self):
        """切换回合"""
        self.current_player_id += 1
        if self.current_player_id > self.players_num:
            self.current_player_id = 1
            self.turn_count += 1

    async def run_turn(self):
        """
        单个玩家的回合流程
        这是整个状态机的核心，使用 await 来暂停等待 UI 输入
        """
        current_player = self.players[self.current_player_id]
        print(f"--- Player {current_player.player_id} Turn Start ---")

        self.event_bus.emit(Trigger.ON_TURN_START, Context(self, source=current_player))
        
        turn_active = True
        while turn_active:
            # 1. 构造主阶段状态上下文
            # 筛选出当前玩家所有还能动的单位 UID
            # 注意建筑可以随时被拆除
            operable_entities = [
                ent.uid for ent in self.entities.values() 
                if ((ent.operable or isinstance(ent, Building)) and ent.owner_id == current_player.player_id)
            ]
            operable_spells = [
                spell_index for spell_index, casts_left in current_player.spells_casts_left.items()
            ]
            
            # 2. 发送主菜单请求
            try:
                response = await self.request_input(UIRequest(
                    request_id="main_turn_menu",
                    player_id=current_player.player_id,
                    type="MAIN_TURN_MENU",
                    message="请选择行动",
                    validation={
                        "operable_entities": operable_entities,
                        "operable_spells": operable_spells,
                        "can_end_turn": True
                    },
                    allow_cancel=False
                ))
            except asyncio.CancelledError:
                # 处理异常退出
                return 

            # 3. 处理主流程指令
            action = response.get("action")
            
            # TODO: 添加处理操作的逻辑


    # --- 核心交互机制 ---

    def add_request_listener(self, handler: Callable[[UIRequest], None]):
        """注册 UI 请求监听器 (用于展示/高亮等，只读)"""
        self._request_listeners.append(handler)

    def set_player_input_mode(self, player_id: int, mode: str):
        """设置玩家输入模式: interactive | readonly"""
        if mode not in {"interactive", "readonly"}:
            raise ValueError("mode must be 'interactive' or 'readonly'")
        self._player_input_mode[player_id] = mode

    async def request_input(self, request: UIRequest) -> Dict[str, Any]:
        """
        发送请求并挂起，等待 submit_input 唤醒
        """
        if self._input_future is not None and not self._input_future.done():
            raise RuntimeError("Another input request is already pending")

        if "ui_mode" not in request.presentation:
            request.presentation["ui_mode"] = self._player_input_mode.get(request.player_id, "interactive")

        self._current_request = request
        self._input_future = asyncio.get_running_loop().create_future()

        for listener in self._request_listeners:
            listener(request)

        try:
            return await self._input_future
        finally:
            self._current_request = None
            self._input_future = None

    def get_current_request(self) -> Optional[UIRequest]:
        return self._current_request

    def submit_input(self, request_id: str, data: Dict[str, Any]):
        """
        调用此接口提交玩家操作
        """
        if self._current_request is None or self._input_future is None:
            return
        if self._current_request.request_id != request_id:
            return
        if self._input_future.done():
            return

        if data.get("cancel", False):
            if self._current_request.allow_cancel:
                self._input_future.cancel()
            return

        self._input_future.set_result(data)

    # --- 辅助逻辑/战斗计算 ---

    ## -- 辅助函数 --

    def _calc_range_positions(self, unit: Unit, range: Dict[str, Any], Flying: bool = False) -> List[Tuple[int, int]]:
        """获取单位基于指定范围类型的所有格子坐标"""
        """range 示例:
        {
            "Type": "*",   # 范围类型: 十字(+), 王步(*), 直线(-), 斜线(x), 马步(h)
            "Min": 1,      # 最小范围
            "Max": 3       # 最大范围
        }"""
        pass

    ## -- 计算面板属性 --

    def _calc_attack(self, attacker: Unit) -> int:
        pass
    def _calc_move_range(self, unit: Unit) -> int:
        pass
    def _calc_attack_range(self, unit: Unit) -> Tuple[int, int]:
        pass

    ## -- 结合事件系统的计算 --
    
    def _calc_attackable_targets(self, unit: Unit) -> List[int]:
        pass
    
    def _calc_movable_positions(self, unit: Unit) -> List[Tuple[int, int]]:
        pass

    ## -- 战斗流程 --

    async def _execute_attack(self, attacker: Unit, defender: GameObject):
        """执行攻击逻辑 (包含 EventBus 触发)"""
        # 1. 触发攻击前 (Before Attack) - 可能被技能打断
        ctx = Context(self, source=attacker, target=defender)
        self.event_bus.emit(Trigger.BEFORE_ATTACK, ctx)
        if ctx._is_stopped:
            return

        # 2. 计算伤害 (Calc Damage)
        dmg_ctx = Context(self, source=attacker, target=defender, value=self._calc_attack(attacker))
        self.event_bus.emit(Trigger.CALC_DAMAGE, dmg_ctx)
        final_damage = dmg_ctx.value
        
        # 3. 结算 HP
        defender.hp -= final_damage
        print(f"{attacker.name} attacks {defender.name} for {final_damage} damage!")
        
        # 4. 触发攻击后 (溅射、反伤等)
        post_ctx = Context(self, source=attacker, target=defender, value=final_damage)
        self.event_bus.emit(Trigger.ON_ATTACK, post_ctx)

        # 5. 触发受伤事件
        damage_ctx = Context(self, source=attacker, target=defender, value=final_damage)
        self.event_bus.emit(Trigger.ON_DAMAGE_TAKEN, damage_ctx)
        
        # 6. 死亡判定
        if defender.hp <= 0:
            print(f"{defender.name} has been killed!")
            self.event_bus.emit(Trigger.ON_DEATH, Context(self, source=defender, target=attacker, value=final_damage))
            self.event_bus.emit(Trigger.ON_KILL, Context(self, source=attacker, target=defender, value=final_damage))
            # 7. 确认是否死亡
            if defender.hp <= 0:
                # 从地图和实体列表中移除
                self.game_map.remove_entity(defender)
                del self.entities[defender.uid]

    ## --- 实体管理 ---

    def spawn_unit(self, name: str, owner_id: int, x: int, y: int, promoted: bool) -> GameObject:
        uid = self._next_uid
        self._next_uid += 1
        unit = self.loader.create_unit(name, uid, owner_id, promoted)
        unit.x = x
        unit.y = y
        self.entities[uid] = unit
        self.game_map.place_entity(unit, x, y)
        # 触发生成事件
        self.event_bus.emit(Trigger.ON_SPAWN, Context(self, source=unit))
        
        return unit
    
    def spawn_building(self, name: str, owner_id: int, x: int, y: int, vertical: bool) -> GameObject:
        uid = self._next_uid
        self._next_uid += 1
        building = self.loader.create_building(name, uid, owner_id, vertical)
        building.x = x
        building.y = y
        self.entities[uid] = building
        self.game_map.place_entity(building, x, y)
        # 触发生成事件
        self.event_bus.emit(Trigger.ON_SPAWN, Context(self, source=building))
        
        return building