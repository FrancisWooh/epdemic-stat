# 香港各区疫情统计 Dashboard

基于 Flask + ECharts 构建的香港新冠疫情数据可视化平台，涵盖 2022 年第五波疫情期间 18 个行政区的完整数据。

## 功能

- **疫情总览** — 累计确诊、死亡、康复、死亡率、峰值日期等关键指标
- **每日趋势** — 新增确诊/死亡/康复折线图，含 7 日均线
- **区域对比** — 各区累计确诊、峰值单日、死亡人数、发病率柱状图
- **地图热力** — 按日期和指标展示各区地理分布，支持时间轴播放
- **热力矩阵** — 时间 × 地区的疫情强度热力图
- **趋势预测** — 基于 ARIMA 模型的未来 5 日预测（含置信区间）

## 快速启动

### 方式一：Docker（推荐）

无需安装任何依赖，只需有 Docker Engine：

```bash
docker run -d -p 5000:5000 fancylan/epdemic-stat:latest
```

启动后访问 http://localhost:5000

### 方式二：本地运行

**环境要求：** Python 3.10+

```bash
# 安装依赖
pip install -r requirements.txt

# 启动（开发模式）
python app.py

# 或使用 gunicorn（生产模式）
gunicorn --bind 0.0.0.0:5000 --workers 2 app:app
```

启动后访问 http://localhost:5000

### 方式三：自行构建镜像

```bash
docker build -t epdemic-stat .
docker run -d -p 5000:5000 epdemic-stat
```

## 项目结构

```
├── app.py                          # Flask 后端，提供数据 API
├── templates/
│   └── index.html                  # 前端单页应用
├── static/
│   └── hk_districts.json           # 香港各区 GeoJSON 地图数据
├── 香港各区疫情数据_20250322.xlsx   # 数据源
├── requirements.txt                # Python 依赖
└── Dockerfile                      # 容器构建配置
```

## API 端点

| 端点 | 说明 |
|------|------|
| `GET /api/summary` | 疫情总览关键指标 |
| `GET /api/daily` | 每日新增/累计数据序列 |
| `GET /api/regions` | 各区汇总统计 |
| `GET /api/region_trend` | 前 6 区每日趋势 |
| `GET /api/heatmap` | 时间 × 地区热力矩阵数据 |
| `GET /api/map_data?date=&metric=` | 指定日期和指标的地图数据 |
| `GET /api/district_series?district=` | 指定区的完整时间序列 |
| `GET /api/risk` | 各风险等级每日分布 |
| `GET /api/forecast` | ARIMA 5 日趋势预测 |

## 技术栈

- **后端** — Python 3.10 / Flask / pandas / statsmodels
- **前端** — ECharts 5 / 原生 JavaScript
- **容器** — Docker / Gunicorn
