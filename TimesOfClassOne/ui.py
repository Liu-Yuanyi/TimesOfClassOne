import pygame
import asyncio
from typing import Dict, Optional, Any, List, Callable, Tuple
import json5

from session import GameSession
from modes import baseMode
from engine import PlayerState
from loader import loader

# --- 1. 轻量级 UI 框架 (美化版) ---

# 配色方案 (Nord/Dracula 风格混搭)
THEME = {
    "bg_dark": (40, 44, 52),       # 深色背景
    "panel_bg": (33, 37, 43),      # 面板背景
    "text_main": (230, 230, 230),  # 主要文字
    "text_dim": (150, 150, 150),   # 次要文字
    
    "btn_primary": (97, 175, 239), # 主按钮 (蓝)
    "btn_primary_hover": (117, 195, 255),
    "btn_primary_active": (80, 150, 210),
    
    "btn_success": (152, 195, 121),# 成功/开始 (绿)
    "btn_success_hover": (172, 215, 141),
    
    "btn_danger": (224, 108, 117), # 危险/退出 (红)
    "btn_danger_hover": (244, 128, 137),
    
    "btn_neutral": (62, 68, 81),   # 普通/默认 (灰)
    "btn_neutral_hover": (75, 82, 99),
    
    "shadow": (20, 20, 25) # 阴影颜色
}

class UIElement:
    def __init__(self, x: int, y: int, width: int, height: int):
        self.rect = pygame.Rect(x, y, width, height)
        self.visible = True
        self.active = True # 是否响应交互

    def handle_event(self, event: pygame.event.Event) -> bool:
        return False

    def draw(self, screen: pygame.Surface):
        pass

class Label(UIElement):
    def __init__(self, x, y, text, font: pygame.font.Font, color=THEME["text_main"], shadow=True):
        surf = font.render(text, True, color)
        super().__init__(x, y, surf.get_width(), surf.get_height())
        self.text = text
        self.font = font
        self.color = color
        self.shadow = shadow
        self._surface = surf
        if shadow:
             self._shadow_surf = font.render(text, True, (0, 0, 0))

    def set_text(self, text):
        self.text = text
        self._surface = self.font.render(text, True, self.color)
        if self.shadow:
             self._shadow_surf = self.font.render(text, True, (0, 0, 0))
        self.rect.width = self._surface.get_width()
        self.rect.height = self._surface.get_height()

    def draw(self, screen: pygame.Surface):
        if self.visible:
            if self.shadow:
                # 绘制文字阴影 (向右下偏移2像素)
                screen.blit(self._shadow_surf, (self.rect.x + 2, self.rect.y + 2))
            screen.blit(self._surface, self.rect)

class Button(UIElement):
    def __init__(self, x, y, width, height, text, font: pygame.font.Font, 
                 on_click: Callable[[], None], 
                 style="neutral", # neutral, primary, success, danger
                 text_color=THEME["text_main"]):
        super().__init__(x, y, width, height)
        self.text = text
        self.font = font
        self.on_click = on_click
        self.text_color = text_color
        self.is_hovered = False
        self.is_pressed = False
        self.style_type = style
        self.radius = 8  # 圆角半径

    def _get_colors(self):
        if not self.active:
             return (50, 54, 60) # Disabled color
             
        if self.style_type == "primary":
            base = THEME["btn_primary"]
            hover = THEME["btn_primary_hover"]
        elif self.style_type == "success":
            base = THEME["btn_success"]
            hover = THEME["btn_success_hover"]
        elif self.style_type == "danger":
            base = THEME["btn_danger"]
            hover = THEME["btn_danger_hover"]
        else: # neutral
            base = THEME["btn_neutral"]
            hover = THEME["btn_neutral_hover"]
            
        color = hover if self.is_hovered else base
        # 如果按下，颜色稍微变暗一点点，或者这里我们主要靠位移来体现按下
        return color

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible or not self.active:
            return False
        
        if event.type == pygame.MOUSEMOTION:
            self.is_hovered = self.rect.collidepoint(event.pos)
        
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.is_hovered:
                self.is_pressed = True
                return True
        
        if event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1 and self.is_pressed:
                self.is_pressed = False
                if self.is_hovered and self.on_click:
                    self.on_click()
                return True
            self.is_pressed = False

        return False

    def draw(self, screen: pygame.Surface):
        if not self.visible:
            return
        
        color = self._get_colors()
        
        # 计算绘制位置 (按下时下沉)
        draw_rect = self.rect.copy()
        shadow_rect = self.rect.copy()
        shadow_rect.y += 4 # 阴影深度
        
        if self.is_pressed:
            #不仅仅是变色，还有物理位移，按下时 draw_rect 向下移动，遮住部分阴影
            draw_rect.y += 2
        
        # 1. 绘制底部阴影 (圆角)
        if self.active and not self.is_pressed:
             pygame.draw.rect(screen, THEME["shadow"], shadow_rect, border_radius=self.radius)

        # 2. 绘制按钮主体
        pygame.draw.rect(screen, color, draw_rect, border_radius=self.radius)
        
        # 3. 绘制文字
        text_surf = self.font.render(self.text, True, self.text_color)
        text_rect = text_surf.get_rect(center=draw_rect.center)
        
        # 给文字也加特别淡的阴影
        if self.active:
             shadow_surf = self.font.render(self.text, True, (0,0,0, 50))
             screen.blit(shadow_surf, (text_rect.x+1, text_rect.y+1))
             
        screen.blit(text_surf, text_rect)

class UIContainer:
    """管理一组 UI 元素"""
    def __init__(self):
        self.elements: List[UIElement] = []

    def add(self, element: UIElement):
        self.elements.append(element)

    def handle_event(self, event: pygame.event.Event):
        # 逆序处理，确保顶层元素先响应
        for el in reversed(self.elements):
            if el.handle_event(event):
                break

    def draw(self, screen: pygame.Surface):
        for el in self.elements:
            el.draw(screen)
    
    def clear(self):
        self.elements.clear()

# --- 2. 场景基类 ---

class MapView:
    """负责在屏幕上绘制地图和实体"""
    def __init__(self, x, y, tile_size=40):
        self.x = x # 屏幕上的起始x
        self.y = y # 屏幕上的起始y
        self.tile_size = tile_size
        self.engine = None # 绑定的游戏引擎实例
        
        self.colors = {
            0: (100, 100, 100), # 中立
            1: (50, 50, 200),   # P1 (Blue)
            2: (200, 50, 50),   # P2 (Red)
            3: (50, 200, 50),   # P3 (Green)
            4: (200, 200, 50)   # P4 (Yellow)
        }
        self.bg_color = (200, 200, 180) # 地面颜色
        self.grid_color = (150, 150, 150) # 网格线颜色
        
        # 高亮层数据: {(x, y): color}
        self.highlights: Dict[Tuple[int, int], Tuple[int, int, int]] = {}

    def bind_engine(self, engine):
        self.engine = engine

    def set_highlights(self, highlights: Dict[Tuple[int, int], Tuple[int, int, int]]):
        self.highlights = highlights

    def clear_highlights(self):
        self.highlights = {}

    def grid_to_screen(self, gx, gy):
        """游戏网格坐标 (1-based) -> 屏幕像素坐标 (Top-Left)"""
        return (self.x + (gx - 1) * self.tile_size, 
                self.y + (gy - 1) * self.tile_size)

    def screen_to_grid(self, sx, sy):
        """屏幕像素坐标 -> 游戏网格坐标 (1-based)"""
        gx = (sx - self.x) // self.tile_size + 1
        gy = (sy - self.y) // self.tile_size + 1
        return gx, gy

    def draw(self, screen: pygame.Surface):
        if not self.engine:
            return

        map_w = self.engine.game_map.width
        map_h = self.engine.game_map.height

        # 1. 绘制网格底色
        total_w = map_w * self.tile_size
        total_h = map_h * self.tile_size
        pygame.draw.rect(screen, self.bg_color, (self.x, self.y, total_w, total_h))
        
        # 1.5 绘制高亮
        for (gx, gy), color in self.highlights.items():
            if not self.engine.game_map.out_of_bounds(gx, gy):
                sx, sy = self.grid_to_screen(gx, gy)
                # 绘制半透明矩形
                s = pygame.Surface((self.tile_size, self.tile_size))
                s.set_alpha(128) # 透明度
                s.fill(color)
                screen.blit(s, (sx, sy))

        # 2. 绘制网格线
        for i in range(map_w + 1):
            sx = self.x + i * self.tile_size
            pygame.draw.line(screen, self.grid_color, (sx, self.y), (sx, self.y + total_h))
        for j in range(map_h + 1):
            sy = self.y + j * self.tile_size
            pygame.draw.line(screen, self.grid_color, (self.x, sy), (self.x + total_w, sy))

        # 3. 绘制实体
        # 简单起见，先画圆圈代表兵种，方块代表建筑
        font = pygame.font.SysFont("Arial", 12)
        
        for uid, ent in self.engine.entities.items():
            sx, sy = self.grid_to_screen(ent.x, ent.y)
            color = self.colors.get(ent.owner_id, (255, 255, 255))
            
            # 计算实体占用的像素大小
            ent_w_tiles = ent.size.get("Width", 1)
            ent_h_tiles = ent.size.get("Height", 1)
            if hasattr(ent, 'vertical') and ent.vertical:
                 ent_w_tiles, ent_h_tiles = ent_h_tiles, ent_w_tiles
            
            pixel_w = ent_w_tiles * self.tile_size
            pixel_h = ent_h_tiles * self.tile_size
            
            rect = pygame.Rect(sx + 2, sy + 2, pixel_w - 4, pixel_h - 4) # 留一点边距

            if ent.__class__.__name__ == "Building":
                pygame.draw.rect(screen, color, rect)
                pygame.draw.rect(screen, (0,0,0), rect, 2) # 黑边
            else:
                # Unit 画圆
                cx = sx + pixel_w // 2
                cy = sy + pixel_h // 2
                radius = min(pixel_w, pixel_h) // 2 - 4
                pygame.draw.circle(screen, color, (cx, cy), radius)
                pygame.draw.circle(screen, (0,0,0), (cx, cy), radius, 2)

            # 绘制名称或首字母
            name_txt = ent.name[:2]
            txt_surf = font.render(name_txt, True, (255, 255, 255))
            screen.blit(txt_surf, (sx + 5, sy + 5))
            
            # 简单的血条
            hp_ratio = max(0, ent.hp / ent.max_hp) if hasattr(ent, 'max_hp') and ent.max_hp > 0 else 1
            pygame.draw.rect(screen, (255, 0, 0), (sx + 2, sy + pixel_h - 6, pixel_w - 4, 4))
            pygame.draw.rect(screen, (0, 255, 0), (sx + 2, sy + pixel_h - 6, (pixel_w - 4) * hp_ratio, 4))

class Scene:
    """所有场景的基类"""
    def __init__(self, manager):
        self.manager = manager
        self.ui = UIContainer() # 每个场景自带 UI 容器

    def handle_event(self, event: pygame.event.Event):
        """处理 Pygame 事件 (点击, 键盘等)"""
        self.ui.handle_event(event)

    def update(self, dt: float):
        """每帧逻辑更新 (dt: delta time in seconds)"""
        pass

    def draw(self, screen: pygame.Surface):
        """绘制屏幕"""
        self.ui.draw(screen)

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
        self.width = screen.get_width()
        self.height = screen.get_height()
        
        # 共享资源
        self.common_loader = loader() 
        # 预加载一些基础数据，方便用
        try:
           self.common_loader.append_stats("./stats/maps.json5", "map")
        except Exception as e:
           print(f"Warning: Failed to load maps.json5: {e}")

    def switch_to(self, scene_class, **kwargs):
        if self.current_scene:
            self.current_scene.on_exit()
        self.current_scene = scene_class(self)
        self.current_scene.on_enter(**kwargs)

    def quit_game(self):
        self.running = False


# --- 3. 具体场景 ---

class TitleScene(Scene):
    """主菜单"""
    def on_enter(self, **kwargs):
        print("UI: Entering Main Menu")
        try:
            # 尝试加载更现代的字体，如果系统有微软雅黑(Msyd)或其他无衬线字体最好
            title_font = pygame.font.SysFont("Microsoft YaHei", 48, bold=True) 
            menu_font = pygame.font.SysFont("Microsoft YaHei", 20, bold=True)
        except:
             title_font = pygame.font.SysFont("Arial", 48, bold=True)
             menu_font = pygame.font.SysFont("Arial", 20, bold=True)
        
        cx = self.manager.width // 2
        
        # 标题 (带阴影)
        self.ui.add(Label(cx - 300, 100, "Times of Class One: Honor Edition", title_font, color=THEME["text_main"]))

        # 按钮
        btn_width = 280
        btn_height = 55
        start_y = 280
        gap = 75
        
        self.ui.add(Button(cx - btn_width//2, start_y, btn_width, btn_height, 
                           "本地游戏", menu_font, self.goto_local_game, style="primary"))
        
        self.ui.add(Button(cx - btn_width//2, start_y + gap, btn_width, btn_height, 
                           "图鉴 (WIP)", menu_font, lambda: print("TODO"), style="neutral"))
        
        # 禁用的按钮我们 temporarily 用 neutral 并且逻辑上不做处理，或者以后给 Button 加 disable 属性
        b_net_create = Button(cx - btn_width//2, start_y + gap*2, btn_width, btn_height, 
                           "创建网络游戏 (开发中)", menu_font, lambda: print("TODO"), style="neutral")
        b_net_create.active = False # 禁用
        self.ui.add(b_net_create)
        
        b_net_join = Button(cx - btn_width//2, start_y + gap*3, btn_width, btn_height, 
                           "加入网络游戏 (开发中)", menu_font, lambda: print("TODO"), style="neutral")
        b_net_join.active = False
        self.ui.add(b_net_join)
                           
        self.ui.add(Button(cx - btn_width//2, start_y + gap*4, btn_width, btn_height, 
                           "退出游戏", menu_font, self.manager.quit_game, style="danger"))

    def goto_local_game(self):
        self.manager.switch_to(LocalGameSetupScene)
    
    def draw(self, screen: pygame.Surface):
        screen.fill(THEME["bg_dark"]) # 统一背景色
        super().draw(screen)

class LocalGameSetupScene(Scene):
    """创建本地游戏界面"""
    def on_enter(self, **kwargs):
        try:
            self.font = pygame.font.SysFont("Microsoft YaHei", 18)
            self.header_font = pygame.font.SysFont("Microsoft YaHei", 32, bold=True)
        except:
            self.font = pygame.font.SysFont("Arial", 18)
            self.header_font = pygame.font.SysFont("Arial", 32, bold=True)
        
        cx = self.manager.width // 2
        
        self.ui.add(Label(50, 50, "创建本地游戏", self.header_font))
        
        # --- 地图选择 ---
        self.ui.add(Label(50, 120, "选择地图:", self.font))
        self.selected_map = "default_map"
        
        # 从 loader 中获取地图列表
        map_list = list(self.manager.common_loader.map_stats.keys())
        # 如果 load 失败或者为空，至少保留 default_map
        if "default_map" not in map_list:
             map_list.append("default_map")

        map_start_y = 150
        for i, m_name in enumerate(map_list):
            btn = Button(50, map_start_y + i*50, 220, 40, m_name, self.font, 
                         lambda n=m_name: self.select_map(n), style="neutral")
            self.ui.add(btn)
        
        self.selected_map_label = Label(300, 120, f"当前选择: {self.selected_map}", self.font, color=THEME["btn_success"])
        self.ui.add(self.selected_map_label)

        # --- 模式选择 (简化) ---
        self.ui.add(Label(300, 200, "游戏模式: 经典模式 (默认)", self.font))
        
        # --- 玩家设置 (简化) ---
        # 默认为 P1 vs P2
        self.ui.add(Label(300, 250, "玩家1: 本地玩家 (Blue)", self.font))
        self.ui.add(Label(300, 290, "玩家2: AI 玩家 (Red)", self.font))
        
        # --- 底部按钮 ---
        self.ui.add(Button(50, 600, 160, 50, "返回主菜单", self.font, 
                           lambda: self.manager.switch_to(TitleScene), style="neutral"))
                           
        self.ui.add(Button(self.manager.width - 250, 600, 200, 50, "开始游戏", self.header_font, 
                           self.start_game, style="success")) # 改用 success 绿色风格

    def select_map(self, map_name):
        self.selected_map = map_name
        self.selected_map_label.set_text(f"当前选择: {self.selected_map}")
        print(f"Selected map: {map_name}")

    def start_game(self):
        # 准备数据，进入 BattleScene
        # 构造默认玩家
        p1 = PlayerState(player_id=1, _name="Player 1", gold=100, wood=100)
        p2 = PlayerState(player_id=2, _name="AI Player", gold=100, wood=100) 
        
        # 构造模式
        mode = baseMode("standard") 
        
        print(f"Starting local game on map {self.selected_map}")
        self.manager.switch_to(BattleScene, 
                              mode=mode, 
                              player_states={1: p1, 2: p2},
                              map_name=self.selected_map)

    def draw(self, screen: pygame.Surface):
        screen.fill(THEME["bg_dark"]) 
        super().draw(screen)



class UnitInfoPanel(UIElement):
    """侧边栏：显示单位详情"""
    def __init__(self, x, y, width, height, font):
        super().__init__(x, y, width, height)
        self.font = font
        self.target_unit = None
        self.bg_color = THEME["panel_bg"]

    def set_target(self, unit):
        self.target_unit = unit

    def draw(self, screen: pygame.Surface):
        # 绘制背景
        pygame.draw.rect(screen, self.bg_color, self.rect)
        pygame.draw.rect(screen, (50, 50, 50), self.rect, 2)
        
        if not self.target_unit:
            return

        # 绘制信息
        u = self.target_unit
        lines = [
            f"名称: {u.name}",
            f"ID: {u.uid}",
            f"归属: Player {u.owner_id}",
            f"HP: {u.hp} / {u.max_hp}",
        ]
        
        # 区分兵种和建筑
        if hasattr(u, "attack"): 
             lines.append(f"攻击: {u.attack}")
             lines.append(f"攻击范围: {u.attack_range}")
             lines.append(f"移动相关: M={u.move_range}")
        
        if hasattr(u, "promoted"):
            lines.append(f"晋升: {'Yes' if u.promoted else 'No'}")
        
        if hasattr(u, "skills"):
            lines.append("--- 技能 ---")
            for sk_name, sk_info in u.skills.items():
                val = u.vars.get(sk_name, {}).get("Value", 0)
                lines.append(f"{sk_name} (剩余: {val})")
        
        y_off = 10
        for line in lines:
            txt = self.font.render(line, True, THEME["text_main"])
            screen.blit(txt, (self.rect.x + 10, self.rect.y + y_off))
            y_off += 25

class BattleScene(Scene):
    """战斗场景"""
    def __init__(self, manager):
        super().__init__(manager)
        self.session: Optional[GameSession] = None
        try:
             self.font = pygame.font.SysFont("Microsoft YaHei", 16)
        except:
             self.font = pygame.font.SysFont("Arial", 16)
        
        # 布局参数
        self.map_view = MapView(20, 50, tile_size=32)
        
        # 侧边栏
        self.info_panel = UnitInfoPanel(700, 50, 200, 400, self.font)
        self.ui.add(self.info_panel)
        
        # 交互状态
        self.selected_uid: Optional[int] = None
        
        # 底部按钮栏
        self.btn_end_turn = Button(700, 500, 120, 40, "结束回合", self.font, 
                                   self.do_end_turn, style="primary")
        self.ui.add(self.btn_end_turn)
        
    def on_enter(self, mode=None, player_states=None, map_name="default_map", **kwargs):
        if not mode or not player_states:
             # Fallback for testing
             print("Warning: BattleScene entered without config, using defaults.")
             p1 = PlayerState(player_id=1, _name="Hero")
             p2 = PlayerState(player_id=2, _name="Enemy")
             mode = baseMode("standard") 
             player_states = {1: p1, 2: p2}

        # 检查 session 是否接收 map_name
        try:
            self.session = GameSession(mode, player_states, map_name)
        except TypeError:
            print("Warning: GameSession does not support map_name yet.")
            self.session = GameSession(mode, player_states)

        # 绑定 Engine 到 MapView
        self.map_view.bind_engine(self.session.engine)

        asyncio.create_task(self.session.start())
        print("Battle Scene Started")

    def on_exit(self):
        if self.session:
            self.session.stop()
            print("Battle Session Stopped")

    def handle_event(self, event: pygame.event.Event):
        super().handle_event(event) # 先处理可能存在的 UI
        
        # 处理地图交互
        if event.type == pygame.MOUSEBUTTONDOWN:
            mx, my = pygame.mouse.get_pos()
            gx, gy = self.map_view.screen_to_grid(mx, my)
            # 确保引擎已加载地图且点击在范围内
            if self.session and self.session.engine and self.session.engine.game_map:
                if not self.session.engine.game_map.out_of_bounds(gx, gy):
                     if event.button == 1: # 左键: 选择
                         self.handle_select(gx, gy)
                     elif event.button == 3: # 右键: 移动/攻击
                         self.handle_order(gx, gy)
                else:
                    # 点击地图外，取消选择
                    if event.button == 1:
                        self.deselect()

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.manager.switch_to(TitleScene)
            if event.key == pygame.K_SPACE:
                 self.do_end_turn()

    def handle_select(self, x, y):
        """处理左键选择"""
        engine = self.session.engine
        ent = engine.game_map.get_entity_at(x, y)
        
        self.selected_uid = ent.uid if ent else None
        self.info_panel.set_target(ent)
        
        # 计算高亮
        self.map_view.clear_highlights()
        
        if ent and ent.owner_id == engine.current_player_id:
            # 只有当前玩家的单位才显示移动/攻击范围
            highlights = {}
            # 绿色=选中
            highlights[(ent.x, ent.y)] = (0, 255, 0)
            
            # 使用 engine 的计算方法
            if hasattr(ent, "nowmovable") and ent.nowmovable:
                 moves = engine.calc_movable_positions(ent)
                 for pos in moves:
                     highlights[pos] = (0, 0, 255) # 蓝色移动
            
            if hasattr(ent, "nowattackable") and ent.nowattackable:
                 attacks = engine.calc_attackable_positions(ent)
                 for pos in attacks:
                     highlights[pos] = (255, 0, 0) # 红色攻击
            
            self.map_view.set_highlights(highlights)
        elif ent:
             # 选中敌人或中立，只高亮自身
             self.map_view.set_highlights({(ent.x, ent.y): (255, 255, 0)})

    def handle_order(self, x, y):
        """处理右键指令"""
        if not self.selected_uid:
            return
            
        # 必须是当前玩家的回合且正在等待输入
        if not (self.session.current_request and self.session.current_request.player_id == self.session.engine.current_player_id):
             print("Not your turn!")
             return

        engine = self.session.engine
        unit = engine.get_object(self.selected_uid)
        if not unit or unit.owner_id != engine.current_player_id:
            return

        # 检查是否移动
        moves = engine.calc_movable_positions(unit)
        if (x, y) in moves:
            print(f"Ordering Move to {x}, {y}")
            self.session.submit_action({
                "action": "entity_move", 
                "entity_uid": unit.uid, 
                "target_position": [x, y]
            })
            self.deselect()
            return

        # 检查是否攻击
        attacks = engine.calc_attackable_positions(unit)
        if (x, y) in attacks:
            target_ent = engine.game_map.get_entity_at(x, y)
            if target_ent:
                print(f"Ordering Attack on {target_ent.name}")
                self.session.submit_action({
                    "action": "entity_attack", 
                    "entity_uid": unit.uid, 
                    "target_entity_uid": target_ent.uid,
                    "target_position": [x, y]
                })
                self.deselect()
                return

    def deselect(self):
        self.selected_uid = None
        self.info_panel.set_target(None)
        self.map_view.clear_highlights()

    def do_end_turn(self):
        if self.session and self.session.current_request:
             self.session.submit_action({"action": "end_turn"})
             self.deselect()
    
    def update(self, dt: float):
        # 可以在这里做自动重绘检测等
        pass

    def draw(self, screen: pygame.Surface):
        screen.fill((50, 55, 60)) 
        
        # 绘制地图
        self.map_view.draw(screen)

        # 绘制 UI
        super().draw(screen) # Buttons & Panels
        
        # 简单的状态文字
        y = 500
        status_lines = []
        if self.session and self.session.engine:
             eng = self.session.engine
             status_lines.append(f"Turn: {eng.turn_count}")
             status_lines.append(f"Current Player: P{eng.current_player_id}")
        
        if self.session and self.session.current_request:
            req = self.session.current_request
            status_lines.append(f"WAITING INPUT ({req.player_id})")

        for line in status_lines:
            txt = self.font.render(line, True, THEME["text_main"])
            screen.blit(txt, (20, y))
            y += 25


