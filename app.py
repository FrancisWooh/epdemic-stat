from flask import Flask, jsonify, render_template, send_file, request
import pandas as pd
import math
import os

app = Flask(__name__)

def load_data():
    df = pd.read_excel("香港各区疫情数据_20250322.xlsx")
    df["报告日期"] = pd.to_datetime(df["报告日期"])
    return df

DF = load_data()

def clean(series):
    result = []
    for v in series:
        if v is None:
            result.append(None)
        elif isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            result.append(None)
        elif hasattr(v, 'item'):
            result.append(v.item())
        else:
            result.append(v)
    return result

def get_daily():
    daily = DF.groupby("报告日期").agg(
        新增确诊=("新增确诊", "sum"),
        累计确诊=("累计确诊", "sum"),
        新增死亡=("新增死亡", "sum"),
        累计死亡=("累计死亡", "sum"),
        新增康复=("新增康复", "sum"),
    ).reset_index().sort_values("报告日期")
    daily["7日均线"]    = daily["新增确诊"].rolling(7, center=True).mean().round(1)
    daily["死亡7日均线"] = daily["新增死亡"].rolling(7, center=True).mean().round(2)
    daily["康复7日均线"] = daily["新增康复"].rolling(7, center=True).mean().round(1)
    daily["报告日期"]   = daily["报告日期"].dt.strftime("%Y-%m-%d")
    return daily


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/static/hk_districts.json")
def geojson():
    return send_file("static/hk_districts.json", mimetype="application/json")


@app.route("/api/summary")
def api_summary():
    daily = get_daily()
    peak_idx = int(daily["新增确诊"].idxmax())
    total = int(daily["累计确诊"].iloc[-1])
    total_death = int(daily["累计死亡"].iloc[-1])
    return jsonify({
        "total_confirmed": total,
        "total_death":     total_death,
        "total_recovered": int(daily["新增康复"].sum()),
        "death_rate":      round(total_death / total * 100, 2) if total else 0,
        "peak_daily":      int(daily["新增确诊"].max()),
        "peak_date":       daily.loc[peak_idx, "报告日期"],
        "date_start":      daily["报告日期"].iloc[0],
        "date_end":        daily["报告日期"].iloc[-1],
        "total_days":      len(daily),
        "regions":         int(DF["地区名称"].nunique()),
    })


@app.route("/api/daily")
def api_daily():
    daily = get_daily()
    return jsonify({
        "dates":             daily["报告日期"].tolist(),
        "new_cases":         clean(daily["新增确诊"]),
        "cumulative":        clean(daily["累计确诊"]),
        "ma7":               clean(daily["7日均线"]),
        "new_deaths":        clean(daily["新增死亡"]),
        "death_ma7":         clean(daily["死亡7日均线"]),
        "cumulative_deaths": clean(daily["累计死亡"]),
        "new_recovered":     clean(daily["新增康复"]),
        "recovered_ma7":     clean(daily["康复7日均线"]),
    })


@app.route("/api/regions")
def api_regions():
    region_cum   = DF.groupby("地区名称")["累计确诊"].max()
    region_peak  = DF.groupby("地区名称")["新增确诊"].max()
    region_death = DF.groupby("地区名称")["累计死亡"].max()
    region_pop   = DF.groupby("地区名称")["人口"].first()
    region_rate  = (region_cum / region_pop * 100000).round(1)
    order = region_cum.sort_values(ascending=False).index.tolist()
    return jsonify({
        "names":          order,
        "cumulative":     [int(region_cum[n])    for n in order],
        "peak_daily":     [int(region_peak[n])   for n in order],
        "deaths":         [int(region_death[n])  for n in order],
        "incidence_rate": [float(region_rate[n]) for n in order],
        "population":     [int(region_pop[n])    for n in order],
    })


@app.route("/api/region_trend")
def api_region_trend():
    top6 = DF.groupby("地区名称")["累计确诊"].max().nlargest(6).index.tolist()
    dates = sorted(DF["报告日期"].unique())
    date_strs = [d.strftime("%Y-%m-%d") for d in dates]
    series = {}
    for region in top6:
        sub = DF[DF["地区名称"] == region].set_index("报告日期")["新增确诊"]
        series[region] = [int(sub.get(d, 0)) for d in dates]
    return jsonify({"dates": date_strs, "regions": top6, "series": series})


@app.route("/api/risk")
def api_risk():
    risk_trend = (
        DF.groupby(["报告日期", "风险等级"])
          .size()
          .unstack(fill_value=0)
          .reset_index()
    )
    risk_trend["报告日期"] = risk_trend["报告日期"].dt.strftime("%Y-%m-%d")
    result = {"dates": risk_trend["报告日期"].tolist()}
    for level in ["低风险", "中风险", "高风险"]:
        result[level] = risk_trend[level].tolist() if level in risk_trend.columns else [0] * len(risk_trend)
    return jsonify(result)


@app.route("/api/heatmap")
def api_heatmap():
    pivot = DF.pivot_table(
        index="地区名称", columns="报告日期",
        values="新增确诊", aggfunc="sum", fill_value=0,
    )
    pivot.columns = pivot.columns.strftime("%Y-%m-%d")
    regions = pivot.index.tolist()
    dates   = pivot.columns.tolist()
    data = [
        [di, ri, int(pivot.iat[ri, di])]
        for ri in range(len(regions))
        for di in range(len(dates))
        if pivot.iat[ri, di] > 0
    ]
    return jsonify({"regions": regions, "dates": dates, "data": data})


@app.route("/api/map_dates")
def api_map_dates():
    """Return all available dates and the per-district stats for each."""
    dates = sorted(DF["报告日期"].dt.strftime("%Y-%m-%d").unique().tolist())
    return jsonify({"dates": dates})


@app.route("/api/map_data")
def api_map_data():
    """
    Return per-district values for a given date and metric.
    Also returns per-district time-series for the sparkline popup.
    Query params: date (YYYY-MM-DD), metric (新增确诊|累计确诊|新增死亡|累计死亡|发病率)
    """
    date   = request.args.get("date")
    metric = request.args.get("metric", "新增确诊")

    valid_metrics = {"新增确诊", "累计确诊", "新增死亡", "累计死亡", "发病率(每10万人)"}
    if metric == "发病率":
        metric = "发病率(每10万人)"
    if metric not in valid_metrics:
        metric = "新增确诊"

    if date:
        try:
            target = pd.to_datetime(date)
            df_day = DF[DF["报告日期"] == target]
        except Exception:
            df_day = pd.DataFrame()
    else:
        df_day = DF[DF["报告日期"] == DF["报告日期"].max()]

    result = []
    for _, row in df_day.iterrows():
        v = row[metric]
        result.append({
            "name":        row["地区名称"],
            "value":       round(float(v), 2) if not math.isnan(float(v)) else 0,
            "新增确诊":    int(row["新增确诊"]),
            "累计确诊":    int(row["累计确诊"]),
            "新增死亡":    int(row["新增死亡"]),
            "累计死亡":    int(row["累计死亡"]),
            "风险等级":    row["风险等级"],
            "发病率":      round(float(row["发病率(每10万人)"]), 2),
            "人口":        int(row["人口"]),
        })
    return jsonify(result)


@app.route("/api/district_series")
def api_district_series():
    """Time-series for a specific district (for popup sparkline)."""
    district = request.args.get("district", "")
    df_d = DF[DF["地区名称"] == district].sort_values("报告日期")
    if df_d.empty:
        return jsonify({"dates": [], "新增确诊": [], "累计确诊": [], "新增死亡": []})
    return jsonify({
        "dates":   df_d["报告日期"].dt.strftime("%Y-%m-%d").tolist(),
        "新增确诊": clean(df_d["新增确诊"]),
        "累计确诊": clean(df_d["累计确诊"]),
        "新增死亡": clean(df_d["新增死亡"]),
        "风险等级": df_d["风险等级"].tolist(),
    })


@app.route("/api/forecast")
def api_forecast():
    try:
        from statsmodels.tsa.arima.model import ARIMA
        import warnings
        warnings.filterwarnings('ignore')

        daily = get_daily()
        series = daily["新增确诊"].values.astype(float)

        model = ARIMA(series, order=(5, 1, 5))
        fit = model.fit()

        fc = fit.get_forecast(steps=5)
        mean = fc.predicted_mean
        ci = fc.conf_int(alpha=0.05)

        last_date = pd.to_datetime(daily["报告日期"].iloc[-1])
        future_dates = [
            (last_date + pd.Timedelta(days=i + 1)).strftime("%Y-%m-%d")
            for i in range(5)
        ]

        import numpy as np
        ci_arr = ci.values if hasattr(ci, 'values') else np.array(ci)

        forecast_vals = [max(0.0, round(float(v), 1)) for v in mean]
        lower_vals    = [max(0.0, round(float(v), 1)) for v in ci_arr[:, 0]]
        upper_vals    = [max(0.0, round(float(v), 1)) for v in ci_arr[:, 1]]

        return jsonify({
            "forecast_dates": future_dates,
            "forecast": forecast_vals,
            "lower":    lower_vals,
            "upper":    upper_vals,
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
