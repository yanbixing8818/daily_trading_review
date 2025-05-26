import pywencai
import pandas as pd
from datetime import datetime
import streamlit as st
import requests
import base64
import urllib.parse
import time
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from chinese_calendar import is_workday
import sys
import matplotlib.pyplot as plt
import matplotlib
import plotly.graph_objects as go
import plotly.io as pio
import numpy as np
from matplotlib import cm
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'sans-serif']
matplotlib.rcParams['axes.unicode_minus'] = False

# 企业内部应用参数
APPKEY = 'dingdh0hnt40b7eqyivc'
APPSECRET = 'eXbAsAG5HRYMNFW4x3ffL1kSLepZcldVfyEeiSvsuhb5js_foSRZHtOtXrWo_5_f'
CHATID = 'chat9652245847eebc05ee9e1a1fea02ceda'  # 你的目标群chatid

def get_access_token(appkey, appsecret):
    url = f"https://oapi.dingtalk.com/gettoken?appkey={appkey}&appsecret={appsecret}"
    resp = requests.get(url)
    data = resp.json()
    if data.get('errcode', 0) != 0:
        raise Exception(f"获取access_token失败: {data}")
    return data["access_token"]

def upload_image_to_dingtalk(access_token, image_path):
    url = f"https://oapi.dingtalk.com/media/upload?access_token={access_token}&type=image"
    with open(image_path, 'rb') as f:
        files = {'media': f}
        res = requests.post(url, files=files)
    data = res.json()
    if data.get('errcode', 0) != 0:
        raise Exception(f"上传图片失败: {data}")
    return data["media_id"]

def send_image_to_group(access_token, chatid, media_id):
    url = f"https://oapi.dingtalk.com/chat/send?access_token={access_token}"
    data = {
        "chatid": chatid,
        "msg": {
            "msgtype": "image",
            "image": {
                "media_id": media_id
            }
        }
    }
    res = requests.post(url, json=data)
    print('发送图片返回:', res.json())

def save_df_as_img_matplotlib(df, filename, title=None, row_height=0.7, adaptive_row_height_col=None, fontsize=None, col_width_boost=None):
    """使用 plotly 绘制表格，涨停原因列宽0.3且内容自动换行，其余列宽自适应，保存为PNG图片"""
    # 涨停原因列特殊处理
    df = df.copy()
    if '涨停原因' in df.columns:
        def wrap_reason(x):
            s = str(x)
            return '<br>'.join([s[i:i+16] for i in range(0, len(s), 16)])
        df['涨停原因'] = df['涨停原因'].apply(wrap_reason)
    # 计算列宽
    min_width = 0.07
    col_widths = []
    total = 0
    for col in df.columns:
        if col == '涨停原因':
            col_widths.append(0.3)
        else:
            maxlen = max([len(str(x)) for x in df[col]] + [len(str(col))])
            col_widths.append(maxlen)
            total += maxlen
    # 归一化非"涨停原因"列宽
    for i, col in enumerate(df.columns):
        if col != '涨停原因':
            col_widths[i] = max(min_width, (col_widths[i]/total)*(0.7 if '涨停原因' in df.columns else 1.0))
    # 行颜色
    odd_row_color = "#f8f9fa"
    even_row_color = "white"
    fill_colors = []
    for i in range(len(df)):
        fill_colors.append([odd_row_color if i%2==0 else even_row_color]*len(df.columns))
    header_color = even_row_color
    fig = go.Figure(data=[go.Table(
        header=dict(
            values=[f'<b>{c}</b>' for c in df.columns],
            fill_color=header_color,
            align='center',
            font=dict(size=(fontsize+2) if fontsize else 15, color='black'),
            height=int(row_height*60)
        ),
        cells=dict(
            values=[df[col].astype(str) for col in df.columns],
            fill_color=fill_colors,
            align='center',
            font=dict(size=fontsize if fontsize else 13, color='black'),
            height=int(row_height*60)
        ),
        columnwidth=col_widths
    )])
    if title:
        fig.update_layout(title=title, title_font_size=(fontsize+3) if fontsize else 16, margin=dict(t=60))
    else:
        fig.update_layout(margin=dict(t=20))
    # 设置整体宽高，确保所有行完整显示
    fig_width = 1200
    base_height = 70  # 每行高度
    fig_height = base_height * (len(df) + 2)
    fig.update_layout(
        autosize=False,
        width=fig_width,
        height=fig_height
    )
    pio.write_image(fig, filename, scale=2)

def save_heatmap_from_grouped(grouped, date_str, filename):
    grouped_no_other = grouped[grouped['涨停原因'] != '其他']
    grouped_no_other = grouped_no_other.sort_values('个数', ascending=True)
    # 颜色渐变
    norm = plt.Normalize(grouped_no_other['个数'].min(), grouped_no_other['个数'].max())
    cmap = matplotlib.colormaps['Oranges']
    colors = [cmap(norm(v)) for v in grouped_no_other['个数']]
    plt.figure(figsize=(10, max(4, 0.5 * len(grouped_no_other))))
    bars = plt.barh(grouped_no_other['涨停原因'], grouped_no_other['个数'], color=colors)
    for idx, val in enumerate(grouped_no_other['个数']):
        plt.text(val, idx, str(val), va='center', fontsize=14)
    plt.xlabel('个数', fontsize=14)
    plt.ylabel('涨停原因', fontsize=14)
    plt.title(f'涨停原因热力图 {date_str}', fontsize=18)
    plt.tight_layout()
    plt.savefig(filename, bbox_inches='tight', dpi=200)
    plt.close()

def process_data(date_str):
    """获取并处理涨停数据，返回主表和分组表"""
    try:
        param = f"{date_str}涨停，非ST"
        df = pywencai.get(query=param, sort_key='成交金额', sort_order='desc')
        if df is None or df.empty:
            return None, None
        selected_columns = [
            '股票代码', '股票简称', '最新价', '最新涨跌幅', f'连续涨停天数[{date_str}]', f'几天几板[{date_str}]',
            f'首次涨停时间[{date_str}]', f'最终涨停时间[{date_str}]', f'涨停封单额[{date_str}]', f'涨停类型[{date_str}]',
            f'涨停原因类别[{date_str}]', f'a股市值(不含限售股)[{date_str}]'
        ]
        jj_df = df[selected_columns].copy()
        # 新增"涨停原因"列，便于后续分组
        jj_df['涨停原因'] = jj_df[f'涨停原因类别[{date_str}]']
        # 统一去除所有不需要的列
        drop_cols = [c for c in jj_df.columns if c.startswith('首次涨停时间') or c.startswith('最终涨停时间') or c.startswith('涨停原因类别')]
        jj_df = jj_df.drop(columns=drop_cols, errors='ignore')
        # 市值列重命名
        old_market_col = f'a股市值(不含限售股)[{date_str}]'
        new_market_col = f'a股市值'
        if old_market_col in jj_df.columns:
            jj_df[new_market_col] = pd.to_numeric(jj_df[old_market_col], errors='coerce').div(100000000).round(0).astype('Int64').astype(str) + '亿'
            jj_df = jj_df.drop(columns=[old_market_col])
        # 封单额列处理
        seal_amt_col = f'涨停封单额[{date_str}]'
        if seal_amt_col in jj_df.columns:
            jj_df[seal_amt_col.replace(f'[{date_str}]', '')] = pd.to_numeric(jj_df[seal_amt_col], errors='coerce').div(10000).round(0).astype('Int64').astype(str) + '万'
            jj_df = jj_df.drop(columns=[seal_amt_col])
        # 列名去掉日期后缀
        jj_df.columns = [c.replace(f'[{date_str}]', '') for c in jj_df.columns]
        # 排序
        if '连续涨停天数' in jj_df.columns:
            jj_df = jj_df.sort_values(by='连续涨停天数', ascending=False).reset_index(drop=True)
        # 重新编号
        if '序号' in jj_df.columns:
            jj_df = jj_df.drop(columns=['序号'])
        jj_df.insert(0, '序号', range(1, len(jj_df) + 1))
        # 最新涨跌幅只保留整数位
        if '最新涨跌幅' in jj_df.columns:
            jj_df['最新涨跌幅'] = pd.to_numeric(jj_df['最新涨跌幅'], errors='coerce').fillna(0).astype(int).astype(str)
        # 分组统计
        reason_stock_df = jj_df[['股票简称', '涨停原因']].copy()
        reason_stock_df['涨停原因'] = reason_stock_df['涨停原因'].fillna('其他')
        reason_stock_df['涨停原因'] = reason_stock_df['涨停原因'].apply(lambda x: '其他' if str(x).strip() == '' else x)
        reason_stock_df = reason_stock_df.assign(
            涨停原因=reason_stock_df['涨停原因'].str.split('+')
        ).explode('涨停原因')
        reason_stock_df['涨停原因'] = reason_stock_df['涨停原因'].fillna('其他')
        reason_stock_df['涨停原因'] = reason_stock_df['涨停原因'].apply(lambda x: '其他' if str(x).strip() == '' else x)
        grouped = reason_stock_df.groupby('涨停原因').agg(
            个数=('股票简称', 'nunique'),
            涨停股票列表=('股票简称', lambda x: '，'.join(sorted(set(x))))
        ).reset_index()
        grouped = grouped.sort_values('个数', ascending=False)
        # 合并涨停数为1的到"其他"
        grouped_gt1 = grouped[grouped['个数'] > 1].copy()
        grouped_eq1 = grouped[grouped['个数'] == 1].copy()
        def wrap_stock_list(stock_list):
            stocks = stock_list.replace('<br>', '，').split('，')
            stocks = [s.strip() for s in stocks if s.strip()]
            lines = ['，'.join(stocks[i:i+6]) for i in range(0, len(stocks), 6)]
            return '\n'.join(lines)
        if not grouped_eq1.empty:
            all_stocks = []
            for stocks in grouped_eq1['涨停股票列表']:
                all_stocks.extend(stocks.replace('<br>', '，').split('，'))
            all_stocks = sorted(set([s for s in all_stocks if s.strip()]))
            if '其他' in grouped_gt1['涨停原因'].values:
                idx = grouped_gt1[grouped_gt1['涨停原因'] == '其他'].index[0]
                old_stocks = grouped_gt1.at[idx, '涨停股票列表']
                merged_stocks = sorted(set(old_stocks.replace('<br>', '，').split('，') + all_stocks))
                grouped_gt1.at[idx, '涨停股票列表'] = wrap_stock_list('，'.join(merged_stocks))
                grouped_gt1.at[idx, '个数'] = len(merged_stocks)
                grouped_gt1['涨停股票列表'] = grouped_gt1['涨停股票列表'].apply(wrap_stock_list)
                grouped_final = grouped_gt1.reset_index(drop=True)
            else:
                other_row = {
                    '涨停原因': '其他',
                    '个数': len(all_stocks),
                    '涨停股票列表': wrap_stock_list('，'.join(all_stocks))
                }
                grouped_gt1['涨停股票列表'] = grouped_gt1['涨停股票列表'].apply(wrap_stock_list)
                grouped_final = pd.concat([grouped_gt1, pd.DataFrame([other_row])], ignore_index=True)
        else:
            grouped_gt1['涨停股票列表'] = grouped_gt1['涨停股票列表'].apply(wrap_stock_list)
            grouped_final = grouped_gt1
        # "其他"行每6个股票换行
        if '涨停股票列表' in grouped_final.columns and '涨停原因' in grouped_final.columns:
            mask = grouped_final['涨停原因'] == '其他'
            def wrap6(s):
                stocks = str(s).replace('\n', '，').replace('<br>', '，').split('，')
                stocks = [x for x in stocks if x.strip()]
                lines = ['，'.join(stocks[i:i+6]) for i in range(0, len(stocks), 6)]
                return '<br>'.join(lines)
            grouped_final.loc[mask, '涨停股票列表'] = grouped_final.loc[mask, '涨停股票列表'].apply(wrap6)
        return jj_df, grouped_final
    except Exception as e:
        print(f"数据处理失败: {str(e)}")
        return None, None

def scheduled_job():
    """调度任务：生成图片并发送钉钉"""
    if not is_workday(datetime.now()):
        return
    try:
        date_str = datetime.now().strftime("%Y%m%d")
        jj_df_sorted, grouped = process_data(date_str)
        if jj_df_sorted is None or grouped is None:
            print("当日没有涨停股票数据！")
            return
        # 再次校验，防止漏删
        drop_cols = [c for c in jj_df_sorted.columns if c.startswith('首次涨停时间') or c.startswith('最终涨停时间') or c.startswith('涨停原因类别')]
        if drop_cols:
            jj_df_sorted = jj_df_sorted.drop(columns=drop_cols)
        # 生成图片
        save_df_as_img_matplotlib(jj_df_sorted, f"涨停股票列表_{date_str}.png", title=f"涨停股票列表 {date_str}", row_height=0.7)
        save_df_as_img_matplotlib(
            grouped,
            f"涨停原因统计_{date_str}.png",
            title=f"涨停原因统计 {date_str}",
            row_height=0.7,
            adaptive_row_height_col='涨停股票列表',
            fontsize=18,
            col_width_boost={'half_first_third': True}
        )
        heatmap_file = f"涨停原因热力图_{date_str}.png"
        save_heatmap_from_grouped(grouped, date_str, heatmap_file)
        # 钉钉发送
        access_token = get_access_token(APPKEY, APPSECRET)
        for img_file in [f"涨停股票列表_{date_str}.png", f"涨停原因统计_{date_str}.png", heatmap_file]:
            try:
                media_id = upload_image_to_dingtalk(access_token, img_file)
                send_image_to_group(access_token, CHATID, media_id)
            except Exception as e:
                print(f"发送图片 {img_file} 失败: {e}")
    except Exception as e:
        print(f"获取数据或发送图片时发生错误：{str(e)}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--scheduled":
        scheduler = BlockingScheduler(timezone="Asia/Shanghai")
        scheduler.add_job(
            scheduled_job,
            CronTrigger(day_of_week='mon-fri', hour=16, minute=33)
        )
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            scheduler.shutdown()
    else:
        scheduled_job()
