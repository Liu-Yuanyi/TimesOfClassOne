from typing import List, Dict, Callable, Any, Tuple, TYPE_CHECKING
from interactions import *
if TYPE_CHECKING:
    from engine import GameEngine, PlayerState
    from entities import GameObject, Unit, Building
    from event import Trigger, Context
    from maps import GameMap


# --- 辅助工具 (Pythonic "Macros") ---

def get_player_id(ctx: "Context", uid :int) -> int:
    """宏替代: 快速获取玩家ID"""
    ent = get_self(ctx, uid)
    return ent.owner_id if ent else None

def get_map(ctx: "Context") -> "GameMap":
    """宏替代: 快速获取当前游戏地图对象"""
    return ctx.engine.game_map

def get_self(ctx: "Context", uid: int) -> "GameObject":
    """宏替代: 快速获取触发该技能的实体对象"""
    return ctx.engine.entities[uid]

def add_resources(ctx: "Context", gold: int, wood: int, player_id: int = None, uid: int = None):
    """宏替代: 给当前玩家增加资源"""
    if player_id is None:
        if uid is not None:
            player_id = get_player_id(ctx, uid)
        else:
            raise ValueError("必须提供 player_id 或 uid 来确定目标玩家")
    if player_id is None:
        raise ValueError("无法确定目标玩家")
    if player_id == 0:
        return # 玩家ID为0表示无效玩家，不执行任何操作
    p : "PlayerState" = ctx.engine.players[player_id]
    p.resources["Gold"] += gold
    p.resources["Wood"] += wood

def affordable(money: Dict[str, int], cost: Dict[str, int]) -> bool:
    """判断玩家是否负担得起某个成本"""
    for res, amount in cost.items():
        if money.get(res, 0) < amount:
            return False
    return True

def affordable_buildings(engine: "GameEngine", player_id:int) -> List[str]:
    """获取玩家负担得起的建筑列表"""
    player = engine.players[player_id]
    cost_list = engine.costlist(player_id)
    return [b for b in player.chosen_buildings if affordable(player.resources, cost_list.get(b, {}))]

def affordable_units(engine: "GameEngine", player_id:int) -> List[str]:
    """获取玩家负担得起的单位列表"""
    player = engine.players[player_id]
    cost_list = engine.costlist(player_id)
    return [u for u in player.chosen_units if affordable(player.resources, cost_list.get(u, {}))]

# --- 技能实现 ---

def Crispy(ctx: "Context", uid: int):
    print("触发技能: 脆皮")
    ctx.value += 1

def SellChick(ctx: "Context", uid: int):
    # 使用辅助函数简化代码
    print("触发技能: 卖鸡")
    add_resources(ctx, gold=100, wood=3, player_id=ctx.source.owner_id)

def Bayonet(ctx: "Context", uid: int):
    if isinstance(ctx.target, Unit):
        print("触发技能: 刺刀")
        ctx.value += 1

#"Description": "多谢@：消耗4血为代价为攻击范围内全体友兵恢复[2][3]血",
# 主动技能的参数是engine和uid，ctx是被动技能才有的参数
def ThankYou(engine: "GameEngine", uid: int):
    me : "Unit" = engine.entities[uid]
    print("触发技能: 多谢@")
    engine.execute_real_damage(me, me, 4, me.position) # 先扣自己血
    heal_amount = 3 if me.promoted else 3
    # 恢复范围内友军血量
    entities = engine.game_map.calc_range_entities(me, engine.calc_attack_range(me))
    for ent_id in entities:
        ent = engine.entities[ent_id]
        if isinstance(ent, Unit) and ent.owner_id == me.owner_id:
            engine.heal(me, ent, heal_amount, me.position)

def Thankyou_check(engine: "Context", uid: int):
    me : "Unit" = engine.entities[uid]
    if me.hp <= 4:
        return False
    return True

# "Description": "吸引:攻击后可与目标交换位置(若其为兵)",
async def Kawaii(ctx: "Context", uid: int):
    engine = ctx.engine
    me : "Unit" = get_self(ctx, uid)
    target = ctx.target
    if not target or target.hp <= 0:
        print("目标无效，无法使用吸引")
        return
    if isinstance(target, Unit):
        # 调用interaction.py 询问玩家是否交换位置
        response = await ask_confirm(ctx.source.owner_id, f"是否与{target.name}交换位置？")
        if response:
            mp , tp = me.position, target.position
            get_map(ctx).swap_entities(me, target)
            print(f"{me.name}吸引了{target.name}，交换了位置！")

def RingAttack (ctx: "Context", uid: int):
    me : "Unit" = get_self(ctx, uid)
    attack = ctx.engine.calc_attack(me)
    if me.vars["正在环击"]["Value"] == 0:
        print("触发技能: 环击")
        me.vars["正在环击"]["Value"] = 1
        entities_in_range = get_map(ctx).calc_range_entities(me, {"Type": "*", "Min": 1, "Max": 1})
        entities_in_range.remove(ctx.target.uid)  # 移除原攻击目标
        for ent_id in entities_in_range:
            ctx.engine.execute_attack(me, get_self(ctx, ent_id), attack)
        me.vars["正在环击"]["Value"] = 0

async def Interroll(engine: "GameEngine", uid: int):
    me : "Unit" = engine.entities[uid]
    print("触发技能: 互卷@")#与范围内的友兵交换位置
    entities_in_range = engine.game_map.calc_range_entities(me, engine.calc_attack_range(me))
    for ent_id in entities_in_range:
        ent= engine.entities[ent_id]
        if ent.uid != me.uid or not isinstance(ent, Unit):
            entities_in_range.remove(ent_id)
    if not entities_in_range:
        raise RuntimeError("范围内没有友兵，无法使用互卷@")
    
    choosable_positions = [engine.entities[ent_id].position for ent_id in entities_in_range]
    choice_pos = await select_location(engine, me.owner_id, choosable_positions, "请选择要交换位置的友兵")

    if choice_pos is None:
        print("取消选择，无法使用互卷@")
        me.vars["互卷@"]["Value"] +=1
        return

    targert_uid = engine.game_map.get_uid_at(choice_pos)
    targert_ent = engine.entities[targert_uid]
    if targert_ent and isinstance(targert_ent, Unit) and targert_ent.owner_id == me.owner_id:
        engine.game_map.swap_entities(me, targert_ent)
        print(f"{me.name}与{targert_ent.name}交换了位置！")

def Interroll_check(engine: "GameEngine", uid: int):
    me : "Unit" = engine.entities[uid]
    entities_in_range = engine.game_map.calc_range_entities(me, engine.calc_attack_range(me))
    friendlies = [ent_id for ent_id in entities_in_range if isinstance(engine.entities[ent_id], Unit) and engine.entities[ent_id].owner_id == me.owner_id and ent_id != me.uid]
    return len(friendlies) > 0

# 裸衣：Q不可回血。Q可以消耗1血量，下回合移动范围变为*4
def Naked(engine: "GameEngine", uid: int):
    me : "Unit" = engine.entities[uid]
    print("触发技能: 裸衣")
    engine.execute_real_damage(me, me, 1, me.position)
    engine.buff_unit(engine.entities[uid], "裸衣", 2)

def Naked_check(engine: "GameEngine", uid: int):
    me : "Unit" = engine.entities[uid]
    return me.hp > 1

def NoHeal(ctx: "Context", uid: int):
    print("触发技能: 不可回血")
    ctx.value = 0

def TearApart(ctx: "Context", uid: int):
    me : "Unit" = get_self(ctx, uid)
    if isinstance(ctx.target, Unit):
        print("触发技能: 撕碎")
        ctx.value += (ctx.target.max_hp - ctx.target.hp) // 2

# 爆浆：死亡后对周围8格造成[6][9]真实伤害，更外16格造成[2][3]伤害，建筑减半向下取整，不分敌我
def Burst(ctx: "Context", uid: int):
    me : "Unit" = get_self(ctx, uid)
    print("触发技能: 爆浆")
    game_map = get_map(ctx)
    inner_entities = game_map.calc_range_entities(me, {"Type": "*", "Min": 1, "Max": 1})
    outer_entities = game_map.calc_range_entities(me, {"Type": "*", "Min": 1, "Max": 2})
    # 除去内圈的部分
    outer_entities = [ent_id for ent_id in outer_entities if ent_id not in inner_entities]

    inner_damage = 9 if me.promoted else 6
    outer_damage = 3 if me.promoted else 2

    for ent_id in inner_entities:
        ent = get_self(ctx, ent_id)
        if isinstance(ent, Building):
            damage = inner_damage // 2
        else:
            damage = inner_damage
        ctx.engine.execute_real_damage(me, ent, damage, ent.pos)
    
    for ent_id in outer_entities:
        ent = get_self(ctx, ent_id)
        if isinstance(ent, Building):
            damage = outer_damage // 2
        else:
            damage = outer_damage
        ctx.engine.execute_real_damage(me, ent, damage, ent.pos)

# 穿透：同时攻击目标与目标身后的单位（不分敌我）
async def Pierce(ctx: "Context", uid: int):
    me : "Unit" = get_self(ctx, uid)
    target = ctx.target
    
    dist = max(abs(me.position[0] - target.position[0]), abs(me.position[1] - target.position[1]))
    if dist != 1:
        return # 只对相邻单位生效
    pierce_pos = (target.position[0]* 2 - me.position[0]), (target.position[1]*2 - me.position[1])
    pierce_uid = ctx.engine.game_map.get_uid_at(pierce_pos[0], pierce_pos[1])
    if pierce_uid is None or pierce_uid == target.uid:
        return # 没有目标或者目标就是穿透位置的单位
    print("触发技能: 穿透")
    new_target = ctx.engine.entities[pierce_uid]
    ctx.engine.execute_attack(me, new_target, ctx.engine.calc_attack(me))

# 狙击：移动后不能攻击
def Snipe(ctx: "Context", uid: int):
    me : "Unit" = get_self(ctx, uid)
    print("触发技能: 狙击")
    me.action_state.Attackable = False

# 抚慰@：为范围内一个友兵恢复[4][6]血
async def Comfort(engine: "GameEngine", uid: int):
    me : "Unit" = engine.entities[uid]
    print("触发技能: 抚慰@")
    entities_in_range = engine.game_map.calc_range_entities(me, engine.calc_attack_range(me))
    friendlies = [ent_id for ent_id in entities_in_range if isinstance(engine.entities[ent_id], Unit) and engine.entities[ent_id].owner_id == me.owner_id]
    if not friendlies:
        print("范围内没有友兵，无法使用抚慰@")
        me.vars["抚慰@"]["Value"] += 1
        return
    
    choosable_positions = [engine.entities[ent_id].position for ent_id in friendlies]
    choice_pos = await select_location(engine, me.owner_id, choosable_positions, "请选择要治疗的友兵")

    if choice_pos is None:
        print("取消选择，无法使用抚慰@")
        me.vars["抚慰@"]["Value"] += 1
        return

    target_uid = engine.game_map.get_uid_at(choice_pos)
    target_ent = engine.entities[target_uid]

    heal_amount = 6 if me.promoted else 4
    engine.heal(me, target_ent, heal_amount, choice_pos)
    print(f"{me.name}治疗了{target_ent.name}！")

# 啊？：目标下回合无法移动(不影响特技和法术)
def Ah(ctx: "Context", uid: int):
    print("触发技能: 啊？")
    ctx.engine.buff_unit(ctx.target, "啊？", 1)

# "Description": "打铁：攻击范围内友兵攻击+1",
# "Skills": {
#     "打铁":{
#         "Type":"PassiveSkill",
#         "Trigger":"CALC_ATTACK",
#         "Effect":"Blacksmith",
#         "Role": "GLOBAL"
#     }
# }
def Blacksmith(ctx: "Context", uid: int):
    me : "Unit" = get_self(ctx, uid)
    if me.owner_id == ctx.source.owner_id:
        entities_in_range = get_map(ctx).calc_range_entities(me, ctx.engine.calc_attack_range(me))
        if ctx.source.uid in entities_in_range:
            print("触发技能: 打铁")
            ctx.value += 1

# 迅捷：每回合可操作两次(释放技能后二次操作)
def Speed(engine: "GameEngine", uid: int):
    me : "Unit" = engine.entities[uid]
    print("触发技能: 迅捷")
    me.action_state.Movable = True
    me.action_state.Attackable = True

def BendOver(ctx: "Context", uid: int):
    me : "Unit" = get_self(ctx, uid)
    print("触发技能: 折腰")
    ctx.value += me.max_hp-me.hp

def NoHaste(ctx: "Context", uid: int):
    me : "Unit" = get_self(ctx, uid)
    print("触发技能: 不可加速")
    ctx.value["Min"]=1
    ctx.value["Max"]=1

async def HealInjury(engine: "GameEngine", uid: int):
    me : "Unit" = engine.entities[uid]
    print("触发技能: 养伤")
    #me.hp = me.max_hp
    await engine.heal(me, me, me.max_hp - me.hp, me.position)
    
def Charm(ctx: "Context", uid: int):
    print("触发技能: 魅惑")
    ctx.engine.buff_unit(ctx.target, "魅惑", 1)

def Umbrella(ctx: "Context", uid: int):
    me : "Unit" = get_self(ctx, uid)
    source = ctx.source
    # 来源在*1以外的伤害最终视为1
    # 计算source和me之间的最短距离, 注意source可能大小比1*1更大
    swidth = source.size.get("Width", 1)
    sheight = source.size.get("Height", 1)
    if source.vertical:
        swidth, sheight = sheight, swidth
    # 计算最短距离(source的坐标在左下角)
    p=[source.pos, (source.pos[0]+swidth-1, source.pos[1]), (source.pos[0], source.pos[1]+sheight-1), (source.pos[0]+swidth-1, source.pos[1]+sheight-1)]
    dist = min(max(abs(me.pos[0]-px), abs(me.pos[1]-py)) for px, py in p)
    if dist > 1:
        print("触发技能: 打伞")
        ctx.value = 1

# 荆棘：反伤[3][5](真实伤害)
async def Thorn(ctx: "Context", uid: int):
    me : "Unit" = get_self(ctx, uid)
    print("触发技能: 荆棘")
    damage = 5 if me.promoted else 3
    ctx.engine.execute_real_damage(me, ctx.source, damage, me.pos)

# 尚文：目标下回合[面板攻击力视为1][无法攻击]
def ShangWen(ctx: "Context", uid: int):
    me : "Unit" = get_self(ctx, uid)
    print("触发技能: 尚文")
    if me.promoted:
        ctx.engine.buff_unit(ctx.target, "尚文2", 1)
    else:
        ctx.engine.buff_unit(ctx.target, "尚文1", 1)

# 领袖@：将*2内的一个友兵传送至边邻处本回合其伤害[+1][+2]
async def Leader(engine: "GameEngine", uid: int):
    me : "Unit" = engine.entities[uid]
    print("触发技能: 领袖@")
    entities_in_range = engine.game_map.calc_range_entities(me, {"Type": "*", "Min": 1, "Max": 2})
    friendlies = [ent_id for ent_id in entities_in_range if isinstance(engine.entities[ent_id], Unit) and engine.entities[ent_id].owner_id == me.owner_id]
    if not friendlies:
        raise RuntimeError("范围内没有友兵，无法使用领袖@")
    
    adjacent_positions = engine.game_map.calc_range_empty_positions(me, {"Type": "+", "Min": 1, "Max": 1})
    if not adjacent_positions:
        raise RuntimeError("没有边邻空格，无法使用领袖@")
    
    choosable_positions = [engine.entities[ent_id].position for ent_id in friendlies]
    choice_pos = await select_location(engine, me.owner_id, choosable_positions, "请选择要传送的友兵")

    if choice_pos is None:
        print("取消选择，无法使用领袖@")
        me.vars["领袖@"]["Value"] += 1
        return
    target_uid = engine.game_map.get_uid_at(choice_pos)
    target_ent = engine.entities[target_uid]
    
    # 传送至边邻
    target_pos = await select_location(engine, me.owner_id, adjacent_positions, "请选择传送目标位置", cancelable=False)
    engine.game_map.move_entity(target_ent, target_pos)

    # 增加伤害
    buff_name = "领袖2" if me.promoted else "领袖1"
    engine.buff_unit(target_ent, buff_name, 1)

def Leader_check(engine: "GameEngine", uid: int):
    me : "Unit" = engine.entities[uid]
    entities_in_range = engine.game_map.calc_range_entities(me, {"Type": "*", "Min": 1, "Max": 2})
    friendlies = [ent_id for ent_id in entities_in_range if isinstance(engine.entities[ent_id], Unit) and engine.entities[ent_id].owner_id == me.owner_id]
    if not friendlies:
        return False
    
    adjacent_positions = engine.game_map.calc_range_empty_positions(me, {"Type": "+", "Min": 1, "Max": 1})
    if not adjacent_positions:
        return False
    
    return True

# "Description": "工程@:修建建筑或为边邻非敌方建筑恢2血;只产生于基地",
# "Skills": {
#     "水平@":{
#         "Type":"ActiveSkill",
#         "Effect":"Engineer_Horizontal",
#         "MoveConflict":true,
#         "AttackConflict":true
#     },
#     "垂直@":{
#         "Type":"ActiveSkill",
#         "Effect":"Engineer_Vertical",
#         "MoveConflict":true,
#         "AttackConflict":true
#     },
#     "修复@":{
#         "Type":"ActiveSkill",
#         "Effect":"Repair",
#         "MoveConflict":true,
#         "AttackConflict":true
#     }
# }

async def Engineer_Horizontal(engine: "GameEngine", uid: int):
    me : "Unit" = engine.entities[uid]
    print("触发技能: 工程@-水平")# 修建一个水平的建筑

    affordable_buildings = affordable_buildings(engine, me.owner_id)
    if not affordable_buildings:
        raise RuntimeError("没有负担得起的建筑，无法使用工程@")

    while True:
        building = await select_chosen_object(engine, me.owner_id, affordable_buildings, "请选择要建造的建筑类型")
        if building is None:
            print("取消选择，无法使用工程@")
            me.vars["水平@"]["Value"] += 1
            return
        
        if engine.game_map.calc_range_entity_positions(me, {"Type": "+", "Min": 1, "Max": 1}) == []:
            raise RuntimeError("没有边邻空格，无法使用工程@")

        # 遍历全图计算可建造的位置, 一个大小为width*height的建筑, 每个占用格现在都必须为空, 且必须至少一个格子与me.pos有公共边, 计算结果为一个List, 每个元素是建筑左下角的坐标

        building_stats = engine.loader.building_stats[building]
        width = building_stats["Size"]["Width"]
        height = building_stats["Size"]["Height"]
        
        valid_positions = []
        for x in range(1, engine.game_map.width - width + 2):
            for y in range(1, engine.game_map.height - height + 2):
                # 检查占用格
                can_build = True
                adjacent_to_me = False
                for dx in range(width):
                    for dy in range(height):
                        pos = (x + dx, y + dy)
                        if engine.game_map.get_uid_at(pos) is not None:
                            can_build = False
                            break
                        if not adjacent_to_me and ((abs(pos[0] - me.position[0]) == 1 and pos[1] == me.position[1]) or (abs(pos[1] - me.position[1]) == 1 and pos[0] == me.position[0])):
                            adjacent_to_me = True
                    if not can_build:
                        break
                if can_build and adjacent_to_me:
                    valid_positions.append((x, y))
        if not valid_positions:
            print("此类建筑没有可建造的位置，请重新选择建筑")
        else:
            break
    choice_pos = await select_location(engine, me.owner_id, valid_positions, "请选择建筑位置")
    if choice_pos is None:
        print("取消选择，无法使用工程@")
        me.vars["水平@"]["Value"] += 1
        return
    
    # 创建建筑
    new_building = engine.spawn_building(building, me.owner_id, choice_pos[0],choice_pos[1], vertical=False)
    cost = engine.costlist(me.owner_id).get(building, {})
    for res, amount in cost.items():
        me.resources[res] -= amount

    print(f"{me.name}建造了{new_building.name}！")
    # 这三个技能其实是一个技能, 因此另外两个也要减少使用次数
    me.vars["垂直@"]["Value"] -= 1
    me.vars["修复@"]["Value"] -= 1

async def Engineer_Vertical(engine: "GameEngine", uid: int):
    me : "Unit" = engine.entities[uid]
    print("触发技能: 工程@-垂直")# 修建一个垂直的建筑
    # 逻辑与水平类似, 只是建筑旋转90度
    a_buildings = affordable_buildings(engine, me.owner_id)
    if not a_buildings:
        raise RuntimeError("没有负担得起的建筑，无法使用工程@")
    while True:
        building = await select_chosen_object(engine, me.owner_id, a_buildings, "请选择要建造的建筑类型")
        if building is None:
            print("取消选择，无法使用工程@")
            me.vars["垂直@"]["Value"] += 1
            return
        
        if engine.game_map.calc_range_entity_positions(me, {"Type": "+", "Min": 1, "Max": 1}) == []:
            raise RuntimeError("没有边邻空格，无法使用工程@")

        building_stats = engine.loader.building_stats[building]
        width = building_stats["Size"]["Width"]
        height = building_stats["Size"]["Height"]
        
        valid_positions = []
        for x in range(1, engine.game_map.width - height + 2):
            for y in range(1, engine.game_map.height - width + 2):
                can_build = True
                adjacent_to_me = False
                for dx in range(height):
                    for dy in range(width):
                        pos = (x + dx, y + dy)
                        if engine.game_map.get_uid_at(pos) is not None:
                            can_build = False
                            break
                        if not adjacent_to_me and ((abs(pos[0] - me.position[0]) == 1 and pos[1] == me.position[1]) or (abs(pos[1] - me.position[1]) == 1 and pos[0] == me.position[0])):
                            adjacent_to_me = True
                    if not can_build:
                        break
                if can_build and adjacent_to_me:
                    valid_positions.append((x, y))
        if not valid_positions:
            print("此类建筑没有可建造的位置，请重新选择建筑")
        else:
            break
    choice_pos = await select_location(engine, me.owner_id, valid_positions, "请选择建筑位置")
    if choice_pos is None:
        print("取消选择，无法使用工程@")
        me.vars["垂直@"]["Value"] += 1
        return
    new_building = engine.spawn_building(building, me.owner_id, choice_pos[0],choice_pos[1], vertical=True)
    cost = engine.costlist(me.owner_id).get(building, {})
    for res, amount in cost.items():
        me.resources[res] -= amount
    print(f"{me.name}建造了{new_building.name}！")
    # 这三个技能其实是一个技能, 因此另外两个也要减少使用次数
    me.vars["水平@"]["Value"] -= 1
    me.vars["修复@"]["Value"] -= 1

def Engineer_check(engine: "GameEngine", uid: int):
    me : "Unit" = engine.entities[uid]
    if engine.game_map.calc_range_entity_positions(me, {"Type": "+", "Min": 1, "Max": 1}) == []:
        return False
    affordable_buildings = affordable_buildings(engine, me.owner_id)
    if not affordable_buildings:
        return False
    return True

def Engineer_Horizontal_check(engine: "GameEngine", uid: int):
    return Engineer_check(engine, uid)
def Engineer_Vertical_check(engine: "GameEngine", uid: int):
    return Engineer_check(engine, uid)

async def Repair(engine: "GameEngine", uid: int):
    me : "Unit" = engine.entities[uid]
    print("触发技能: 工程@-修复")# 为边邻非敌方建筑恢复2血
    adjacent_entities = engine.game_map.calc_range_entities(me, {"Type": "+", "Min": 1, "Max": 1})
    valid_targets = [ent_id for ent_id in adjacent_entities if isinstance(engine.entities[ent_id], Building) and engine.entities[ent_id].owner_id in [me.owner_id, 0] and engine.entities[ent_id].hp < engine.entities[ent_id].max_hp]
    if not valid_targets:
        raise RuntimeError("没有可修复的建筑，无法使用工程@")
    
    choosable_positions = [engine.entities[ent_id].position for ent_id in valid_targets]
    choice_pos = await select_location(engine, me.owner_id, choosable_positions, "请选择要修复的建筑")

    if choice_pos is None:
        print("取消选择，无法使用工程@")
        me.vars["修复@"]["Value"] += 1
        return

    target_uid = engine.game_map.get_uid_at(choice_pos)
    target_ent = engine.entities[target_uid]

    heal_amount = 6 if me.promoted else 4
    engine.heal(me, target_ent, heal_amount, choice_pos)
    print(f"{me.name}修复了{target_ent.name}！")
    # 这三个技能其实是一个技能, 因此都要减少使用次数
    me.vars["水平@"]["Value"] -= 1
    me.vars["垂直@"]["Value"] -= 1

def Repair_check(engine: "GameEngine", uid: int):
    me : "Unit" = engine.entities[uid]
    adjacent_entities = engine.game_map.calc_range_entities(me, {"Type": "+", "Min": 1, "Max": 1})
    valid_targets = [ent_id for ent_id in adjacent_entities if isinstance(engine.entities[ent_id], Building) and engine.entities[ent_id].owner_id in [me.owner_id, 0] and engine.entities[ent_id].hp < engine.entities[ent_id].max_hp]
    return len(valid_targets) > 0

async def ProduceEngineer(engine: "GameEngine", uid: int):
    me : "Unit" = engine.entities[uid]
    print("触发技能: 生产")
    # 生产一个工程兵, 位置在基地(me)边邻的空格里
    adjacent_positions = engine.game_map.calc_range_empty_positions(me, {"Type": "+", "Min": 1, "Max": 1})
    if not adjacent_positions:
        raise RuntimeError("没有边邻空格，无法生产工兵")
    choice_pos = await select_location(engine, me.owner_id, adjacent_positions, "请选择位置", cancelable=False)
    if choice_pos is None:
        print("取消选择，无法使用生产工兵")
        me.vars["生产"]["Value"] += 1
        return

    new_unit = engine.spawn_unit("工兵", me.owner_id, choice_pos[0], choice_pos[1])
    print(f"{me.name}生产了{new_unit.name}！")

def ProduceEngineer_check(engine: "GameEngine", uid: int):
    me : "Unit" = engine.entities[uid]
    adjacent_positions = engine.game_map.calc_range_empty_positions(me, {"Type": "+", "Min": 1, "Max": 1})
    return len(adjacent_positions) > 0

def GoldAndWoodFarm(ctx: "Context", uid: int):
    print("触发技能: 产金木")
    if ctx.engine.current_player_id == get_self(ctx, uid).owner_id:
        add_resources(ctx, gold=100, wood=5, uid = uid) 

def ThornArmor(ctx: "Context", uid: int):
    me : "Unit" = get_self(ctx, uid)
    if me.owner_id == 0:
        print("触发技能: 反伤")
        ctx.engine.execute_real_damage(me, ctx.source, 3, me.pos)

def CaptureBuilding(ctx: "Context", uid: int):
    me : "Unit" = get_self(ctx, uid)
    if me.owner_id == 0:
        if ctx.target.owner_id != 0:
            print("触发技能: 占领")
            me.owner_id = ctx.target.owner_id
            me.hp = me.max_hp
        else: 
            print("[Warning] 还有这事???")
    else:
        print("触发技能: 占领")
        me.owner_id = 3 - me.owner_id
        me.hp = me.max_hp

async def ProduceSoldier(engine: "GameEngine", uid: int):
    # 兵营的技能, 生产一个士兵, 位置在其边邻的空格里
    me : "Building" = engine.entities[uid]
    print("触发技能: 生产士兵")

    a_units = affordable_units(engine, me.owner_id)
    if not a_units:
        raise RuntimeError("没有负担得起的单位，无法使用生产士兵")
    
    unit = await select_chosen_object(engine, me.owner_id, a_units, "请选择要生产的单位类型")

    adjacent_positions = engine.game_map.calc_range_empty_positions(me, {"Type": "+", "Min": 1, "Max": 1})
    if not adjacent_positions:
        raise RuntimeError("没有边邻空格，无法生产士兵")
    
    choice_pos = await select_location(engine, me.owner_id, adjacent_positions, "请选择位置", cancelable=False)
    if choice_pos is None:
        print("取消选择，无法使用生产士兵")
        me.vars["生产士兵"]["Value"] += 1
        return

    new_unit = engine.spawn_unit(unit, me.owner_id, choice_pos[0], choice_pos[1])
    add_resources(engine.players[me.owner_id], gold=-engine.costlist(me.owner_id)[unit]["Gold"], wood=-engine.costlist(me.owner_id)[unit]["Wood"])
    print(f"{me.name}生产了{new_unit.name}！")

def ProduceSoldier_check(engine: "GameEngine", uid: int):
    me : "Building" = engine.entities[uid]
    a_units = affordable_units(engine, me.owner_id)
    if not a_units:
        return False
    adjacent_positions = engine.game_map.calc_range_empty_positions(me, {"Type": "+", "Min": 1, "Max": 1})
    return len(adjacent_positions) > 0

def GoldMine(ctx: "Context", uid: int):
    print("触发技能: 金矿")
    if ctx.engine.current_player_id == get_self(ctx, uid).owner_id:
        add_resources(ctx, gold=50, wood=0, uid=uid)

def WoodFarm(ctx: "Context", uid: int):
    print("触发技能: 伐木场")
    if ctx.engine.current_player_id == get_self(ctx, uid).owner_id:
        add_resources(ctx, gold=0, wood=5, uid=uid)

def DoubleCostPerExistingUnit(ctx: "Context", uid: int):
    me : "Unit" = get_self(ctx, uid)
    if me.owner_id == ctx.engine.current_player_id and ctx.name == me.name:
    # 把ctx.cost翻倍
        for res in ctx.cost:
            print("触发技能: 现有单位双倍成本")
            ctx.cost[res] *= 2

def Neutralize(ctx: "Context", uid: int):
    print("触发技能: 中立")
    me : "Building" = get_self(ctx, uid)
    me.owner_id = 0

# "Description":"对*6范围内的一格造成30真实伤害，并对此格周围八格造成10溅射真实伤害(可以空打) (不分敌我，自己也受)"
async def MissileAttack(engine : "GameEngine", uid: int):
    me : "Building" = engine.entities[uid]
    positions = engine.game_map.calc_range_positions(me, {"Type": "*", "Min": 1, "Max": 6})
    choice_pos = await select_location(engine, me.owner_id, positions, "请选择攻击位置", cancelable=False)
    if choice_pos is None:
        print("取消选择，无法使用导弹攻击")
        me.vars["导弹攻击"]["Value"] += 1
        return
    print("触发技能: 导弹攻击")
    # 计算目标格周围八格的坐标
    adjacent_positions = [(choice_pos[0] + dx, choice_pos[1] + dy) for dx in range(-1, 2) for dy in range(-1, 2) if not (dx == 0 and dy == 0)]
    # 对目标格造成30点真实伤害
    target_uid = engine.game_map.get_uid_at(choice_pos)
    if target_uid is not None:
        target_ent = engine.entities[target_uid]
        engine.execute_real_damage(me, target_ent, 30, choice_pos)
    # 对周围八格造成10溅射真实伤害
    for pos in adjacent_positions:
        uid = engine.game_map.get_uid_at(pos)
        if uid is not None:
            ent = engine.entities[uid]
            engine.execute_real_damage(me, ent, 10, pos)

# 痊愈一个边邻兵
async def HealUnit(engine: "GameEngine", uid: int):
    me : "Building" = engine.entities[uid]
    print("触发技能: 治疗")
    adjacent_entities = engine.game_map.calc_range_entities(me, {"Type": "+", "Min": 1, "Max": 1})
    valid_targets = [ent_id for ent_id in adjacent_entities if isinstance(engine.entities[ent_id], Unit) and engine.entities[ent_id].owner_id == me.owner_id and engine.entities[ent_id].hp < engine.entities[ent_id].max_hp]
    if not valid_targets:
        raise ValueError("没有可治疗的单位")
    
    choosable_positions = [engine.entities[ent_id].position for ent_id in valid_targets]
    choice_pos = await select_location(engine, me.owner_id, choosable_positions, "请选择要治疗的单位")

    if choice_pos is None:
        print("取消选择，无法使用治疗")
        me.vars["治疗"]["Value"] += 1
        return

    target_uid = engine.game_map.get_uid_at(choice_pos)
    target_ent = engine.entities[target_uid]

    heal_amount = target_ent.max_hp - target_ent.hp
    engine.heal(me, target_ent, heal_amount, choice_pos)
    print(f"{me.name}治疗了{target_ent.name}！")
    
def HealUnit_check(engine: "GameEngine", uid: int):
    me : "Building" = engine.entities[uid]
    adjacent_entities = engine.game_map.calc_range_entities(me, {"Type": "+", "Min": 1, "Max": 1})
    valid_targets = [ent_id for ent_id in adjacent_entities if isinstance(engine.entities[ent_id], Unit) and engine.entities[ent_id].owner_id == me.owner_id and engine.entities[ent_id].hp < engine.entities[ent_id].max_hp]
    return len(valid_targets) > 0

# 在黑奴市场边邻四格各召唤一个黑奴(若为空)(冷却1回合)
async def SummonBlackSlaves(engine: "GameEngine", uid: int):
    me : "Building" = engine.entities[uid]
    print("触发技能: 召唤黑奴")
    adjacent_positions = engine.game_map.calc_range_positions(me, {"Type": "+", "Min": 1, "Max": 1})
    summon_positions = []
    for pos in adjacent_positions:
        if engine.game_map.get_uid_at(pos) is None:
            summon_positions.append(pos)
    if not summon_positions:
        raise RuntimeError("没有可召唤的位置，无法使用召唤黑奴")
    if me.vars["黑奴冷却"]["Value"] > 0:
        raise RuntimeError("技能冷却中，无法使用召唤黑奴")
    me.vars["黑奴冷却"]["Value"] = 2
    for pos in summon_positions:
        new_unit = engine.spawn_unit("黑奴", me.owner_id, pos[0], pos[1])
        print(f"{me.name}召唤了{new_unit.name}！")

def SummonBlackSlaves_check(engine: "GameEngine", uid: int):
    me : "Building" = engine.entities[uid]
    if me.vars["黑奴冷却"]["Value"] > 0:
        return False
    adjacent_positions = engine.game_map.calc_range_positions(me, {"Type": "+", "Min": 1, "Max": 1})
    for pos in adjacent_positions:
        if engine.game_map.get_uid_at(pos) is None:
            return True
    return False

