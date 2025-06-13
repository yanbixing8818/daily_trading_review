
import pandas as pd
from datetime import datetime, timedelta
import pywencai


def safe_float(value):
    """Safely convert a value to float, returning 0 if conversion fails"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


# Helper functions
def get_market_data(date):
    """获取指定日期的涨停和跌停数据"""
    try:
        date_str = date.strftime("%Y%m%d")
        limit_up_query = f"{date}涨停，成交金额排序"
        limit_down_query = f"{date}跌停，成交金额排序"
        limit_up_df = pywencai.get(query=limit_up_query, sort_key='成交额', sort_order='desc',  loop=True)
        limit_down_df = pywencai.get(query=limit_down_query, sort_key='成交额', sort_order='desc', loop=True)
        return limit_up_df, limit_down_df
    except Exception as e:
        print(f"获取数据失败: {e}")
        return None, None


def calculate_metrics(limit_up_df, limit_down_df, date):
    """计算市场指标"""
    if limit_up_df is None or limit_down_df is None:
        return {}

    date_str = date.strftime("%Y%m%d")
    metrics = {
        "涨停数量": len(limit_up_df),
        "跌停数量": len(limit_down_df),
        "涨停比": f"{len(limit_up_df)}:{len(limit_down_df)}",
        "封板率": round(
            len(limit_up_df[limit_up_df[f'最新涨跌幅'].apply(safe_float) >= 9.9]) / len(limit_up_df) * 100,
            2) if len(limit_up_df) > 0 else 0,
        "连板率": round(
            len(limit_up_df[limit_up_df[f'连续涨停天数[{date_str}]'].apply(safe_float) > 1]) / len(limit_up_df) * 100,
            2) if len(limit_up_df) > 0 else 0,
    }
    return metrics


def calculate_sentiment(metrics):
    """计算市场情绪指数"""
    if not metrics:
        return 50

    limit_up_count = int(metrics["涨停比"].split(":")[0])
    limit_down_count = int(metrics["涨停比"].split(":")[1])

    sentiment = (
            0.4 * (limit_up_count / (limit_up_count + limit_down_count) * 100) +
            0.3 * metrics["封板率"] +
            0.3 * metrics["连板率"]
    )
    return round(sentiment, 2)


# Main app
def main():
    # Date selection
    today = datetime.now().date()
    default_date = today - timedelta(days=1)  # 默认显示昨天的数据

    # 获取数据
    limit_up_df, limit_down_df = get_market_data(today)

    if limit_up_df is not None and limit_down_df is not None:
        # 计算指标
        metrics = calculate_metrics(limit_up_df, limit_down_df, today)
        sentiment = calculate_sentiment(metrics)

        print(f"市场情绪指数: {sentiment}")



if __name__ == "__main__":
    main()