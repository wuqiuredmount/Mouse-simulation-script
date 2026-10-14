# AI 答题鼠标助手 (app34141-Mouse simulation script)

面向游戏答题活动：自动识别题目 -> 查固定题库 -> 拟人鼠标点击正确答案。

## 架构

  capture 截图 (mss/pyautogui)
     |
     v
  vision 文字/图标 (OCR / 模板匹配)
     |
     v
  brain 正确答案 (题库 + 匹配)
     |
     v
  action 拟人点击 (贝塞尔轨迹/缓动/过冲)

  一切由 core/engine 状态机驱动

## 目录结构

- config/
  - settings.yaml      全局开关（后端/速度/安全）
  - regions.yaml       屏幕区域（题干/选项坐标）
- data/
  - question_bank.json 固定题库（待填充）
  - assets/            模板图片
- src/
  - capture/   截图
  - vision/    OCR + 模板匹配
  - brain/     题库 + 匹配决策
  - action/    鼠标驱动 + 拟人控制
  - core/      状态机 + 引擎
  - utils/     日志 + 几何
- main.py
- requirements.txt

## 快速开始

1. pip install -r requirements.txt
2. python tools/calibrate.py   鼠标框选校准坐标（见下）
3. python main.py --dry-run   先干跑，确认识别正确
4. python main.py             正式运行

## 学习模式 + 可视化面板（当前主任务）

启动带开关的可视化控制面板：

    python main.py --task learn

面板功能：启动/暂停开关、实时状态、可见元素、执行次数、未知次数，
以及“重新载入规则”“打开规则”按钮。

### 学习进程怎么工作

1. 引擎循环：截图 -> 检测可见模板 -> 匹配规则
2. 命中规则 -> 执行动作（点击/等待）
3. 有可见元素但没有规则匹配 -> 【未知情况】自动暂停，存截图到 data/unknown/
4. 你看截图 + 面板提示，在 config/rules.yaml 写一条新规则
5. 点“重新载入规则” -> 点“继续”

规则文件改动会被引擎自动检测并热加载。

### 抓取开局模板

    python tools/grab_template.py --preset

依次框选：商 / 派遣 / 开始吧 / 确定 / 求助锦囊 / 选项A / 事件图标 / 感叹号 / 宝箱左右。

---

## 丝绸之路自动点击（旧版无学习模式）

规则：屏幕上出现指定按钮时就拟人点击一次。

### 1. 抓取按钮模板

先打开游戏让按钮显示出来，然后运行：

    python tools/grab_template.py --preset

按提示依次框选：开始吧 / 确定 / 求助锦囊 / 选项A / 事件图标 / 感叹号 / 宝箱左右。
保存到 data/assets/。空格键可重新截屏（界面变了就按一下）。

### 2. 运行自动点击

    python main.py --task silkroad --dry-run   # 先干跑，看日志识别对不对
    python main.py --task silkroad             # 正式运行

按钮清单与阈值在 config/silkroad.yaml 里调整。

---

## 坐标校准工具（答题模式用）

运行 python tools/calibrate.py ，屏幕会变暗并提示你依次框选：

1. 题干显示区域
2. 选项 1
3. 选项 2
4. 选项 3
5. 选项 4

按住鼠标左键拖出矩形，松开即确认；按 ESC 取消。完成后坐标自动写入 config/regions.yaml。

注意：先打开游戏并停在答题界面，再运行校准工具。

## 下一步（待办）

- [ ] 填入真实题目到 data/question_bank.json
- [ ] 校准 config/regions.yaml 坐标（可加可视化校准工具）
- [ ] 选择 OCR 后端（中文推荐 PaddleOCR，轻量推荐 Tesseract）
- [ ] 针对游戏引擎选择鼠标后端（DirectInput 游戏用 pydirectinput）

## 安全提示

- 默认开启 failsafe：把鼠标猛甩到屏幕左上角立即中断。
- dry_run 模式只识别不点击，务必先验证。
- 请遵守游戏用户协议，仅用于学习研究。
