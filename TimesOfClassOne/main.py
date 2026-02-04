import asyncio
from typing import Optional
from engine import GameEngine, UIRequest, RequestType
# 假设有一个 Mock 的 UI 和 Mode
class MockMode: 
    name = "Standard"
    def get_player_count(self): return 2

class Application:
    def __init__(self):
        self.current_engine: Optional[GameEngine] = None
        self.game_task: Optional[asyncio.Task] = None
        self.is_app_running = True

    async def main_loop(self):
        """应用程序的主入口"""
        print("--- 游戏启动，进入主菜单 ---")
        
        while self.is_app_running:
            # 这里模拟主菜单的逻辑
            cmd = await self.await_ui_command()
            
            if cmd == "NEW_GAME":
                await self.start_new_game()
            elif cmd == "LOAD_GAME":
                await self.load_game()
            elif cmd == "EXIT_APP":
                self.is_app_running = False

    async def await_ui_command(self):
        # 模拟等待 UI 按钮点击
        # 在真实场景中，这里可能是等待一个 asyncio.Queue 或者 UI 事件
        return await asyncio.to_thread(input, "主菜单 (NEW_GAME/LOAD_GAME/EXIT_APP): ")

    async def start_new_game(self):
        print("--- 初始化新游戏 ---")
        self.current_engine = GameEngine(MockMode())
        
        # 关键点：把游戏逻辑作为一个子任务启动
        # Application 不会被游戏逻辑阻塞，Application 依然拥有控制权
        self.game_task = asyncio.create_task(self.run_game_wrapper())
        
        # 进入“战局中”的控制循环
        await self.in_game_loop()

    async def run_game_wrapper(self):
        """包装 Engine 的运行，处理异常和取消"""
        try:
            # 假设 engine 有一个 async run_turn_loop() 方法
            # await self.current_engine.run_turn_loop()
            print("Engine: 游戏循环开始...")
            # 模拟游戏运行
            await asyncio.Future() # 假装在一直运行
        except asyncio.CancelledError:
            print("Engine: 收到停机指令，正在清理战场...")
        finally:
            print("Engine: 彻底关闭。")

    async def in_game_loop(self):
        """游戏进行时的系统级监听"""
        print("--- 进入战局 UI 模式 ---")
        while self.game_task and not self.game_task.done():
            # 这里的 input 模拟 UI 线程的上帝视角操作
            # 注意：这和 Engine 请求的“选择单位”不同，这是系统级指令
            cmd = await asyncio.to_thread(input, "系统指令 (SAVE/MENU/RESUME): ")
            
            if cmd == "SAVE":
                self.save_game_snapshot()
            elif cmd == "MENU":
                print("Application: 正在终止当前战局...")
                self.game_task.cancel() # 杀死 Engine 任务
                try:
                    await self.game_task
                except asyncio.CancelledError:
                    pass
                self.current_engine = None
                self.game_task = None
                print("Application: 返回主菜单")
                return # 退出 in_game_loop，回到 main_loop

    def save_game_snapshot(self):
        if not self.current_engine:
            return
        # 直接读取 Engine 内存进行保存，哪怕 Engine 正在 await input
        print(f"System: 正在保存... 玩家数: {self.current_engine.players_num}")
        print("System: 保存完毕 (Engine 还在后台等输入，未受影响)")

    async def load_game(self):
        print("Application: 读取存档...")
        # 逻辑同 start_new_game，只是数据是从文件来的
        await self.start_new_game()

if __name__ == "__main__":
    app = Application()
    asyncio.run(app.main_loop())