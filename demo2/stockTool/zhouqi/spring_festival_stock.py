import streamlit as st
import akshare as ak
import pandas as pd
import matplotlib.pyplot as plt
import lunardate
from datetime import datetime, timedelta

# ---- 中文显示设置 ----
plt.rcParams['font.sans-serif'] = ['STHeiti']  # 苹果系统字体
plt.rcParams['axes.unicode_minus'] = False


def get_spring_festival_date(year):
    """使用农历库计算春节日期"""
    try:
        lunar_date = lunardate.LunarDate(year, 1, 1)
        return lunar_date.toSolarDate()
    except ValueError:
        # 处理闰月情况
        lunar_date = lunardate.LunarDate(year, 1, 1, leap=0)
        return lunar_date.toSolarDate()


def get_trade_calendar():

    @st.cache_data(ttl=60 * 60 * 24 * 7)
    def fetch_calendar():
        df = ak.tool_trade_date_hist_sina()
        # 确保日期列为字符串格式
        return df["trade_date"].astype(str).tolist()

    trade_dates = []
    for d in fetch_calendar():
        try:
            # 处理不同日期格式
            if len(d) == 8:
                dt = datetime.strptime(d, "%Y%m%d").date()
            else:
                dt = datetime.strptime(d, "%Y-%m-%d").date()
            trade_dates.append(dt)
        except ValueError as e:
            st.error(f"日期格式解析错误: {d} - {str(e)}")
    return trade_dates


def find_nearest_trade_day(target_date, direction='before'):
    """改进的交易日查找算法"""
    trade_dates = get_trade_calendar()

    # 边界检查
    if not trade_dates:
        return None
    if target_date < trade_dates[0]:
        return None if direction == 'before' else trade_dates[0]
    if target_date > trade_dates[-1]:
        return trade_dates[-1] if direction == 'before' else None

    # 二分查找算法
    left, right = 0, len(trade_dates) - 1
    while left <= right:
        mid = (left + right) // 2
        if trade_dates[mid] < target_date:
            left = mid + 1
        else:
            right = mid - 1

    if direction == 'before':
        return trade_dates[right] if right >= 0 else None
    else:
        return trade_dates[left] if left < len(trade_dates) else None


# ---- 数据获取函数 ----
@st.cache_data
def get_index_data(symbol="sh000001"):
    df = ak.stock_zh_index_daily(symbol=symbol)
    df['date'] = pd.to_datetime(df['date'])
    return df.set_index('date').sort_index()


# ---- 主程序 ----
def main():
    st.title("春节行情分析")

    # 配置参数
    years = range(2015, 2025)
    symbol = "sh000001"

    # 获取数据
    df = get_index_data(symbol)
    results = []

    for year in years:
        try:
            # 获取关键日期
            spring_date = get_spring_festival_date(year)
            prev_day = find_nearest_trade_day(spring_date, 'before')
            next_day = find_nearest_trade_day(spring_date, 'after')
            prev_prev_day = find_nearest_trade_day(prev_day, 'before') if prev_day else None

            # 数据有效性检查
            if not all([prev_day, next_day, prev_prev_day]):
                st.warning(f"跳过 {year} 年：缺少必要交易日数据")
                continue

            # 日期格式统一处理
            date_fmt = "%Y-%m-%d"
            prev_prev_str = prev_prev_day.strftime(date_fmt)
            prev_str = prev_day.strftime(date_fmt)
            next_str = next_day.strftime(date_fmt)

            # 获取收盘价（增加异常捕获）
            try:
                prev_prev_close = df.loc[prev_prev_str, 'close']
                prev_close = df.loc[prev_str, 'close']
                next_close = df.loc[next_str, 'close']
            except KeyError as e:
                st.error(f"数据缺失：{str(e)}")
                continue

            # 计算涨跌幅
            pre_change = (prev_close - prev_prev_close) / prev_prev_close * 100
            post_change = (next_close - prev_close) / prev_close * 100

            results.append({
                "年份": year,
                "节前日期": prev_str,
                "节后日期": next_str,
                "节前涨跌幅 (%)": round(pre_change, 2),
                "节后涨跌幅 (%)": round(post_change, 2)
            })

        except Exception as e:
            st.error(f"处理 {year} 年数据时出错: {str(e)}")
            continue

    if results:
        result_df = pd.DataFrame(results)

        # ---- 可视化部分（保持原有样式） ----
        plt.style.use('ggplot')
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 12), gridspec_kw={'hspace': 0.4})

        # 节前涨跌幅
        pre_colors = ['#ff6b6b' if x >= 0 else '#2ecc71' for x in result_df['节前涨跌幅 (%)']]
        bars1 = ax1.bar(result_df['年份'].astype(str), result_df['节前涨跌幅 (%)'],
                        color=pre_colors, edgecolor='white', width=0.6)
        ax1.set_title("春节前最后交易日涨跌幅", fontsize=14, pad=15)

        # 节后涨跌幅
        post_colors = ['#ff6b6b' if x >= 0 else '#2ecc71' for x in result_df['节后涨跌幅 (%)']]
        bars2 = ax2.bar(result_df['年份'].astype(str), result_df['节后涨跌幅 (%)'],
                        color=post_colors, edgecolor='white', width=0.6)
        ax2.set_title("春节后首交易日涨跌幅", fontsize=14, pad=15)

        # 统一装饰样式
        for ax in [ax1, ax2]:
            ax.tick_params(axis='x', labelrotation=45)
            ax.grid(axis='y', linestyle='--', alpha=0.7)
            ax.spines[['top', 'right']].set_visible(False)
            ax.axhline(0, color='black', linewidth=1)

            # 动态调整Y轴范围
            y_min, y_max = ax.get_ylim()
            buffer = max(abs(y_min), abs(y_max)) * 0.2
            ax.set_ylim(y_min - buffer, y_max + buffer)

        # 数据标签
        for bars, ax in zip([bars1, bars2], [ax1, ax2]):
            for bar in bars:
                yval = bar.get_height()
                vertical_pos = 0.5 if yval >= 0 else -0.8
                color = '#ff4444' if yval >= 0 else '#2ecc71'
                ax.text(bar.get_x() + bar.get_width() / 2,
                        yval + vertical_pos,
                        f"{yval:.1f}%",
                        ha='center',
                        va='bottom' if yval >= 0 else 'top',
                        fontsize=10,
                        color=color,
                        weight='bold')

        plt.tight_layout(pad=3)
        st.pyplot(fig)

        # ---- 数据表格 ----
        st.subheader("历史数据详情")
        styled_df = result_df.style.format({
            "节前涨跌幅 (%)": "{:.2f}%",
            "节后涨跌幅 (%)": "{:.2f}%"
        }).applymap(lambda x: 'color: #ff4444' if x >= 0 else 'color: #2ecc71',
                    subset=["节前涨跌幅 (%)", "节后涨跌幅 (%)"])

        st.dataframe(styled_df, use_container_width=True)


    else:
        st.warning("未获取到有效数据")


if __name__ == "__main__":
    main()