import { createContext, useContext, useEffect, useMemo, useState } from "react";

const en = {
  "nav.today": "Today", "nav.assistant": "Assistant", "nav.foods": "Foods", "nav.recipes": "Recipes", "nav.profile": "Profile",
  "common.save": "Save", "common.cancel": "Cancel", "common.delete": "Delete", "common.remove": "Remove", "common.add": "Add",
  "common.loading": "Loading…", "common.g": "g", "common.meal": "Meal", "common.date": "Date", "common.grams": "Grams",
  "common.today": "Today", "common.back": "Back", "common.edit": "Edit", "common.expand": "Expand", "common.collapse": "Collapse",
  "app.online": "Backend connected", "app.offline": "Backend offline — start the backend server",
  "meal.breakfast": "Breakfast", "meal.lunch": "Lunch", "meal.dinner": "Dinner", "meal.snack": "Snack", "meal.other": "Other",
  "n.energy_kcal": "Energy", "n.protein_g": "Protein", "n.carbohydrate_g": "Carbs", "n.fat_g": "Fat", "n.fibre_g": "Fibre",
  "n.sugars_g": "Sugars", "n.sat_fat_g": "Saturated fat", "n.sodium_mg": "Sodium", "n.calcium_mg": "Calcium",
  "n.iron_mg": "Iron", "n.vitamin_c_mg": "Vitamin C", "n.vitamin_b12_ug": "Vitamin B12",
  "n.ala_g": "Omega-3 ALA", "n.epa_g": "Omega-3 EPA", "n.dha_g": "Omega-3 DHA",
  "n.epa_dha_g": "Omega-3 EPA+DHA", "n.linoleic_g": "Omega-6 linoleic acid", "n.cholesterol_mg": "Cholesterol",
  "n.potassium_mg": "Potassium", "n.magnesium_mg": "Magnesium", "n.phosphorus_mg": "Phosphorus",
  "n.zinc_mg": "Zinc", "n.selenium_ug": "Selenium", "n.iodine_ug": "Iodine",
  "n.vitamin_a_ug": "Vitamin A", "n.vitamin_d_ug": "Vitamin D", "n.vitamin_e_mg": "Vitamin E",
  "n.vitamin_k_ug": "Vitamin K", "n.folate_ug": "Folate",
  "status.ok": "On track", "status.low": "A bit low", "status.deficient": "Too low", "status.excess": "Over",
  "status.unknown": "Data missing", "status.ok_incomplete": "OK so far (data incomplete)",
  "today.eaten": "eaten", "today.target": "Target", "today.remaining": "{n} kcal left", "today.over": "{n} kcal over",
  "today.addAi": "Log with AI", "today.addSearch": "Search foods", "today.empty": "Nothing logged yet",
  "today.emptyHint": "Tell the assistant what you ate, or search the food database.",
  "today.needProfile": "Set up your profile to get daily targets.", "today.setProfile": "Set up profile",
  "today.details": "Nutrient details", "today.intake": "Intake", "today.targetCol": "Target", "today.max": "limit",
  "today.incomplete": "Some foods have no data for this nutrient, so the real total may be higher.",
  "today.entries": "Food log", "today.gramsInvalid": "Enter an amount above 0.",
  "today.estimate": "AI estimate missing values", "today.estimating": "Estimating…",
  "today.estimateHint": "Only fills values the database lacks. Marked as AI predicted.", "today.estimateNone": "Nothing to estimate.",
  "today.estimated": "Estimated {n} value(s).", "today.aiPredicted": "AI predicted", "today.showAll": "Show all nutrients", "today.showCore": "Show main nutrients only", "today.aiNotice": "Some values below are AI estimates, not database data (marked AI predicted). Check them before relying on them.",
  "assistant.modelHint": "Pick a fast model that does not think deeply (e.g. Claude Haiku). Reasoning models are slow.",
  "today.sourcesOf": "Sources of {n}", "today.noSources": "No logged food has data for this yet.",
  "today.sourcesMissing": "{n} food(s) have no data for this, not counted here.",
  "profile.title": "Profile & targets", "profile.age": "Age", "profile.sex": "Sex", "profile.male": "Male", "profile.female": "Female",
  "profile.height": "Height (cm)", "profile.weight": "Weight (kg)", "profile.activity": "Activity level", "profile.goal": "Goal",
  "profile.prefs": "Dietary preferences (comma separated)", "profile.save": "Save profile", "profile.saved": "Saved",
  "profile.targets": "Your daily targets", "profile.how": "How these were calculated",
  "profile.provisional": "These defaults are provisional and not yet checked against an official reference standard.",
  "profile.limit": "limit", "profile.aim": "aim",
  "act.sedentary": "Sedentary", "act.light": "Light", "act.moderate": "Moderate", "act.active": "Active", "act.very_active": "Very active",
  "goal.fat_loss": "Lose fat", "goal.maintenance": "Maintain", "goal.muscle_gain": "Build muscle",
  "foods.featured": "Common foods (per 100 g)", "foods.featuredHint": "Click a row for the full nutrient table. Dashes mean no data, not zero.",
  "cat.all": "All", "cat.staple": "Staples", "cat.protein": "Protein", "cat.dairy": "Dairy & soy", "cat.veg": "Vegetables", "cat.fruit": "Fruit", "cat.fat": "Nuts & fats",
  "col.food": "Food", "col.kcal": "kcal", "col.protein": "Protein g", "col.carbs": "Carbs g", "col.fat": "Fat g", "col.fibre": "Fibre g", "col.sodium": "Sodium mg",
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
  "assistant.confirm": "Confirm and log ({n})", "assistant.discard": "Discard", "edit.hint": "Changes to today's log. Nothing changes until you apply.", "edit.del": "Delete {name} ({old} g)", "edit.grams": "{name}: {old} g → {new} g", "edit.meal": "{name}: {meal_old} → {meal_new}", "edit.apply": "Apply ({n})", "edit.applied": "Changes applied to today's log", "edit.skipped": "Some entries were already gone", "assistant.logged": "Logged to your diary",
  "assistant.discarded": "Discarded", "assistant.saveRecipe": "Also save as a recipe", "assistant.recipeName": "Recipe name",
  "assistant.yield": "Cooked weight (g)", "assistant.eat": "I ate (g)", "assistant.dish": "Home-cooked dish",
  "rec.title": "Diet suggestions", "rec.hint": "Based on what is still short today. Nutrient numbers come from the food database; the AI only proposes foods.",
  "rec.generate": "Suggest what to eat", "rec.regenerate": "Regenerate", "rec.busy": "Thinking…",
  "rec.noShort": "Everything tracked is on target today.", "rec.lacks": "{n} {unit} short", "rec.repeat": "short yesterday too",
  "rec.excess": "Over limit", "rec.unknown": "Missing data (not counted)", "rec.yesterday": "Yesterday short on",
  "rec.stale": "Your intake changed since these were made. Regenerate for current numbers.", "rec.generatedAt": "Generated {when}",
  "rec.none": "No option could be matched. Try again.", "rec.option": "Option", "rec.overBudget": "Over today’s remaining energy",
  "rec.limitWarn": "adds to an over-limit nutrient: {x}",
  "assistant.mealTotal": "Total for this message (before saving)", "assistant.predicted": "AI-predicted", "assistant.sauce": "Sauce / seasoning", "assistant.nutTitle": "Nutrition breakdown",
  "assistant.ingredient": "Ingredient", "assistant.sauceTotal": "Sauces & seasonings", "assistant.wholeDish": "Whole dish",
  "assistant.youEat": "You eat", "assistant.nutNote": "Numbers come from the food database. A dash means an ingredient has no data for that nutrient.",
  "assistant.recipeSaved": "Recipe “{name}” saved", "assistant.working": "Working… {s}s",
  "assistant.settings": "AI provider settings (bring your own key)", "assistant.provider": "Provider", "assistant.model": "Model",
  "assistant.baseUrl": "Base URL", "assistant.apiKey": "API key", "assistant.keySaved": "a key is saved; leave blank to keep it",
  "assistant.removeKey": "Remove key", "assistant.settingsSaved": "Saved", "assistant.keyRemoved": "Key removed",
  "assistant.privacy": "The key is stored only in your local database and sent only to the provider above. Your messages and the food/intake data the assistant looks up are sent to that provider. Nothing else leaves this machine.",
  "basis.grams": "amount you gave", "basis.ml": "1 ml taken as 1 g (approximate)", "basis.portion": "database portion: {x}",
  "basis.estimate": "AI estimate — please check", "basis.default": "no amount given — default 100 g",
  "basis.defaultSmall": "no amount given — default 10 g, please set", "basis.none": "no database match", "basis.predicted": "AI-predicted — please check",
  "status.understanding": "Understanding your message…", "status.matching": "Matching “{arg}” in the food database…",
  "status.thinking": "Thinking…", "status.tool_search_foods": "Searching foods: {arg}", "status.tool_get_food": "Reading food details",
  "status.tool_get_targets": "Reading your targets", "status.tool_get_daily_intake": "Reading intake for {arg}",
  "status.sending": "Sending…",
  "nav.plan": "Meal plan",
  "plan.title": "Weekly meal plan", "plan.generate": "New plan", "plan.start": "Start date", "plan.days": "Days", "plan.meals": "Meals",
  "plan.notes": "Preferences for this plan", "plan.notesPh": "e.g. Chinese home cooking, no beef, I have chicken thighs and broccoli…",
  "plan.go": "Generate", "plan.empty": "No meal plan yet",
  "plan.emptyHint": "Generate a plan that fits your daily targets. The AI suggests the dishes; amounts and nutrition are calculated from the food database.",
  "plan.needProfile": "Set up your profile first — the plan is built around your targets.", "plan.needAi": "Add your AI provider and key in the Assistant settings first.",
  "plan.working": "Generating… {s}s", "plan.delete": "Delete plan", "plan.confirmDelete": "Delete this plan?",
  "plan.logMeal": "Log meal", "plan.logDay": "Log whole day", "plan.logged": "Logged {n} items for {date}", "plan.regen": "Regenerate day",
  "plan.addItem": "Add food", "plan.dropped": "{n} suggested item(s) could not be matched to the database and were skipped.",
  "plan.pending": "This plan is still being generated…", "plan.p": "Protein", "plan.c": "Carbs", "plan.f": "Fat", "plan.kcal": "kcal",
  "plan.hint": "Nutrition is always computed from the database. Amounts are scaled so each day lands near your energy target (within limits).",
  "plan.searchFood": "Search a food (English)…",
  "status.plan_asking": "Asking the AI to plan {arg} day(s)…", "status.plan_day_done": "Planned {arg}",
  "assistant.resuming": "Still working on your last message…",
};

const zh = {
  "nav.today": "今天", "nav.assistant": "AI 助手", "nav.foods": "食物库", "nav.recipes": "我的菜谱", "nav.profile": "个人资料",
  "common.save": "保存", "common.cancel": "取消", "common.delete": "删除", "common.remove": "移除", "common.add": "添加",
  "common.loading": "加载中…", "common.g": "克", "common.meal": "餐次", "common.date": "日期", "common.grams": "克数",
  "common.today": "今天", "common.back": "返回", "common.edit": "编辑", "common.expand": "展开", "common.collapse": "收起",
  "app.online": "后端已连接", "app.offline": "后端未连接，请先启动后端服务",
  "meal.breakfast": "早餐", "meal.lunch": "午餐", "meal.dinner": "晚餐", "meal.snack": "加餐", "meal.other": "其他",
  "n.energy_kcal": "能量", "n.protein_g": "蛋白质", "n.carbohydrate_g": "碳水化合物", "n.fat_g": "脂肪", "n.fibre_g": "膳食纤维",
  "n.sugars_g": "总糖", "n.sat_fat_g": "饱和脂肪", "n.sodium_mg": "钠", "n.calcium_mg": "钙",
  "n.iron_mg": "铁", "n.vitamin_c_mg": "维生素 C", "n.vitamin_b12_ug": "维生素 B12",
  "n.ala_g": "ω-3 α-亚麻酸（ALA）", "n.epa_g": "ω-3 EPA（二十碳五烯酸）", "n.dha_g": "ω-3 DHA（二十二碳六烯酸）",
  "n.epa_dha_g": "ω-3 EPA+DHA（长链）", "n.linoleic_g": "ω-6 亚油酸", "n.cholesterol_mg": "胆固醇",
  "n.potassium_mg": "钾", "n.magnesium_mg": "镁", "n.phosphorus_mg": "磷",
  "n.zinc_mg": "锌", "n.selenium_ug": "硒", "n.iodine_ug": "碘",
  "n.vitamin_a_ug": "维生素 A", "n.vitamin_d_ug": "维生素 D", "n.vitamin_e_mg": "维生素 E",
  "n.vitamin_k_ug": "维生素 K", "n.folate_ug": "叶酸",
  "status.ok": "达标", "status.low": "略低", "status.deficient": "不足", "status.excess": "超标",
  "status.unknown": "数据缺失", "status.ok_incomplete": "暂未超标（数据不全）",
  "today.eaten": "已摄入", "today.target": "目标", "today.remaining": "还可摄入 {n} 千卡", "today.over": "超出 {n} 千卡",
  "today.addAi": "用 AI 记录", "today.addSearch": "搜索食物", "today.empty": "今天还没有记录",
  "today.emptyHint": "告诉 AI 助手你吃了什么，或者在食物库里搜索。",
  "today.needProfile": "先设置个人资料，才能得到每日目标。", "today.setProfile": "去设置",
  "today.details": "营养明细", "today.intake": "摄入", "today.targetCol": "目标", "today.max": "上限",
  "today.incomplete": "部分食物缺少这项营养的数据，实际总量可能更高。",
  "today.entries": "饮食记录", "today.gramsInvalid": "请输入大于 0 的克数。",
  "today.estimate": "AI 估算缺失营养", "today.estimating": "估算中…",
  "today.estimateHint": "只补数据库里没有的值，并标记为 AI 预测。", "today.estimateNone": "没有需要估算的食物。",
  "today.estimated": "已估算 {n} 项。", "today.aiPredicted": "AI预测", "today.showAll": "展开全部营养素", "today.showCore": "收起为主要营养素", "today.aiNotice": "下表部分数值为 AI 估算，并非数据库数据（标有“AI预测”）。请核对后再依赖这些数值。",
  "assistant.modelHint": "建议选快速、不做深度思考的模型（如 Claude Haiku）。推理/思考型模型很慢。",
  "today.sourcesOf": "{n} 的食物来源", "today.noSources": "已记录的食物中没有该营养的数据。",
  "today.sourcesMissing": "{n} 种食物缺少该营养数据，未计入。",
  "profile.title": "个人资料与目标", "profile.age": "年龄", "profile.sex": "性别", "profile.male": "男", "profile.female": "女",
  "profile.height": "身高（cm）", "profile.weight": "体重（kg）", "profile.activity": "活动水平", "profile.goal": "目标",
  "profile.prefs": "饮食偏好（逗号分隔）", "profile.save": "保存资料", "profile.saved": "已保存",
  "profile.targets": "你的每日目标", "profile.how": "计算过程",
  "profile.provisional": "这些默认值是临时参考，尚未与权威标准核对。",
  "profile.limit": "上限", "profile.aim": "目标",
  "act.sedentary": "久坐", "act.light": "轻度活动", "act.moderate": "中度活动", "act.active": "活跃", "act.very_active": "非常活跃",
  "goal.fat_loss": "减脂", "goal.maintenance": "维持体重", "goal.muscle_gain": "增肌",
  "foods.featured": "常见食物(每 100 克)", "foods.featuredHint": "点击一行查看完整营养表。横线表示没有数据，不是 0。",
  "cat.all": "全部", "cat.staple": "主食", "cat.protein": "蛋白质", "cat.dairy": "奶与豆制品", "cat.veg": "蔬菜", "cat.fruit": "水果", "cat.fat": "坚果与油脂",
  "col.food": "食物", "col.kcal": "千卡", "col.protein": "蛋白质 g", "col.carbs": "碳水 g", "col.fat": "脂肪 g", "col.fibre": "纤维 g", "col.sodium": "钠 mg",
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
  "assistant.confirm": "确认并记录（{n}）", "assistant.discard": "放弃", "edit.hint": "以下是对今天记录的修改。点击应用前不会改动记录。", "edit.del": "删除 {name}（{old} 克）", "edit.grams": "{name}：{old} 克 → {new} 克", "edit.meal": "{name}：{meal_old} → {meal_new}", "edit.apply": "应用（{n}）", "edit.applied": "修改已应用到今天的记录", "edit.skipped": "部分记录已不存在", "assistant.logged": "已记入饮食日记",
  "assistant.discarded": "已放弃", "assistant.saveRecipe": "同时保存为菜谱", "assistant.recipeName": "菜谱名称",
  "assistant.yield": "成品重量（克）", "assistant.eat": "我吃了（克）", "assistant.dish": "家常菜",
  "rec.title": "饮食建议", "rec.hint": "根据今天还没达标的营养元素推荐。营养数值来自食物数据库，AI 只负责提出食物。",
  "rec.generate": "生成饮食建议", "rec.regenerate": "重新生成", "rec.busy": "生成中…",
  "rec.noShort": "今天需要关注的营养元素都已达标。", "rec.lacks": "还差 {n} {unit}", "rec.repeat": "昨天也不足",
  "rec.excess": "已超标", "rec.unknown": "数据缺失（未计入）", "rec.yesterday": "昨天不足的",
  "rec.stale": "生成后饮食记录已变化，建议重新生成。", "rec.generatedAt": "生成于 {when}",
  "rec.none": "没有可用的方案，可以重试。", "rec.option": "方案", "rec.overBudget": "超出今天剩余热量",
  "rec.limitWarn": "会加重已超标的：{x}",
  "assistant.mealTotal": "本次记录合计（保存前）", "assistant.predicted": "AI 预测", "assistant.sauce": "酱汁/调料", "assistant.nutTitle": "营养拆解",
  "assistant.ingredient": "食材", "assistant.sauceTotal": "酱汁/调料合计", "assistant.wholeDish": "整道菜",
  "assistant.youEat": "你吃的量", "assistant.nutNote": "营养数值来自食物数据库；“—”表示该食材缺少此项数据。",
  "assistant.recipeSaved": "菜谱“{name}”已保存", "assistant.working": "处理中… {s} 秒",
  "assistant.settings": "AI 服务设置（自带密钥）", "assistant.provider": "服务商", "assistant.model": "模型",
  "assistant.baseUrl": "接口地址", "assistant.apiKey": "API 密钥", "assistant.keySaved": "已保存密钥；留空则保持不变",
  "assistant.removeKey": "移除密钥", "assistant.settingsSaved": "已保存", "assistant.keyRemoved": "密钥已移除",
  "assistant.privacy": "密钥只保存在本机数据库，只会发送给上面选择的服务商。你的消息，以及助手查询到的食物/摄入数据，会发送给该服务商。除此之外没有任何数据离开本机。",
  "basis.grams": "你提供的克数", "basis.ml": "1 毫升按 1 克估算（近似）", "basis.portion": "数据库份量：{x}",
  "basis.estimate": "AI 估算，请核对", "basis.default": "未给出数量，默认 100 克",
  "basis.defaultSmall": "未给出数量，默认 10 克，请自行调整", "basis.none": "数据库中没有匹配", "basis.predicted": "AI 预测，请核对",
  "status.understanding": "正在理解你的话…", "status.matching": "正在匹配“{arg}”…",
  "status.thinking": "思考中…", "status.tool_search_foods": "搜索食物：{arg}", "status.tool_get_food": "读取食物详情",
  "status.tool_get_targets": "读取你的目标", "status.tool_get_daily_intake": "读取 {arg} 的摄入",
  "status.sending": "发送中…",
  "nav.plan": "饮食计划",
  "plan.title": "每周饮食计划", "plan.generate": "新计划", "plan.start": "开始日期", "plan.days": "天数", "plan.meals": "餐次",
  "plan.notes": "这份计划的偏好", "plan.notesPh": "例如：中式家常菜、不吃牛肉、家里有鸡腿和西兰花…",
  "plan.go": "生成", "plan.empty": "还没有饮食计划",
  "plan.emptyHint": "生成一份符合你每日目标的计划。AI 只负责推荐菜品，克数和营养都由食物数据库计算。",
  "plan.needProfile": "请先设置个人资料——计划是围绕你的目标生成的。", "plan.needAi": "请先在“AI 助手”的设置里填写 AI 服务和密钥。",
  "plan.working": "生成中… {s} 秒", "plan.delete": "删除计划", "plan.confirmDelete": "删除这份计划？",
  "plan.logMeal": "记录这一餐", "plan.logDay": "记录整天", "plan.logged": "已把 {n} 项记录到 {date}", "plan.regen": "重新生成这一天",
  "plan.addItem": "添加食物", "plan.dropped": "有 {n} 项推荐在数据库中找不到匹配，已跳过。",
  "plan.pending": "这份计划还在生成中…", "plan.p": "蛋白质", "plan.c": "碳水", "plan.f": "脂肪", "plan.kcal": "千卡",
  "plan.hint": "营养始终由数据库计算。克数会按比例调整，使每天接近你的能量目标（有上下限）。",
  "plan.searchFood": "搜索食物（英文）…",
  "status.plan_asking": "正在请 AI 规划 {arg} 天…", "status.plan_day_done": "已规划 {arg}",
  "assistant.resuming": "仍在处理你上一条消息…",
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
  if (s.startsWith("predicted by AI")) return t("basis.predicted");
  if (s.startsWith("no database match")) return t("basis.none");
  return s;
}
