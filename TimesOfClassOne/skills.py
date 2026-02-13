from typing import List, Dict, Callable, Any, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from engine import GameEngine, PlayerState
    from entities import GameObject, Unit, Building
    from event import Trigger, Context
    from maps import GameMap

# --- 辅助工具 (Pythonic "Macros") ---

def get_player(ctx: "Context") -> "PlayerState":
    """宏替代: 快速获取触发该技能的玩家对象"""
    return ctx.engine.players[ctx.source.owner_id]

def get_map(ctx: "Context") -> "GameMap":
    """宏替代: 快速获取当前游戏地图对象"""
    return ctx.engine.game_map

def get_self(ctx: "Context", uid: int) -> "GameObject":
    """宏替代: 快速获取触发该技能的实体对象"""
    return ctx.engine.entities[uid]

def add_resources(ctx: "Context", gold: int = 0, wood: int = 0):
    """宏替代: 给当前玩家增加资源"""
    p = get_player(ctx)
    p.gold += gold
    p.wood += wood

# --- 技能实现 ---

def Crispy(ctx: "Context", uid: int):
    print("触发技能: 脆皮")
    ctx.value += 1

def SellChick(ctx: "Context", uid: int):
    # 使用辅助函数简化代码
    print("触发技能: 卖鸡")
    add_resources(ctx, gold=100, wood=3)

def Bayonet(ctx: "Context", uid: int):

    if isinstance(ctx.target, Unit):
        print("触发技能: 刺刀")
        ctx.value += 1

# #"Description": "多谢@：消耗4血为代价为攻击范围内全体友兵恢复[2][3]血",
# def ThankYou(ctx: "Context", uid: int):
#     engine = ctx.engine
#     me : "Unit" = get_self(ctx, uid)
#     if me.hp <= 4:
#         print("血量不足，无法使用技能")
#         me.vars["ThankYou"]["Value"]+=1
#     else:
#         print("触发技能: 多谢@")
#         me.hp -= 4
#         # 恢复范围内友军血量
#         game_map = get_map(ctx)
#         entities = game_map.calc_range_entities(me, engine.calc_attack_range(me))
#         for ent_id in entities:
#             ent = get_self(ctx, ent_id)
#             if isinstance(ent, Unit) and ent.owner_id == me.owner_id:
#                 engine.heal(me, ent, ctx.value, me.position)

# "Description": "吸引:攻击后可与目标交换位置(若其为兵)",
def Kawaii(ctx: "Context", uid: int):
    engine = ctx.engine
    me : "Unit" = get_self(ctx, uid)
    target = ctx.target
    if not target or target.hp <= 0:
        print("目标无效，无法使用吸引")
        return
    if isinstance(target, Unit):
        # 交换位置
        mp , tp = me.position, target.position
        get_map(ctx).swap_entities(me, target)
        print(f"{me.name}吸引了{target.name}，交换了位置！")
