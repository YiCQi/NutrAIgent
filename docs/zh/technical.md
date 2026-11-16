# 技术说明

面向开发者，以及想了解 NutrAIgent 工作原理的人。使用方法见 [README](../../README.md)。

## 架构

- **后端：** Python 3.11+、FastAPI、SQLite（一个本地文件）。代码在 `backend/app/`。
- **前端：** React + Vite。构建到 `frontend/dist/`，由后端提供，整个应用只用一个端口。
- **营养计算：** 确定性的 Python 代码（`backend/app/engine/`）。目标和合计由代码计算，AI 不参与。
- **AI 助手：** `backend/app/ai/`。包括服务商适配、食物解析（`nllog.py`）、食物匹配（`aliases.py`、`matching.py`）、问答用的工具式代理（`agent.py`）。
- **餐单规划：** `backend/app/planner.py`。AI 提出食物和克数，后端查询营养素，并把全天按能量目标等比例调整。
- **后台任务：** `backend/app/jobs.py`。即使关闭浏览器标签页，聊天回复和餐单生成仍会继续完成。

## 食物数据

| 来源 | 版本 | 食物数 | 许可 |
|---|---|---|---|
| 英国 CoFID（McCance and Widdowson） | 2021 | 2,887 | Open Government Licence v3.0 |
| 美国 USDA FoodData Central，SR Legacy | 2018-04 | 7,793 | CC0 |
| 美国 USDA FoodData Central，Foundation Foods | 2026-10-29（JSON） | 424 | CC0 |

- 不同来源的食物不会合并，搜索时同一种食物可能出现多次。
- 已存储的营养素：能量、蛋白质、碳水化合物、脂肪、膳食纤维、糖、饱和脂肪、钠、钙、铁、维生素 C、维生素 B12。其他营养素暂未跟踪。
- 数值均为每 100 g（CoFID 中的酒类为每 100 ml，未做换算）。

### 缺失数据不等于零

| 原始数据 | 存储为 |
|---|---|
| 空白或无记录 | 缺失（显示为"无数据"） |
| CoFID `N`（存在但无可靠数值） | 缺失 |
| CoFID `Tr`（微量） | 0，并标记为微量 |
| 实测的 `0` | 0 |

合计时，缺失值不会被当作 0 计入。

### 导入数据

数据库初始为空。导入脚本读取你自行下载的原始文件（这些文件不在仓库中，见 [README](../../README.md#3-导入食物数据仅一次)）。

```
backend/scripts/import_cofid.py            [--xlsx 文件] [--db 路径]
backend/scripts/import_usda_sr_legacy.py   [--raw 目录]  [--db 路径]
backend/scripts/import_usda_foundation.py  [--json 文件] [--db 路径]
```

- 每个脚本只替换自己对应的数据来源，因此可以重复运行。
- 默认数据库：`~/.nutraigent/nutraigent.db`（Windows：`C:\Users\<用户名>\.nutraigent\nutraigent.db`）。可通过环境变量 `NUTRAIGENT_DB` 或参数 `--db` 修改。

## 目标计算（临时）

以下为目标值的默认计算方法。**尚未与官方参考标准核对**，应用中会标注为临时值。

- **基础代谢（BMR）：** Mifflin-St Jeor 公式。
- **活动系数：** 1.2 至 1.9，按活动水平取值。
- **能量：** 减脂 -20 %，维持 0 %，增肌 +10 %（相对于 TDEE）。
- **蛋白质：** 1.8 g/kg（减脂、增肌）；1.0 g/kg（维持）。
- **脂肪：** 占能量的 30 %。
- **饱和脂肪：** 最多占能量的 10 %。
- **膳食纤维：** 30 g。
- **钠：** 最多 2,400 mg。

微量营养素目标尚未实现。个人资料页会显示计算过程。

## AI 助手

### 设置

使用自备密钥（BYOK）。支持的服务商类型：

- **Anthropic**（Claude 模型）。
- **OpenAI 兼容接口**：OpenAI、OpenRouter、Ollama、LM Studio 等。需填写 Base URL 和模型名。

如需添加新服务商，可在 `backend/app/ai/providers.py`（`REGISTRY`）中添加。

### 发送的内容与存储方式

- 你的聊天文本，以及回复所需的食物搜索结果或当日摄入数据，会发送给你所选的服务商。
- API 密钥和服务商设置以**明文**存储在本地 SQLite 数据库中。密钥不会返回给浏览器。请勿在共用电脑上使用。
- 只有在你点击提案卡片上的**确认**后，记录才会保存。

### 记录流程

1. 模型一次性从你的文字中提取条目（食物名、数量、餐次、日期）。
2. 后端将每个条目匹配到数据库，并查询份量。营养素数值不由模型提供。
3. 应用显示提案卡片。你可以更换食物、修改克数或餐次，或取消勾选某些条目。
4. 点击**确认**保存。复合菜肴可连同配料一起保存为食谱。

## 开发者命令

```
.\start.ps1               如需则构建前端，并在 8100–8199 中第一个空闲端口运行应用
.\start.ps1 -Dev          后端（8100–8199 自动选择）与带热更新的 Vite 开发服务器（5173）
.\start.ps1 -Port 9000 -NoBrowser
```

测试：

```
cd backend
.venv\Scripts\python -m pytest
```

前端构建：

```
cd frontend
npm run build
```

环境变量：

- `NUTRAIGENT_DB`：SQLite 数据库路径。
- `NUTRAIGENT_API`：Vite 开发代理使用的后端地址。

仅在 Windows 上测试过 `start.bat` 和 `start.ps1`。macOS 和 Linux 用户可在 `backend/` 目录下用 `uvicorn app.main:app` 运行后端，用 `npm run build` 构建前端；该方式未经测试。

## 路线图

1. ~~MVP：个人资料、食物数据库、目标、每日记录。~~ 已完成。
2. ~~AI 助手：自备密钥、自然语言记录、问答。~~ 已完成。
3. ~~餐单规划。~~ 基础版已完成。待做：根据实际摄入调整计划、购物清单、每周汇总。
4. 进阶：趋势分析、自适应建议、更多营养素。

## 原则

科学准确优先于 AI 假设。数据来源可追溯。本地优先保护隐私。模块化设计。
