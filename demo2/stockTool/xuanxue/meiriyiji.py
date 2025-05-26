import streamlit as st
from datetime import datetime, timedelta
from lunar_python import Lunar
import calendar



def app():

    st.markdown("""
    <style>
    div.day-box {
        border: 1px solid #ddd !important;
        padding: 10px !important;
        min-height: 120px !important;
        border-radius: 5px !important;
        margin: 2px !important;
        background-color: white !important;
    }
    
    div.today {
        background-color: #e8f4ff !important;
        border: 2px solid #2196F3 !important;
    }
    
    div.yi-tag {
        color: #4CAF50 !important;
        font-size: 0.9em !important;
        margin-top: 5px !important;
    }
    
    div.ji-tag {
        color: #f44336 !important;
        font-size: 0.9em !important;
        margin-top: 5px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # 获取月份范围
    selected_month = st.date_input("选择月份",
                                           datetime.now().replace(day=1),
                                           format="YYYY/MM/DD")


    # 生成月历
    def generate_calendar(year, month):
        cal = calendar.Calendar()
        month_days = cal.monthdays2calendar(year, month)

        # 生成日历头
        st.subheader(f"{year}年{month}月")
        cols = st.columns(7)
        days = ["一", "二", "三", "四", "五", "六", "日"]
        for col, day in zip(cols, days):
            col.markdown(f"**{day}**")

        # 生成每日数据
        for week in month_days:
            cols = st.columns(7)
            for i, (day, _) in enumerate(week):
                with cols[i]:
                    if day == 0:
                        st.empty()
                        continue

                    current_date = datetime(year, month, day)
                    lunar = Lunar.fromDate(current_date)
                    yi = lunar.getDayYi() or []
                    ji = lunar.getDayJi() or []

                    # 检查包含交易关键词，可以新增其他关键字，比如开工，XXX等
                    has_yi_trade = any(any(kw in item for kw in ["交易"]) for item in yi)
                    has_ji_trade = any(any(kw in item for kw in ["交易"]) for item in ji)

                    # 构建显示内容
                    day_class = "day-box"
                    if current_date.date() == datetime.now().date():
                        day_class += " today"


                    content = f"""
                    <div class="{day_class}">
                        <div style="font-weight: bold; font-size: 1.2em;">{day}</div>
                        <div style="color: #666; font-size: 0.8em;">
                            {lunar.getMonthInChinese()}月{lunar.getDayInChinese()}
                        </div>
                        {"<div class='yi-tag'>宜交易</div>" if has_yi_trade else "<div class='ji-tag'>忌交易</div>" if has_ji_trade else "" ""}
                      
                    </div>
                    """
                    st.markdown(content, unsafe_allow_html=True)



    generate_calendar(selected_month.year, selected_month.month)


if __name__ == "__main__":
    app()