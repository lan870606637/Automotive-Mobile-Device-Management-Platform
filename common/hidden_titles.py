# -*- coding: utf-8 -*-
"""
100种隐藏称号数据
这些称号只能通过每日转盘抽奖获得，不能在积分商城购买
"""

# 100种隐藏称号列表
HIDDEN_TITLES = [
    # 1-10: 幸运系列
    {"id": "hidden_lucky_01", "name": "🍀 幸运儿", "description": "被幸运女神眷顾的人", "color": "#52c41a", "rarity": "common"},
    {"id": "hidden_lucky_02", "name": "⭐ 幸运星", "description": "闪耀的幸运之星", "color": "#ffd700", "rarity": "rare"},
    {"id": "hidden_lucky_03", "name": "🌟 超级幸运星", "description": "超级幸运的化身", "color": "#ff6b6b", "rarity": "epic"},
    {"id": "hidden_lucky_04", "name": "🎰  jackpot之王", "description": "大奖收割机", "color": "#ff4d4f", "rarity": "legendary"},
    {"id": "hidden_lucky_05", "name": "🎲 骰子之神", "description": "掌控命运的骰子", "color": "#722ed1", "rarity": "legendary"},
    {"id": "hidden_lucky_06", "name": "🎯 命中注定的赢家", "description": "一切都是命中注定", "color": "#eb2f96", "rarity": "epic"},
    {"id": "hidden_lucky_07", "name": "🍀 四叶草守护者", "description": "稀有四叶草的守护者", "color": "#52c41a", "rarity": "rare"},
    {"id": "hidden_lucky_08", "name": "🌈 彩虹尽头的人", "description": "找到了彩虹尽头的宝藏", "color": "#ff7a45", "rarity": "epic"},
    {"id": "hidden_lucky_09", "name": "🎱 黑八奇迹", "description": "一杆清台的奇迹", "color": "#262626", "rarity": "rare"},
    {"id": "hidden_lucky_10", "name": "🎰 老虎机终结者", "description": "让老虎机颤抖的人", "color": "#cf1322", "rarity": "legendary"},
    
    # 11-20: 时间系列
    {"id": "hidden_time_01", "name": "⏰ 时间旅行者", "description": "穿梭于时空之间", "color": "#1890ff", "rarity": "epic"},
    {"id": "hidden_time_02", "name": "🕐 守时达人", "description": "分秒不差的精准", "color": "#52c41a", "rarity": "common"},
    {"id": "hidden_time_03", "name": "⏳ 时光守护者", "description": "守护每一刻美好", "color": "#722ed1", "rarity": "rare"},
    {"id": "hidden_time_04", "name": "🕰️ 钟表匠", "description": "时间的艺术家", "color": "#8c8c8c", "rarity": "common"},
    {"id": "hidden_time_05", "name": "⌛ 沙漏掌控者", "description": "掌控时间的流沙", "color": "#d4b106", "rarity": "rare"},
    {"id": "hidden_time_06", "name": "🌅 黎明使者", "description": "迎接第一缕阳光", "color": "#ffa940", "rarity": "common"},
    {"id": "hidden_time_07", "name": "🌙 夜行者", "description": "在月光下漫步", "color": "#2f54eb", "rarity": "common"},
    {"id": "hidden_time_08", "name": "🕛 午夜精灵", "description": "午夜的神秘访客", "color": "#1d39c4", "rarity": "rare"},
    {"id": "hidden_time_09", "name": "⏱️ 秒表狂人", "description": "与时间赛跑的人", "color": "#f5222d", "rarity": "common"},
    {"id": "hidden_time_10", "name": "📅 万年历", "description": "记住每一个重要日子", "color": "#52c41a", "rarity": "common"},
    
    # 21-30: 自然系列
    {"id": "hidden_nature_01", "name": "🌸 樱花使者", "description": "带来春天的气息", "color": "#eb2f96", "rarity": "common"},
    {"id": "hidden_nature_02", "name": "🌊 海洋之子", "description": "深海的守护者", "color": "#1890ff", "rarity": "rare"},
    {"id": "hidden_nature_03", "name": "🔥 火焰掌控者", "description": "驾驭烈焰的力量", "color": "#ff4d4f", "rarity": "epic"},
    {"id": "hidden_nature_04", "name": "🌍 大地守护者", "description": "守护这片大地", "color": "#52c41a", "rarity": "rare"},
    {"id": "hidden_nature_05", "name": "💨 风之精灵", "description": "随风而行的自由", "color": "#13c2c2", "rarity": "common"},
    {"id": "hidden_nature_06", "name": "⚡ 雷霆之主", "description": "掌控雷电的力量", "color": "#722ed1", "rarity": "epic"},
    {"id": "hidden_nature_07", "name": "❄️ 冰雪女王", "description": "冰封万物的美丽", "color": "#36cfc9", "rarity": "rare"},
    {"id": "hidden_nature_08", "name": "🌵 沙漠行者", "description": "穿越沙漠的勇士", "color": "#d4b106", "rarity": "common"},
    {"id": "hidden_nature_09", "name": "🌲 森林守护者", "description": "守护绿色家园", "color": "#237804", "rarity": "common"},
    {"id": "hidden_nature_10", "name": "🌋 火山探险家", "description": "勇闯火山腹地", "color": "#cf1322", "rarity": "rare"},
    
    # 31-40: 神秘系列
    {"id": "hidden_mystery_01", "name": "👻 幽灵行者", "description": "来无影去无踪", "color": "#8c8c8c", "rarity": "rare"},
    {"id": "hidden_mystery_02", "name": "🔮 预言家", "description": "洞察未来的智者", "color": "#722ed1", "rarity": "epic"},
    {"id": "hidden_mystery_03", "name": "🎭 面具大师", "description": "千面万化的神秘", "color": "#434343", "rarity": "common"},
    {"id": "hidden_mystery_04", "name": "🌙 月影刺客", "description": "月光下的暗影", "color": "#1d39c4", "rarity": "epic"},
    {"id": "hidden_mystery_05", "name": "🔍 真相追寻者", "description": "揭开一切谜团", "color": "#1890ff", "rarity": "common"},
    {"id": "hidden_mystery_06", "name": "📜 古卷守护者", "description": "守护古老的秘密", "color": "#d4b106", "rarity": "rare"},
    {"id": "hidden_mystery_07", "name": "🗝️ 密室逃脱者", "description": "没有能困住我的密室", "color": "#fa8c16", "rarity": "common"},
    {"id": "hidden_mystery_08", "name": "👁️ 天眼通", "description": "洞察一切的双眼", "color": "#13c2c2", "rarity": "epic"},
    {"id": "hidden_mystery_09", "name": "🎪 马戏团之星", "description": "神秘马戏团的明星", "color": "#eb2f96", "rarity": "common"},
    {"id": "hidden_mystery_10", "name": "🃏 王牌魔术师", "description": "变幻莫测的魔术大师", "color": "#262626", "rarity": "legendary"},
    
    # 41-50: 战斗系列
    {"id": "hidden_battle_01", "name": "⚔️ 剑圣", "description": "剑术已达巅峰", "color": "#434343", "rarity": "epic"},
    {"id": "hidden_battle_02", "name": "🛡️ 钢铁卫士", "description": "坚不可摧的防御", "color": "#8c8c8c", "rarity": "rare"},
    {"id": "hidden_battle_03", "name": "🏹 神射手", "description": "百步穿杨的神技", "color": "#52c41a", "rarity": "rare"},
    {"id": "hidden_battle_04", "name": "⚡ 闪电侠", "description": "快如闪电的速度", "color": "#722ed1", "rarity": "epic"},
    {"id": "hidden_battle_05", "name": "🥷 暗影忍者", "description": "暗夜中的杀手", "color": "#262626", "rarity": "epic"},
    {"id": "hidden_battle_06", "name": "🦸 超级英雄", "description": "拯救世界的英雄", "color": "#f5222d", "rarity": "legendary"},
    {"id": "hidden_battle_07", "name": "🐉 屠龙勇士", "description": "击败巨龙的勇士", "color": "#cf1322", "rarity": "legendary"},
    {"id": "hidden_battle_08", "name": "👑 不败王者", "description": "从未失败的王者", "color": "#ffd700", "rarity": "legendary"},
    {"id": "hidden_battle_09", "name": "💪 力量化身", "description": "力量的极致体现", "color": "#fa541c", "rarity": "rare"},
    {"id": "hidden_battle_10", "name": "🎯 一击必杀", "description": "只需一击就能解决战斗", "color": "#ff4d4f", "rarity": "epic"},
    
    # 51-60: 智慧系列
    {"id": "hidden_wisdom_01", "name": "📚 博学者", "description": "学富五车的智者", "color": "#1890ff", "rarity": "common"},
    {"id": "hidden_wisdom_02", "name": "🧠 最强大脑", "description": "智商超群的天才", "color": "#722ed1", "rarity": "epic"},
    {"id": "hidden_wisdom_03", "name": "🔬 科学狂人", "description": "为科学疯狂的探索者", "color": "#13c2c2", "rarity": "rare"},
    {"id": "hidden_wisdom_04", "name": "🎓 博士", "description": "知识的最高殿堂", "color": "#2f54eb", "rarity": "rare"},
    {"id": "hidden_wisdom_05", "name": "📖 图书馆馆长", "description": "掌管无尽的知识", "color": "#8c8c8c", "rarity": "common"},
    {"id": "hidden_wisdom_06", "name": "💡 灵感源泉", "description": "创意永不枯竭", "color": "#ffc53d", "rarity": "common"},
    {"id": "hidden_wisdom_07", "name": "🔭 星空观测者", "description": "探索宇宙的奥秘", "color": "#1d39c4", "rarity": "rare"},
    {"id": "hidden_wisdom_08", "name": "🧮 算盘高手", "description": "心算如飞的能手", "color": "#8c8c8c", "rarity": "common"},
    {"id": "hidden_wisdom_09", "name": "🗿 智慧石像", "description": "沉默中蕴含智慧", "color": "#595959", "rarity": "common"},
    {"id": "hidden_wisdom_10", "name": "🏛️ 大哲学家", "description": "思考人生的真谛", "color": "#434343", "rarity": "rare"},
    
    # 61-70: 财富系列
    {"id": "hidden_wealth_01", "name": "💰 小富翁", "description": "积少成多的智慧", "color": "#d4b106", "rarity": "common"},
    {"id": "hidden_wealth_02", "name": "💎 钻石王老五", "description": "闪耀的财富象征", "color": "#13c2c2", "rarity": "rare"},
    {"id": "hidden_wealth_03", "name": "🏦 银行家", "description": "财富的守护者", "color": "#8c8c8c", "rarity": "common"},
    {"id": "hidden_wealth_04", "name": "🪙 金币收藏家", "description": "收藏每一枚金币", "color": "#ffc53d", "rarity": "common"},
    {"id": "hidden_wealth_05", "name": "👑 财富之王", "description": "财富的终极掌控者", "color": "#ffd700", "rarity": "legendary"},
    {"id": "hidden_wealth_06", "name": "🏴‍☠️ 海盗船长", "description": "寻找失落的宝藏", "color": "#262626", "rarity": "rare"},
    {"id": "hidden_wealth_07", "name": "🎁 礼物达人", "description": "送礼物的艺术家", "color": "#eb2f96", "rarity": "common"},
    {"id": "hidden_wealth_08", "name": "🛍️ 购物狂", "description": "买买买的快乐", "color": "#ff4d4f", "rarity": "common"},
    {"id": "hidden_wealth_09", "name": "💳 黑卡会员", "description": "尊贵的象征", "color": "#262626", "rarity": "epic"},
    {"id": "hidden_wealth_10", "name": "🎰 赌场大亨", "description": "赌场中的传奇", "color": "#cf1322", "rarity": "legendary"},
    
    # 71-80: 美食系列
    {"id": "hidden_food_01", "name": "🍜 拉面达人", "description": "面条的艺术", "color": "#fa8c16", "rarity": "common"},
    {"id": "hidden_food_02", "name": "🍰 甜点大师", "description": "甜蜜的创造者", "color": "#eb2f96", "rarity": "rare"},
    {"id": "hidden_food_03", "name": "🍕 披萨爱好者", "description": "热爱每一口披萨", "color": "#ff7a45", "rarity": "common"},
    {"id": "hidden_food_04", "name": "🍔 汉堡王", "description": "汉堡界的王者", "color": "#fa541c", "rarity": "common"},
    {"id": "hidden_food_05", "name": "🍣 寿司之神", "description": "寿司艺术的巅峰", "color": "#ff4d4f", "rarity": "epic"},
    {"id": "hidden_food_06", "name": "🍺 啤酒达人", "description": "品味人生的苦涩", "color": "#ffc53d", "rarity": "common"},
    {"id": "hidden_food_07", "name": "☕ 咖啡师", "description": "调制完美的咖啡", "color": "#8c8c8c", "rarity": "common"},
    {"id": "hidden_food_08", "name": "🌶️ 辣椒挑战者", "description": "无辣不欢的勇士", "color": "#cf1322", "rarity": "rare"},
    {"id": "hidden_food_09", "name": "🍳 早餐之王", "description": "美好的一天从早餐开始", "color": "#ffc53d", "rarity": "common"},
    {"id": "hidden_food_10", "name": "👨‍🍳 米其林大厨", "description": "顶级美食的创造者", "color": "#ffd700", "rarity": "legendary"},
    
    # 81-90: 动物系列
    {"id": "hidden_animal_01", "name": "🦁 狮子王", "description": "草原上的霸主", "color": "#fa8c16", "rarity": "epic"},
    {"id": "hidden_animal_02", "name": "🦊 狡猾狐狸", "description": "机智过人的代表", "color": "#ff7a45", "rarity": "common"},
    {"id": "hidden_animal_03", "name": "🦅 天空之王", "description": "翱翔天际的自由", "color": "#1890ff", "rarity": "rare"},
    {"id": "hidden_animal_04", "name": "🐉 龙的传人", "description": "传承龙的精神", "color": "#cf1322", "rarity": "legendary"},
    {"id": "hidden_animal_05", "name": "🦉 智慧猫头鹰", "description": "黑夜中的智者", "color": "#722ed1", "rarity": "common"},
    {"id": "hidden_animal_06", "name": "🐺 孤狼", "description": "独来独往的孤傲", "color": "#434343", "rarity": "rare"},
    {"id": "hidden_animal_07", "name": "🦋 蝴蝶效应", "description": "微小改变引发巨大变化", "color": "#eb2f96", "rarity": "common"},
    {"id": "hidden_animal_08", "name": "🐢 长寿龟", "description": "千年王八万年龟", "color": "#52c41a", "rarity": "common"},
    {"id": "hidden_animal_09", "name": "🦈 深海霸主", "description": "海洋中的顶级掠食者", "color": "#13c2c2", "rarity": "rare"},
    {"id": "hidden_animal_10", "name": "🦄 独角兽", "description": "传说中的神秘生物", "color": "#eb2f96", "rarity": "legendary"},
    
    # 91-100: 终极系列
    {"id": "hidden_ultimate_01", "name": "🌟 天选之子", "description": "被上天选中的人", "color": "#ffd700", "rarity": "legendary"},
    {"id": "hidden_ultimate_02", "name": "👑 至尊王者", "description": "至高无上的王者", "color": "#ffd700", "rarity": "legendary"},
    {"id": "hidden_ultimate_03", "name": "🔥 凤凰涅槃", "description": "浴火重生的传奇", "color": "#ff4d4f", "rarity": "legendary"},
    {"id": "hidden_ultimate_04", "name": "⚡ 雷神托尔", "description": "掌控雷霆的神明", "color": "#722ed1", "rarity": "legendary"},
    {"id": "hidden_ultimate_05", "name": "🌌 银河守护者", "description": "守护整个银河系", "color": "#1d39c4", "rarity": "legendary"},
    {"id": "hidden_ultimate_06", "name": "🎆 烟花易冷", "description": "绚烂而短暂的美丽", "color": "#eb2f96", "rarity": "epic"},
    {"id": "hidden_ultimate_07", "name": "🎊 庆典之王", "description": "每一场派对的灵魂", "color": "#ff4d4f", "rarity": "rare"},
    {"id": "hidden_ultimate_08", "name": "🎋 许愿竹", "description": "承载所有愿望", "color": "#52c41a", "rarity": "common"},
    {"id": "hidden_ultimate_09", "name": "🎐 风铃使者", "description": "带来远方的消息", "color": "#13c2c2", "rarity": "common"},
    {"id": "hidden_ultimate_10", "name": "🎁 神秘礼盒", "description": "内含无限惊喜", "color": "#722ed1", "rarity": "legendary"},
]

# 根据稀有度获取称号
def get_titles_by_rarity(rarity: str):
    """根据稀有度获取称号列表"""
    return [t for t in HIDDEN_TITLES if t["rarity"] == rarity]

# 获取随机称号（按稀有度权重）
def get_random_hidden_title():
    """获取随机隐藏称号，考虑稀有度权重"""
    import random
    
    # 稀有度权重
    weights = {
        "common": 50,    # 普通 50%
        "rare": 30,      # 稀有 30%
        "epic": 15,      # 史诗 15%
        "legendary": 5   # 传说 5%
    }
    
    # 按权重选择稀有度
    rarities = list(weights.keys())
    rarity_weights = [weights[r] for r in rarities]
    selected_rarity = random.choices(rarities, weights=rarity_weights, k=1)[0]
    
    # 从选中的稀有度中随机选择一个称号
    titles = get_titles_by_rarity(selected_rarity)
    if titles:
        return random.choice(titles)
    return None

# 根据ID获取称号
def get_hidden_title_by_id(title_id: str):
    """根据ID获取隐藏称号"""
    for title in HIDDEN_TITLES:
        if title["id"] == title_id:
            return title
    return None
