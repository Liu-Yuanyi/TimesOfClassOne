import pygame
import asyncio
import sys
from TimesOfClassOne.ui import SceneManager, TitleScene

# 设置屏幕参数
SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 768
FPS = 60

async def main():
    # 1. Pygame 初始化
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Times of Class One")
    clock = pygame.time.Clock()

    # 2. 创建场景管理器
    manager = SceneManager(screen)
    manager.switch_to(TitleScene) # 初始进入标题画面

    # 3. 主循环
    print("Starting Game Loop...")
    while manager.running:
        dt = clock.tick(FPS) / 1000.0 # Delta time in seconds

        # (A) 处理事件
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                manager.quit_game()
            else:
                if manager.current_scene:
                    manager.current_scene.handle_event(event)

        # (B) 更新逻辑
        if manager.current_scene:
            manager.current_scene.update(dt)

        # (C) 绘制画面
        if manager.current_scene:
            manager.current_scene.draw(screen)
        
        pygame.display.flip()

        # (D) 让出控制权给 asyncio (非常重要!)
        # 这允许后台的 engine (或其他 asyncio 任务) 运行
        await asyncio.sleep(0)

    # 退出清理
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    try:
        # Windows 上 asyncio 设置 (Python 3.8+)
        if sys.platform == 'win32':
             asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
