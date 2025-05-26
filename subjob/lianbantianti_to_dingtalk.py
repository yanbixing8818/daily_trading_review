import pywencai
import pandas as pd
from datetime import datetime, timedelta
import matplotlib
from matplotlib import font_manager
import matplotlib.pyplot as plt
import io
from PIL import Image
import akshare as ak
from core.dingtalk.dingtalk_usage import send_to_dingtalk

# 自动检测并设置可用的中文字体，防止中文缺字
def set_chinese_font():
    font_candidates = ['SimHei', 'Microsoft YaHei', 'STHeiti', 'Arial Unicode MS', 'sans-serif']
    found_font = False
    for font in font_candidates:
        try:
            matplotlib.rcParams['font.sans-serif'] = [font]
            if font_manager.findfont(font, fallback_to_default=False):
                found_font = True
                break
        except Exception:
            continue
    if not found_font:
        matplotlib.rcParams['font.sans-serif'] = ['sans-serif']
    matplotlib.rcParams['axes.unicode_minus'] = False

def get_trade_dates(n=30):
    today = datetime.today().date()
    try:
        trade_cal = ak.tool_trade_date_hist()
        flag_col = 'is_trading_day'
    except Exception:
        trade_cal = ak.tool_trade_date_hist_sina()
        flag_col = None
    if flag_col and flag_col in trade_cal.columns:
        trade_cal = trade_cal[trade_cal[flag_col] == 1]
    if not pd.api.types.is_datetime64_any_dtype(trade_cal['trade_date']):
        trade_cal['trade_date'] = pd.to_datetime(trade_cal['trade_date']).dt.date
    trade_cal = trade_cal[trade_cal['trade_date'] <= today]
    trade_dates = [d.strftime('%Y%m%d') for d in trade_cal['trade_date'].tolist()][-n:]
    return trade_dates

def get_highest_boards(trade_dates):
    highest_boards = []
    highest_names = []
    for d in trade_dates:
        try:
            df = pywencai.get(query=f"{d}涨停，非ST", sort_key='成交金额', sort_order='desc')
            if df is not None and not df.empty:
                col = f'连续涨停天数[{d}]'
                if col in df.columns:
                    max_board = pd.to_numeric(df[col], errors='coerce').max()
                    highest_boards.append(int(max_board) if pd.notnull(max_board) else 0)
                    # 找到所有最高板的股票简称
                    if pd.notnull(max_board):
                        names = df.loc[pd.to_numeric(df[col], errors='coerce') == max_board, '股票简称']
                        highest_names.append('\n'.join(names.astype(str)))
                    else:
                        highest_names.append('')
                else:
                    highest_boards.append(0)
                    highest_names.append('')
            else:
                highest_boards.append(0)
                highest_names.append('')
        except Exception as e:
            highest_boards.append(0)
            highest_names.append('')
    return highest_boards, highest_names

def plot_highest_boards(trade_dates, highest_boards, highest_names):
    fig, ax = plt.subplots(figsize=(16, 7))
    x = range(len(trade_dates))
    ax.plot(x, highest_boards, marker='o', color='orangered', linewidth=2)
    ax.set_title('近30个交易日每日涨停股票最高板数')
    ax.set_xlabel('日期')
    ax.set_ylabel('最高板数')
    ax.set_xticks(x)
    ax.set_xticklabels(trade_dates, rotation=45)
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.set_ylim(bottom=0)
    for i, v in enumerate(highest_boards):
        if highest_names[i]:
            stock_names = highest_names[i].split('\n')
            verticals = []
            for name in stock_names:
                verticals.append('\n'.join(list(name)))
            label = f"{v}\n" + '\n\n'.join(verticals)
        else:
            label = str(v)
        ax.text(i, v, label, ha='center', va='bottom', fontsize=10)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return buf

def send_lianbantianti_to_dingtalk():
    set_chinese_font()
    trade_dates = get_trade_dates(30)
    highest_boards, highest_names = get_highest_boards(trade_dates)
    buf = plot_highest_boards(trade_dates, highest_boards, highest_names)
    # 不保存图片，直接发送到钉钉
    send_to_dingtalk(buf, "近30个交易日每日涨停股票最高板数")

if __name__ == "__main__":
    send_lianbantianti_to_dingtalk()


