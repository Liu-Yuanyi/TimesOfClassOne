import asyncio
from typing import Optional, Dict, Any
from .engine import GameEngine, UIRequest, PlayerState
from .modes import baseMode
from .event import Trigger, Context

class GameSession:
    """
    管理一局游戏的会话。
    负责连接 Engine 和外界 (UI/Network/AI)。
    """
    def __init__(self, mode: baseMode, player_states: Dict[int, PlayerState], map_name: str = "default_map"):
        self.engine = GameEngine(mode, player_states, map_name)
        self.is_running = False
        self.engine_task: Optional[asyncio.Task] = None
        
        # 绑定事件监听
        self.engine.event_bus.subscribe(Trigger.ON_INPUT_REQUEST, self._on_input_request)
        self.engine.event_bus.subscribe(Trigger.ON_GAME_START, self._on_game_start)
        # 可以继续绑定 ON_GAME_OVER 等
        
        # 当前等待处理的请求
        self.current_request: Optional[UIRequest] = None

    async def start(self):
        """启动游戏引擎"""
        self.is_running = True
        print("[Session] Starting Game Engine...")
        self.engine_task = asyncio.create_task(self.engine.start_game())
        
        try:
            await self.engine_task
        except asyncio.CancelledError:
            print("[Session] Game Engine Stopped.")
        finally:
            self.is_running = False

    def stop(self):
        """强制停止游戏"""
        if self.engine_task:
            self.engine_task.cancel()

    def submit_action(self, action_data: Dict[str, Any]):
        """
        UI 层调用此方法提交操作。
        """
        if not self.current_request:
            print("[Session] No active request to submit to.")
            return

        # 这里可以添加网络发送逻辑
        # if self.is_network_game: send_to_server(action_data)
        
        # 提交给引擎
        self.engine.submit_input(self.current_request.request_id, action_data)

    # --- 事件回调 ---

    def _on_input_request(self, ctx: Context):
        """
        引擎请求输入时触发。
        """
        request: UIRequest = ctx.data
        self.current_request = request
        print(f"[Session] Engine requests input for Player {request.player_id}: {request.type}")
        # 注意: 这里不需要直接调用 UI，UI 会在它的 update 循环中检查 session.current_request

    def _on_game_start(self, ctx: Context):
        print("[Session] Game Started!")
