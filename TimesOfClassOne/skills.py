from typing import List, Dict, Callable, Any, Tuple, TYPE_CHECKING
from functools import wraps
if TYPE_CHECKING:
    from .engine import GameEngine
    from .event import Trigger, Context
# --- 注册机制 ---

# 技能注册表: 技能名 -> [(触发时机, 处理函数)]
SKILL_REGISTRY: Dict[str, List[Tuple[Trigger, Callable]]] = {}

def skill(name: str, trigger: Trigger):
    """
    装饰器: 将函数注册为特定技能在特定时机的回调
    """
    def decorator(func):
        if name not in SKILL_REGISTRY:
            SKILL_REGISTRY[name] = []
        SKILL_REGISTRY[name].append((trigger, func))
        
        @wraps(func)
        async def wrapper(ctx: Context):
            # 这里可以添加通用的技能检查逻辑，例如"被沉默时不触发"
            return await func(ctx)
        return wrapper
    return decorator

# --- 技能实现示例 ---

# 1. [军团]: 同时召唤3个 (触发时机: 生成时 ON_SPAWN)
# Docs: 骷髅,K,...,"军团：同时召唤3个"
@skill("军团", Trigger.ON_SPAWN)
async def skill_legion(ctx: Context):
    unit = ctx.source
    engine = ctx.engine
    
    # 防止无限递归: 只有主单位触发，生成的衍生物不应该再次触发
    # 也可以检查 unit.name 是否是 "骷髅"
    if getattr(unit, "is_summoned", False):
        return

    print(f"[{unit.name}] 发动技能 [军团]!")
    
    # 在周围寻找空位召唤 2 个额外的骷髅
    # 注意: 这里逻辑简化，实际需要计算周围空闲坐标
    targets = [
        (unit.x + 1, unit.y), 
        (unit.x - 1, unit.y), 
        (unit.x, unit.y + 1),
        (unit.x, unit.y - 1)
    ]
    
    count = 0
    for tx, ty in targets:
        if count >= 2: break
        if engine.game_map.is_valid(tx, ty) and engine.game_map.get_entity(tx, ty) is None:
            # 召唤代码，假设 engine 有 spawn_unit
            new_unit = await engine.spawn_unit(unit.name, unit.owner_id, tx, ty, promoted=False)
            new_unit.is_summoned = True # 标记为衍生物
            count += 1

# 2. [脆皮]: 受伤+1 (触发时机: 计算受到伤害 CALC_DAMAGE 或 ON_DAMAGE_TAKEN)
# Docs: 小土豆,...,"脆皮：受伤+1"
# 这里选择 CALC_DAMAGE 阶段修改数值，这是一个同步事件，通常不需要 async，
# 也可以兼容 async (EventBus 已支持)
@skill("脆皮", Trigger.CALC_DAMAGE)
async def skill_brittle(ctx: Context):
    # ctx.target 是受击者
    if ctx.target == ctx.source:
        ctx.value += 1
        print(f"[{ctx.source.name}] [脆皮] 触发: 受到伤害 +1")

# 3. [卖鸡]: 死亡时返还100金3木 (触发时机: ON_DEATH)
# Docs: 鸡男,...,"卖鸡：死亡时返还100金3木"
@skill("卖鸡", Trigger.ON_DEATH)
async def skill_sell_chicken(ctx: Context):
    unit = ctx.source
    engine = ctx.engine
    player = engine.players[unit.owner_id]
    
    print(f"[{unit.name}] [卖鸡] 触发: 返还资源")
    player.gold += 100
    player.wood += 3
    # 可以在这里做一些特效通知 UI

# 4. [荆棘]: 反伤 (触发时机: ON_DAMAGE_TAKEN)
# Docs: 金吉,...,"荆棘：反伤[3][5]"
@skill("荆棘", Trigger.ON_DAMAGE_TAKEN)
async def skill_thorns(ctx: Context):
    defender = ctx.target  # 受伤的人 (金吉)
    attacker = ctx.source  # 攻击者
    
    # 只有被攻击且攻击者还在场时反伤
    if defender == ctx.source: return # 自己打自己不算? ctx.source通常是造成伤害的人
    # 修正逻辑: ON_DAMAGE_TAKEN 中: source=attacker, target=victim
    
    if attacker and defender and attacker != defender:
        damage = 5 if defender.promoted else 3
        print(f"[{defender.name}] [荆棘] 触发: 反伤 {damage}")
        
        # 造成真实伤害 (直接扣血，不触发 CALC_DAMAGE 护甲计算)
        attacker.hp -= damage
        
        # 也要做死亡检查 (这里简化，建议封装 engine.apply_true_damage)
        if attacker.hp <= 0:
            await ctx.engine.event_bus.async_emit(Trigger.ON_DEATH, Context(ctx.engine, source=attacker, target=defender)) 
