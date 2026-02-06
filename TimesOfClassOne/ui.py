import pygame
import asyncio
from typing import Dict, Optional, Any
from .session import GameSession
from .modes import baseMode
from .engine import PlayerState

# --- 基础架构 ---

class Scene:
    """所有场景的基类"""
    def __init__(self, manager):
        self.manager = manager

    def handle_event(self, event: pygame.event.Event):
        """处理 Pygame 事件 (点击, 键盘等)"""
        pass

    def update(self, dt: float):
        """每帧逻辑更新 (dt: delta time in seconds)"""
        pass

    def draw(self, screen: pygame.Surface):
        """绘制屏幕"""
        pass

    def on_enter(self, **kwargs):
        """进入场景时调用"""
        pass

    def on_exit(self):
        """离开场景时调用"""
        pass

class SceneManager:
    """管理场景切换和主循环"""
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.current_scene: Optional[Scene] = None
        self.running = True

    def switch_to(self, scene_class, **kwargs):
        if self.current_scene:
            self.current_scene.on_exit()
        self.current_scene = scene_class(self)
        self.current_scene.on_enter(**kwargs)

    def quit_game(self):
        self.running = False

# --- 具体场景实现 ---

class TitleScene(Scene):
    """标题/主菜单场景"""
    def on_enter(self):
        self.font = pygame.font.SysFont("Arial", 32)
        print("进入主菜单")

    def handle_event(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                # 按回车开始游戏 (这里模拟直接进入战斗，实际可能跳到 BP 或 房间)
                self.manager.switch_to(BattleScene)
            elif event.key == pygame.K_ESCAPE:
                self.manager.quit_game()

    def draw(self, screen: pygame.Surface):
        screen.fill((20, 20, 40))
        text = self.font.render("Times of Class One - Press ENTER to Start", True, (255, 255, 255))
        screen.blit(text, (100, 200))

class BattleScene(Scene):
    """战斗场景: 持有 GameSession"""
    def __init__(self, manager):
        super().__init__(manager)
        self.session: Optional[GameSession] = None
        self.font = pygame.font.SysFont("Arial", 16)
        
    def on_enter(self):
        # 初始化一局游戏
        # 实际数据应该从上一级场景(Lobby/BP)传过来
        p1 = PlayerState(player_id=1, _name="Hero")
        p2 = PlayerState(player_id=2, _name="Enemy")
        mode = baseMode("standard") # 需确保 modes.py 里有这个类或类似的
        
        self.session = GameSession(mode, {1: p1, 2: p2})
        
        # 异步启动 session
        asyncio.create_task(self.session.start())

    def on_exit(self):
        if self.session:
            self.session.stop()

    def handle_event(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                # 退出战斗，返回主菜单
                self.manager.switch_to(TitleScene)
            
            # --- 测试用的临时交互 ---
            if event.key == pygame.K_SPACE:
                # 模拟玩家确认操作
                if self.session and self.session.current_request:
                    # 只有当是为了 player 1 请求时才响应
                    req = self.session.current_request
                    if req.player_id == 1:
                        print("UI: User pressed SPACE, submitting action...")
                        # 构造一个假动作
                        action = {"action": "end_turn"} 
                        self.session.submit_action(action)

    def update(self, dt: float):
        # 这里可以读取 session.current_request 来决定显示什么提示
        pass

    def draw(self, screen: pygame.Surface):
        screen.fill((50, 100, 50)) # 绿色背景代表草地
        
        # 绘制简单的状态
        y = 10
        status_lines = [
            f"Turn: {self.session.engine.turn_count}", 
            f"Current Player: {self.session.engine.current_player_id}"
        ]
        
        # 绘制当前请求
        req = self.session.current_request
        if req:
            status_lines.append(f"WAITING INPUT: {req.message} (Player {req.player_id})")
            if req.player_id == 1:
                status_lines.append(">> Press SPACE to End Turn <<")
            else:
                status_lines.append(">> Waiting for Opponent... <<")

        for line in status_lines:
            txt = self.font.render(line, True, (255, 255, 255))
            screen.blit(txt, (10, y))
            y += 25
