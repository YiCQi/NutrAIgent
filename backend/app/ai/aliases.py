"""Curated alias table: common wordings (Chinese/English) -> a specific database search query.

Why: free-text matching alone picks odd entries (rice -> glutinous rice, broccoli -> broccoli raab).
Each value is a search query (tokens must all start words in the food name) that the ranker then
resolves, so a missing exact name degrades to normal search instead of failing.
Keys are matched against the user's label and the model's first search term: exact match first,
otherwise the longest key contained in the label (Chinese only; English needs an exact match).
Assumptions are deliberate and visible here: e.g. 豆奶 -> sweetened, 豆浆 -> unsweetened.
"""

ALIASES: dict[str, str] = {}


def _add(keys: str, query: str) -> None:
    for k in keys.split("|"):
        ALIASES[k.strip().lower()] = query


# staples
_add("米饭|大米饭|白米饭|白饭|蒸米饭|rice|white rice|steamed rice|cooked rice|boiled rice", "rice white long-grain regular enriched cooked")
_add("糙米饭|糙米|brown rice", "rice brown long-grain cooked")
_add("糯米饭|糯米|glutinous rice|sticky rice", "rice white glutinous cooked")
_add("面条|面|挂面|拉面|noodles|wheat noodles|chinese noodles", "pasta cooked enriched without added salt")
_add("意面|意大利面|pasta|spaghetti", "pasta cooked enriched without added salt")
_add("鸡蛋面|egg noodles", "noodles egg enriched cooked")
_add("馒头|花卷|steamed bun|mantou", "bread white commercially prepared")  # proxy: no steamed-bun entry in CoFID/USDA
_add("面包|白面包|bread|white bread", "bread white commercially prepared")
_add("全麦面包|whole wheat bread|wholemeal bread", "bread whole-wheat commercially prepared")
_add("燕麦|燕麦片|oats|rolled oats|oatmeal", "oats whole grain rolled old fashioned")
_add("土豆|马铃薯|potato|potatoes", "potatoes boiled cooked in skin flesh without salt")
_add("红薯|地瓜|番薯|sweet potato", "sweet potato cooked baked in skin flesh without salt")
_add("玉米|sweet corn|corn", "corn sweet yellow cooked boiled drained without salt")
_add("山药|yam|chinese yam", "yam cooked boiled drained or baked without salt")
# eggs, dairy, soy
_add("鸡蛋|水煮蛋|煮鸡蛋|白煮蛋|egg|eggs|boiled egg|hard-boiled egg", "egg whole cooked hard-boiled")
_add("煎蛋|荷包蛋|炒鸡蛋|fried egg", "egg whole cooked fried")
_add("牛奶|全脂牛奶|milk|whole milk", "milk whole 3.25% milkfat")
_add("脱脂牛奶|低脂牛奶|skim milk|low fat milk", "milk nonfat fluid")
_add("酸奶|yogurt|yoghurt", "yogurt plain whole milk")
_add("豆浆|unsweetened soy milk", "soy milk unsweetened plain")
_add("豆奶|soy milk|soya milk", "soy milk sweetened plain")
_add("豆腐|tofu", "tofu firm")
_add("奶酪|芝士|cheese", "cheese cheddar")
# meat, fish
_add("鸡胸肉|鸡胸|chicken breast", "chicken broilers or fryers breast meat only cooked roasted")
_add("鸡腿|鸡腿肉|chicken thigh|chicken leg", "chicken broilers or fryers thigh meat only cooked roasted")
_add("鸡肉|chicken", "chicken broilers or fryers meat only cooked roasted")
_add("猪里脊|里脊|pork loin", "pork fresh loin separable lean only cooked roasted")
_add("猪肉|瘦猪肉|pork", "pork fresh loin separable lean only cooked roasted")
_add("五花肉|pork belly", "pork fresh belly raw")
_add("排骨|猪排骨|spareribs|pork ribs", "pork fresh spareribs separable lean and fat cooked braised")
_add("牛肉|瘦牛肉|beef", "beef round top round separable lean only trimmed to 0 fat cooked braised")
_add("牛排|steak|beef steak", "beef loin top loin steak separable lean only trimmed to 0 fat cooked broiled")
_add("羊肉|lamb|mutton", "lamb leg whole shank and sirloin separable lean only cooked roasted")
_add("三文鱼|鲑鱼|salmon", "fish salmon atlantic farmed cooked dry heat")
_add("鱼|白鱼|cod", "fish cod atlantic cooked dry heat")
_add("虾|虾仁|shrimp|prawn", "crustaceans shrimp cooked")
_add("培根|bacon", "pork cured bacon cooked pan-fried")
_add("火腿|ham", "ham sliced regular")
# vegetables
_add("西兰花|西蓝花|broccoli", "broccoli cooked boiled drained without salt")
_add("菠菜|spinach", "spinach cooked boiled drained without salt")
_add("白菜|大白菜|chinese cabbage", "cabbage chinese pe-tsai cooked boiled drained without salt")
_add("青菜|小白菜|上海青|pak choi|bok choy", "cabbage chinese pak-choi cooked boiled drained without salt")
_add("卷心菜|包菜|圆白菜|cabbage", "cabbage cooked boiled drained without salt")
_add("胡萝卜|carrot|carrots", "carrots cooked boiled drained without salt")
_add("西红柿|番茄|tomato|tomatoes", "tomatoes red ripe raw year round average")
_add("黄瓜|cucumber", "cucumber with peel raw")
_add("秋葵|okra", "okra cooked boiled drained without salt")
_add("茄子|eggplant|aubergine", "eggplant cooked boiled drained without salt")
_add("青椒|甜椒|彩椒|bell pepper|green pepper", "peppers sweet green raw")
_add("洋葱|onion|onions", "onions raw")
_add("蘑菇|香菇|mushroom|mushrooms", "mushrooms white cooked boiled drained without salt")
_add("四季豆|豆角|青豆|green beans|string beans", "beans snap green cooked boiled drained without salt")
_add("芹菜|celery", "celery cooked boiled drained without salt")
_add("生菜|lettuce", "lettuce cos or romaine raw")
_add("冬瓜|winter melon", "waxgourd chinese preserving cooked boiled drained without salt")
_add("莲藕|藕|lotus root", "lotus root cooked boiled drained without salt")
_add("萝卜|白萝卜|radish|daikon", "radishes oriental cooked boiled drained without salt")
_add("南瓜|pumpkin", "pumpkin cooked boiled drained without salt")
_add("蒜|大蒜|garlic", "garlic raw")
_add("姜|生姜|ginger", "ginger root raw")
_add("葱|大葱|小葱|spring onion|scallion", "onions spring or scallions raw")
# fruit
_add("苹果|apple", "apples raw")
_add("香蕉|banana", "bananas raw")
_add("橙子|橘子|橙|orange", "oranges raw all commercial varieties")
_add("葡萄|grapes|grape", "grapes red or green raw")
_add("草莓|strawberry|strawberries", "strawberries raw")
_add("西瓜|watermelon", "watermelon raw")
_add("梨|pear", "pears raw")
_add("桃子|桃|peach", "peaches yellow raw")
_add("芒果|mango", "mangos raw")
_add("猕猴桃|奇异果|kiwi", "kiwifruit green raw")
_add("蓝莓|blueberries|blueberry", "blueberries raw")
# nuts, oils, seasonings, drinks
_add("花生|peanuts|peanut", "peanuts all types dry-roasted without salt")
_add("核桃|walnut|walnuts", "nuts walnuts english")
_add("杏仁|almonds|almond", "nuts almonds")
_add("花生油|peanut oil", "oil peanut salad or cooking")
_add("食用油|植物油|菜籽油|大豆油|cooking oil|vegetable oil", "oil soybean salad or cooking")
_add("橄榄油|olive oil", "oil olive salad or cooking")
_add("香油|麻油|芝麻油|sesame oil", "oil sesame salad or cooking")
_add("猪油|lard", "lard")
_add("黄油|butter", "butter without salt")
_add("酱油|生抽|老抽|soy sauce", "soy sauce made from soy and wheat shoyu")
_add("盐|食盐|salt", "salt table")
_add("糖|白糖|砂糖|冰糖|sugar|white sugar", "sugars granulated")
_add("蚝油|oyster sauce", "sauce oyster")
_add("醋|米醋|白醋|vinegar", "vinegar distilled")
_add("蜂蜜|honey", "honey")
_add("料酒|黄酒|cooking wine", "alcoholic beverage wine cooking")
_add("番茄酱|番茄沙司|ketchup", "catsup")
_add("咖啡|黑咖啡|coffee", "beverages coffee brewed prepared with tap water")
_add("茶|绿茶|红茶|tea", "beverages tea green brewed regular")
