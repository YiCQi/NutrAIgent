import { createContext, useContext, useEffect, useMemo, useState } from "react";

const en = {
  "nav.today": "Today", "nav.assistant": "Assistant", "nav.foods": "Foods", "nav.recipes": "Recipes", "nav.profile": "Profile",
  "common.save": "Save", "common.cancel": "Cancel", "common.delete": "Delete", "common.remove": "Remove", "common.add": "Add",
  "common.loading": "Loading…", "common.g": "g", "common.meal": "Meal", "common.date": "Date", "common.grams": "Grams",
  "common.today": "Today", "common.back": "Back", "common.edit": "Edit",
  "app.online": "Backend connected", "app.offline": "Backend offline — start the backend server",
  "meal.breakfast": "Breakfast", "meal.lunch": "Lunch", "meal.dinner": "Dinner", "meal.snack": "Snack", "meal.other": "Other",
  "n.energy_kcal": "Energy", "n.protein_g": "Protein", "n.carbohydrate_g": "Carbs", "n.fat_g": "Fat", "n.fibre_g": "Fibre",
  "n.sugars_g": "Sugars", "n.sat_fat_g": "Saturated fat", "n.sodium_mg": "Sodium", "n.calcium_mg": "Calcium",
  "n.iron_mg": "Iron", "n.vitamin_c_mg": "Vitamin C", "n.vitamin_b12_ug": "Vitamin B12",
  "status.ok": "On track", "status.low": "A bit low", "status.deficient": "Too low", "status.excess": "Over",
  "status.unknown": "Data missing", "status.ok_incomplete": "OK so far (data incomplete)",
  "today.eaten": "eaten", "today.target": "Target", "today.remaining": "{n} kcal left", "today.over": "{n} kcal over",
  "today.addAi": "Log with AI", "today.addSearch": "Search foods", "today.empty": "Nothing logged yet",
  "today.emptyHint": "Tell the assistant what you ate, or search the food database.",
  "today.needProfile": "Set up your profile to get daily targets.", "today.setProfile": "Set up profile",
  "today.details": "Nutrient details", "today.intake": "Intake", "today.targetCol": "Target", "today.max": "limit",
  "today.incomplete": "Some foods have no data for this nutrient, so the real total may be higher.",
  "today.entries": "Food log",
  "profile.title": "Profile & targets", "profile.age": "Age", "profile.sex": "Sex", "profile.male": "Male", "profile.female": "Female",
  "profile.height": "Height (cm)", "profile.weight": "Weight (kg)", "profile.activity": "Activity level", "profile.goal": "Goal",
  "profile.prefs": "Dietary preferences (comma separated)", "profile.save": "Save profile", "profile.saved": "Saved",
  "profile.targets": "Your daily targets", "profile.how": "How these were calculated",
  "profile.provisional": "These defaults are provisional and not yet checked against an official reference standard.",
  "profile.limit": "limit", "profile.aim": "aim",
  "act.sedentary": "Sedentary", "act.light": "Light", "act.moderate": "Moderate", "act.active": "Active", "act.very_active": "Very active",
  "goal.fat_loss": "Lose fat", "goal.maintenance": "Maintain", "goal.muscle_gain": "Build muscle",
  "foods.title": "Food database", "foods.placeholder": "Search foods in English, e.g. egg, rice, okra…",
  "foods.noMatch": "No matches", "foods.hint": "Food names come from USDA and UK CoFID datasets and are in English.",
  "foods.pick": "Pick a food to see its nutrients", "foods.per100": "Per 100 g", "foods.forN": "For {n} g",
  "foods.noData": "no data", "foods.present": "present, amount unknown", "foods.trace": "trace",
  "foods.portion": "Portion", "foods.pickPortion": "pick…", "foods.log": "Add to log", "foods.logged": "Logged {n} g of {name}",
  "foods.source": "Source", "foods.state": "State", "foods.edible": "Edible portion", "foods.group": "Group",
  "recipes.title": "My recipes", "recipes.new": "New recipe", "recipes.empty": "No recipes yet",
  "recipes.emptyHint": "Tell the assistant about a home-cooked dish, or create one here.",
  "recipes.name": "Recipe name", "recipes.notes": "Notes", "recipes.ingredients": "Ingredients",
  "recipes.addIngredient": "Add ingredient", "recipes.searchIng": "Search an ingredient or seasoning (English)…",
  "recipes.yield": "Cooked weight (g)", "recipes.yieldHint": "Stews lose water. Enter the real cooked weight, or leave empty to use the ingredient total.",
  "recipes.rawTotal": "Ingredient total", "recipes.save": "Save recipe", "recipes.nutrition": "Nutrition per 100 g",
  "recipes.confirmDelete": "Delete this recipe?", "recipes.nIng": "{n} ingredients", "recipes.kcal100": "{n} kcal / 100 g",
  "recipes.missingNote": "A dash means one ingredient has no data for that nutrient.", "recipes.noIng": "Add at least one ingredient",
  "assistant.title": "Assistant", "assistant.new": "New chat", "assistant.confirmDelete": "Delete this conversation?",
  "assistant.placeholder": "Tell me what you ate, or ask a question…", "assistant.notReady": "Add your AI provider and key in Settings first",
  "assistant.hint": "Nutrient numbers always come from the food database, never from the AI.",
  "assistant.try1": "I had two eggs, a banana and coffee with milk for breakfast",
  "assistant.try2": "I cooked braised pork ribs for dinner and ate a bowl of rice",
  "assistant.try3": "How is my protein today?",
  "assistant.recognised": "Recognised {n} item(s). Review the matches and amounts below, then confirm.",
  "assistant.check": "Check before saving — nothing is saved yet", "assistant.youSaid": "You said",
  "assistant.matched": "Matched food (change if wrong)", "assistant.noMatch": "No match — add it from Foods",
  "assistant.confirm": "Confirm and log ({n})", "assistant.discard": "Discard", "assistant.logged": "Logged to your diary",
  "assistant.discarded": "Discarded", "assistant.saveRecipe": "Also save as a recipe", "assistant.recipeName": "Recipe name",
  "assistant.yield": "Cooked weight (g)", "assistant.eat": "I ate (g)", "assistant.dish": "Home-cooked dish",
  "assistant.recipeSaved": "Recipe “{name}” saved", "assistant.working": "Working… {s}s",
  "assistant.settings": "AI provider settings (bring your own key)", "assistant.provider": "Provider", "assistant.model": "Model",
  "assistant.baseUrl": "Base URL", "assistant.apiKey": "API key", "assistant.keySaved": "a key is saved; leave blank to keep it",
  "assistant.removeKey": "Remove key", "assistant.settingsSaved": "Saved", "assistant.keyRemoved": "Key removed",
  "assistant.privacy": "The key is stored only in your local database and sent only to the provider above. Your messages and the food/intake data the assistant looks up are sent to that provider. Nothing else leaves this machine.",
  "basis.grams": "amount you gave", "basis.ml": "1 ml taken as 1 g (approximate)", "basis.portion": "database portion: {x}",
  "basis.estimate": "AI estimate — please check", "basis.default": "no amount given — default 100 g",
  "basis.defaultSmall": "no amount given — default 10 g, please set", "basis.none": "no database match",
  "status.understanding": "Understanding your message…", "status.matching": "Matching “{arg}” in the food database…",
  "status.thinking": "Thinking…", "status.tool_search_foods": "Searching foods: {arg}", "status.tool_get_food": "Reading food details",
  "status.tool_get_targets": "Reading your targets", "status.tool_get_daily_intake": "Reading intake for {arg}",
  "status.sending": "Sending…",
};

const zh = {
  "nav.today": "今天", "nav.assistant": "AI 助手", "nav.foods": "食物库", "nav.recipes": "我的菜谱", "nav.profile": "个人资料",
  "common.save": "保存", "common.cancel": "取消", "common.delete": "删除", "common.remove": "移除", "common.add": "添加",
  "common.loading": "加载中…", "common.g": "克", "common.meal": "餐次", "common.date": "日期", "common.grams": "克数",
  "common.today": "今天", "common.back": "返回", "common.edit": "编辑",
  "app.online": "后端已连接", "app.offline": "后端未连接，请先启动后端服务",
  "meal.breakfast": "早餐", "meal.lunch": "午餐", "meal.dinner": "晚餐", "meal.snack": "加餐", "meal.other": "其他",
  "n.energy_kcal": "能量", "n.protein_g": "蛋白质", "n.carbohydrate_g": "碳水化合物", "n.fat_g": "脂肪", "n.fibre_g": "膳食纤维",
  "n.sugars_g": "总糖", "n.sat_fat_g": "饱和脂肪", "n.sodium_mg": "钠", "n.calcium_mg": "钙",
  "n.iron_mg": "铁", "n.vitamin_c_mg": "维生素 C", "n.vitamin_b12_ug": "维生素 B12",
  "status.ok": "达标", "status.low": "略低", "status.deficient": "不足", "status.excess": "超标",
  "status.unknown": "数据缺失", "status.ok_incomplete": "暂未超标（数据不全）",
  "today.eaten": "已摄入", "today.target": "目标", "today.remaining": "还可摄入 {n} 千卡", "today.over": "超出 {n} 千卡",
  "today.addAi": "用 AI 记录", "today.addSearch": "搜索食物", "today.empty": "今天还没有记录",
  "today.emptyHint": "告诉 AI 助手你吃了什么，或者在食物库里搜索。",
  "today.needProfile": "先设置个人资料，才能得到每日目标。", "today.setProfile": "去设置",
  "today.details": "营养明细", "today.intake": "摄入", "today.targetCol": "目标", "today.max": "上限",
  "today.incomplete": "部分食物缺少这项营养的数据，实际总量可能更高。",
  "today.entries": "饮食记录",
  "profile.title": "个人资料与目标", "profile.age": "年龄", "profile.sex": "性别", "profile.male": "男", "profile.female": "女",
  "profile.height": "身高（cm）", "profile.weight": "体重（kg）", "profile.activity": "活动水平", "profile.goal": "目标",
  "profile.prefs": "饮食偏好（逗号分隔）", "profile.save": "保存资料", "profile.saved": "已保存",
  "profile.targets": "你的每日目标", "profile.how": "计算过程",
  "profile.provisional": "这些默认值是临时参考，尚未与权威标准核对。",
  "profile.limit": "上限", "profile.aim": "目标",
  "act.sedentary": "久坐", "act.light": "轻度活动", "act.moderate": "中度活动", "act.active": "活跃", "act.very_active": "非常活跃",
  "goal.fat_loss": "减脂", "goal.maintenance": "维持体重", "goal.muscle_gain": "增肌",
  "foods.title": "食物库", "foods.placeholder": "用英文搜索食物，例如 egg、rice、okra…",
  "foods.noMatch": "没有匹配的食物", "foods.hint": "食物名称来自 USDA 和英国 CoFID 数据集，均为英文。",
  "foods.pick": "选择一种食物查看营养", "foods.per100": "每 100 克", "foods.forN": "{n} 克",
  "foods.noData": "无数据", "foods.present": "含有，含量未知", "foods.trace": "微量",
  "foods.portion": "份量", "foods.pickPortion": "选择…", "foods.log": "加入记录", "foods.logged": "已记录 {n} 克 {name}",
  "foods.source": "来源", "foods.state": "状态", "foods.edible": "可食部分", "foods.group": "分类",
  "recipes.title": "我的菜谱", "recipes.new": "新建菜谱", "recipes.empty": "还没有菜谱",
  "recipes.emptyHint": "告诉 AI 助手你做的家常菜，或者在这里手动创建。",
  "recipes.name": "菜谱名称", "recipes.notes": "备注", "recipes.ingredients": "食材",
  "recipes.addIngredient": "添加食材", "recipes.searchIng": "搜索食材或调料（英文）…",
  "recipes.yield": "成品重量（克）", "recipes.yieldHint": "炖煮会掉水。可填写实际成品重量；留空则等于食材总重。",
  "recipes.rawTotal": "食材总重", "recipes.save": "保存菜谱", "recipes.nutrition": "每 100 克营养",
  "recipes.confirmDelete": "删除这个菜谱？", "recipes.nIng": "{n} 种食材", "recipes.kcal100": "{n} 千卡 / 100 克",
  "recipes.missingNote": "“—”表示有食材缺少该营养的数据。", "recipes.noIng": "至少添加一种食材",
  "assistant.title": "AI 助手", "assistant.new": "新对话", "assistant.confirmDelete": "删除这个对话？",
  "assistant.placeholder": "告诉我你吃了什么，或者直接提问…", "assistant.notReady": "请先在“设置”里填写 AI 服务和密钥",
  "assistant.hint": "营养数值始终来自食物数据库，而不是 AI 的估算。",
  "assistant.try1": "早餐吃了两个鸡蛋、一根香蕉，还有一杯加牛奶的咖啡",
  "assistant.try2": "晚上做了红烧排骨，配了一碗米饭",
  "assistant.try3": "我今天蛋白质够吗？",
  "assistant.recognised": "识别到 {n} 项。请核对匹配的食物和克数，然后确认。",
  "assistant.check": "保存前请核对——目前尚未保存", "assistant.youSaid": "你说的",
  "assistant.matched": "匹配的食物（不对可更换）", "assistant.noMatch": "没有匹配——请到食物库手动添加",
  "assistant.confirm": "确认并记录（{n}）", "assistant.discard": "放弃", "assistant.logged": "已记入饮食日记",
  "assistant.discarded": "已放弃", "assistant.saveRecipe": "同时保存为菜谱", "assistant.recipeName": "菜谱名称",
  "assistant.yield": "成品重量（克）", "assistant.eat": "我吃了（克）", "assistant.dish": "家常菜",
  "assistant.recipeSaved": "菜谱“{name}”已保存", "assistant.working": "处理中… {s} 秒",
  "assistant.settings": "AI 服务设置（自带密钥）", "assistant.provider": "服务商", "assistant.model": "模型",
  "assistant.baseUrl": "接口地址", "assistant.apiKey": "API 密钥", "assistant.keySaved": "已保存密钥；留空则保持不变",
  "assistant.removeKey": "移除密钥", "assistant.settingsSaved": "已保存", "assistant.keyRemoved": "密钥已移除",
  "assistant.privacy": "密钥只保存在本机数据库，只会发送给上面选择的服务商。你的消息，以及助手查询到的食物/摄入数据，会发送给该服务商。除此之外没有任何数据离开本机。",
  "basis.grams": "你提供的克数", "basis.ml": "1 毫升按 1 克估算（近似）", "basis.portion": "数据库份量：{x}",
  "basis.estimate": "AI 估算，请核对", "basis.default": "未给出数量，默认 100 克",
  "basis.defaultSmall": "未给出数量，默认 10 克，请自行调整", "basis.none": "数据库中没有匹配",
  "status.understanding": "正在理解你的话…", "status.matching": "正在匹配“{arg}”…",
  "status.thinking": "思考中…", "status.tool_search_foods": "搜索食物：{arg}", "status.tool_get_food": "读取食物详情",
  "status.tool_get_targets": "读取你的目标", "status.tool_get_daily_intake": "读取 {arg} 的摄入",
  "status.sending": "发送中…",
};

const DICT = { en, zh };
const Ctx = createContext(null);

function initialLang() {
  try {
    const s = localStorage.getItem("lang");
    if (s === "en" || s === "zh") return s;
  } catch {}
  return (navigator.language || "").toLowerCase().startsWith("zh") ? "zh" : "en";
}

export function I18nProvider({ children }) {
  const [lang, setLang] = useState(initialLang);
  useEffect(() => {
    try { localStorage.setItem("lang", lang); } catch {}
    document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
  }, [lang]);
  const value = useMemo(() => {
    const t = (key, vars) => {
      let s = DICT[lang][key] ?? DICT.en[key] ?? key;
      if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v));
      return s;
    };
    return { lang, setLang, t, nutrient: (code) => t(`n.${code}`) };
  }, [lang]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useI18n = () => useContext(Ctx);

// Translate the backend's English "grams_basis" text.
export function basisLabel(t, s) {
  if (!s) return "";
  if (s.startsWith("stated in grams")) return t("basis.grams");
  if (s.startsWith("1 ml")) return t("basis.ml");
  if (s.startsWith("database portion: ")) return t("basis.portion", { x: s.slice("database portion: ".length) });
  if (s.startsWith("typical weight")) return t("basis.estimate");
  if (s.startsWith("no amount given (default 10 g")) return t("basis.defaultSmall");
  if (s.startsWith("default 100 g")) return t("basis.default");
  if (s.startsWith("no database match")) return t("basis.none");
  return s;
}
