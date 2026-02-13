from typing import Dict, List, Tuple, Any, Optional, TYPE_CHECKING
from entities import GameObject, Unit, Building
if TYPE_CHECKING:
    from engine import GameEngine

class GameMap:
    """游戏地图类，负责存储地图信息和提供地图相关的功能"""
    """同时维护实体坐标和地图坐标的统一, 也即需要在每个函数后边设置置实体坐标的代码, 以保证地图和实体坐标的一致性"""
    def __init__(self, map_info: Dict[str, Any]):
        self.name = map_info.get("Name", "Unnamed Map")
        self.width = map_info.get("Width", 20)
        self.height = map_info.get("Height", 20)
        # "宽度"对应x轴，"高度"对应y轴，矩阵用列优先表示, 即matrix[x][y]表示(x,y)位置的实体UID
        # 地图下标从1开始，0留作无效值
        self.matrix: List[List[Optional[int]]] = [[None for _ in range(self.height + 1)] for _ in range(self.width + 1)]

    def out_of_bounds(self, x: int, y: int) -> bool:
        """检查坐标是否越界"""
        return x <= 0 or y <= 0 or x > self.width or y > self.height

    def place_entity(self, entity: GameObject, x: int, y: int) -> bool:
        """尝试在地图上放置一个实体，返回是否成功"""
        dx = entity.size["Width"]
        dy = entity.size["Height"]
        if entity.vertical:
            dx, dy = dy, dx
        # 检查放置区域是否越界或被占用
        if self.out_of_bounds(x, y) or self.out_of_bounds(x + dx - 1, y + dy - 1):
            return False
        for i in range(x, x + dx):
            for j in range(y, y + dy):
                if self.matrix[i][j] is not None:
                    return False
        for i in range(x, x + dx):
            for j in range(y, y + dy):
                self.matrix[i][j] = entity.uid
        entity.x = x
        entity.y = y
        return True
    
    def move_entity(self, entity: GameObject, new_x: int, new_y: int) -> bool:
        """尝试移动一个实体到新位置，返回是否成功"""
        # 先清除原位置
        dx = entity.size["Width"]
        dy = entity.size["Height"]
        if entity.vertical:
            dx, dy = dy, dx
        if self.out_of_bounds(new_x, new_y) or self.out_of_bounds(new_x + dx - 1, new_y + dy - 1):
            return False
        for i in range(entity.x, entity.x + dx):
            for j in range(entity.y, entity.y + dy):
                self.matrix[i][j] = None
        # 尝试放置到新位置
        if not self.place_entity(entity, new_x, new_y):
            # 如果放置失败，恢复原位置
            self.place_entity(entity, entity.x, entity.y)
            return False
        return True
    
    def swap_entities(self, entity1: GameObject, entity2: GameObject) -> bool:
        """尝试交换两个实体的位置，返回是否成功"""
        x1, y1 = entity1.pos
        x2, y2 = entity2.pos
        dx1 = entity1.size["Width"]
        dy1 = entity1.size["Height"]
        dx2 = entity2.size["Width"]
        dy2 = entity2.size["Height"]
        if entity1.vertical:
            dx1, dy1 = dy1, dx1
        if entity2.vertical:
            dx2, dy2 = dy2, dx2
        # 直接交换, 因为交换过程中原位置会被对方占用, 不会出现自己占用自己的情况
        if dx1 != dx2 or dy1 != dy2:
            return False # 只支持交换同尺寸的实体
        for i in range(x1, x1 + dx1):
            for j in range(y1, y1 + dy1):
                self.matrix[i][j] = entity2.uid
        for i in range(x2, x2 + dx2):
            for j in range(y2, y2 + dy2):
                self.matrix[i][j] = entity1.uid
        entity1.x, entity1.y = x2, y2
        entity2.x, entity2.y = x1, y1
        return True

    def remove_entity(self, entity: GameObject):
        """从地图上移除一个实体"""
        dx = entity.size["Width"]
        dy = entity.size["Height"]
        if entity.vertical:
            dx, dy = dy, dx
        for i in range(entity.x, entity.x + dx):
            for j in range(entity.y, entity.y + dy):
                self.matrix[i][j] = None
        entity.x = 0
        entity.y = 0

    def get_uid_at(self, x: Any, y: Optional[int] = None) -> Optional[int]:
        """获取指定位置的实体UID"""
        if y is None:
            x, y = x
        if self.out_of_bounds(x, y):
            return None
        return self.matrix[x][y]
    
    # range 相关:
    # rule.md 中说:表示范围的记号主要分为三种, +代表曼哈顿距离, \*代表切比雪夫距离, -代表只能沿直线. 比如\*3为以某一位置为中心的7\*7的正方形范围, 总共49格; 而+2是一个斜45度的一个锯齿方形区域, 总共13格; -5是一个大的十字, 总共21格. 当然也有一些特殊的范围, 比如迈步哥的范围是国象的马步, 不算起始位置总共八格. 当然, 如果这个范围是相对于一个大于1\*1的单位描述的, 那么则会相应的变形. 比如一个2\*2的建筑的+3范围, 事实上(不算建筑本身的四格)有36格.

    # type: *, +, -, x, h

    # 保证如果type in [x,h], 则实体的大小必须是1*1
    # 保证如果type=h, 则min和max必须都为1
    # 除了-, 其他都可以深搜或广搜, 但是要注意实体大小和障碍物的影响

    def calc_range_positions(self, entity: GameObject, range_info: Dict[str, Any]) -> List[Tuple[int, int]]:
        """计算以entity为中心，满足range_info条件的格子位置列表"""
        positions = set()
        
        # 1. 基础信息解析
        # 实体占据的矩形区域: [ex, ex+w) * [ey, ey+h)
        ex, ey = entity.pos
        w = entity.size["Width"]
        h = entity.size["Height"]
        if entity.vertical:
            w, h = h, w
            
        range_type = range_info.get("Type", "*")
        rmin = range_info.get("Min", 1)
        rmax = range_info.get("Max", 1)

        # 2. 特殊形状处理: 马步
        if range_type == "h":
            if w != 1 or h != 1: 
                raise ValueError("Range type 'h' only supports 1*1 entities")
            if rmin != 1 or rmax != 1:
                raise ValueError("Range type 'h' only supports Min=1 and Max=1")
            # 马步通常是定值的
            moves = [
                (ex-2, ey-1), (ex-2, ey+1), (ex+2, ey-1), (ex+2, ey+1),
                (ex-1, ey-2), (ex-1, ey+2), (ex+1, ey-2), (ex+1, ey+2)
            ]
            for px, py in moves:
                if not self.out_of_bounds(px, py):
                    positions.add((px, py))
            return list(positions)

        if range_type == "x" and (w != 1 or h != 1):
            raise ValueError("Range type 'x' only supports 1*1 entities")

        # 3. 通用距离场扫描
        # 只要在实体边界外扩 rmax 的范围内扫描即可
        scan_min_x = max(1, ex - rmax)
        scan_max_x = min(self.width, ex + w + rmax - 1)
        scan_min_y = max(1, ey - rmax)
        scan_max_y = min(self.height, ey + h + rmax - 1)

        for px in range(scan_min_x, scan_max_x + 1):
            for py in range(scan_min_y, scan_max_y + 1):
                # 排除实体自身占据的格子
                if ex <= px < ex + w and ey <= py < ey + h:
                    continue

                # 计算 px, py 到实体矩形的距离
                dx = 0
                if px < ex:      dx = ex - px
                elif px >= ex+w: dx = px - (ex + w - 1)
                
                dy = 0
                if py < ey:      dy = ey - py
                elif py >= ey+h: dy = py - (ey + h - 1)

                dist = 0
                valid = False

                if range_type == "*":
                    # 切比雪夫距离: 横向或纵向距离的最大值
                    dist = max(dx, dy)
                    valid = (rmin <= dist <= rmax)
                    
                elif range_type == "+":
                    # 曼哈顿距离
                    dist = dx + dy
                    valid = (rmin <= dist <= rmax)
                    
                elif range_type == "-":
                    # 只能沿直线: 要么dx=0要么dy=0
                    if dx == 0 and dy > 0:
                        dist = dy
                        valid = (rmin <= dist <= rmax)
                    elif dy == 0 and dx > 0:
                        dist = dx
                        valid = (rmin <= dist <= rmax)
                        
                elif range_type == "x":
                    # 斜角, 必须是同色格子
                    if (dx+dy)%2 == 0:
                        dist = (abs(dx - dy)+abs(dx + dy))/2  # 斜角距离的一个合理定义
                        valid = (rmin <= dist <= rmax)
                if valid:
                    positions.add((px, py))
        return list(positions)

    def calc_range_entity_positions(self, entity: GameObject, range_info: Dict[str, Any]) -> List[Tuple[int, int]]:
        """计算以(x,y)为中心，满足range_info条件的有实体格子位置列表"""
        range_positions = self.calc_range_positions(entity, range_info)
        entity_positions = []
        for pos in range_positions:
            if self.get_uid_at(pos) is not None:
                entity_positions.append(pos)
        return entity_positions
    
    def calc_range_entities(self, entity: GameObject, range_info: Dict[str, Any]) -> List[int]:
        """计算以(x,y)为中心，满足range_info条件的有实体格子上的实体列表"""
        range_positions = self.calc_range_positions(entity, range_info)
        entities = set() # 用set去重, 因为一个实体可能占据多个格子
        for pos in range_positions:
            uid = self.get_uid_at(pos)
            if uid is not None:
                entities.add(uid)
        return list(entities)

    # 保证如果ignore_obstacles=True, 则rmin=1且w=h=1, 也即可以直接使用搜索算法计算
    def calc_range_empty_positions(self, entity: GameObject, range_info: Dict[str, Any], ignore_obstacles: bool = False) -> List[Tuple[int, int]]:
        """计算以(x,y)为中心，满足range_info条件的空格子位置列表"""
        empty_positions = []
        if ignore_obstacles:
            range_positions = self.calc_range_positions(entity, range_info)
            for pos in range_positions:
                if self.get_uid_at(pos) is None:
                    empty_positions.append(pos)
            return empty_positions
        else:
            # 如果不忽略障碍物, 则需要在计算范围时考虑实体的阻挡, 因此需要单独实线搜索算法
            # 此时rmin=w=h=1, 因此以实体占据的格子为起点进行搜索即可
            rtype = range_info.get("Type", "*")
            rmax = range_info.get("Max", 1)
            ex = entity.x
            ey = entity.y
            if range_info.get("Min", 1) != 1 or entity.size["Width"] != 1 or entity.size["Height"] != 1:
                raise ValueError("When ignore_obstacles is False, range must have Min=1 and entity size must be 1*1")     
                   
            if rtype == "-":# 直线范围的特殊处理, 只需要在四个方向上扫描即可
                directions = [(1,0), (-1,0), (0,1), (0,-1)]
                for dx, dy in directions:
                    for dist in range(1, rmax + 1):
                        nx, ny = ex + dx * dist, ey + dy * dist
                        if self.out_of_bounds(nx, ny):
                            break
                        if self.get_uid_at(nx, ny) is not None:
                            break # 遇到障碍物停止
                        empty_positions.append((nx, ny))
                return empty_positions

            step_move=[]
            if rtype == "+":
                step_move = [(1,0),(-1,0),(0,1),(0,-1)]
            elif rtype == "*":
                step_move = [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]
            elif rtype == "x":
                step_move = [(1,1),(1,-1),(-1,1),(-1,-1)]
            elif rtype == "h":
                step_move = [(2,1),(2,-1),(-2,1),(-2,-1),(1,2),(1,-2),(-1,2),(-1,-2)]
                if rmax != 1:
                    raise ValueError("Range type 'h' only supports Max=1")
            else:
                raise ValueError(f"Unknown range type: {rtype}")
            
            visited = set()
            def bfs(start):
                queue = [(start, 0)]  # (position, distance)
                visited.add(start)
                while queue:
                    (cx, cy), dist = queue.pop(0)
                    if dist > rmax:
                        continue
                    if self.get_uid_at((cx, cy)) is None and dist >= 1:
                        empty_positions.append((cx, cy))
                    for dx, dy in step_move:
                        nx, ny = cx + dx, cy + dy
                        if not self.out_of_bounds(nx, ny) and (nx, ny) not in visited:
                            if self.get_uid_at((nx, ny)) is None:  # 只有空格子才继续搜索
                                visited.add((nx, ny))
                                queue.append(((nx, ny), dist + 1))
            bfs((ex, ey))
            return empty_positions