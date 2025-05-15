import re
import pandas as pd
import numpy as np
from openpyxl import load_workbook

def color_bk_col(s):
    if s=='FF':
        color = 'yellow'
    elif s>=5.5:
        color = 'red'
    elif s<=-9.9:
        color = 'green'
    else:
        color = 'white'
    return f"background-color:{color}"

def color_bk_row(row):
    s = row['涨停类别0']
    if s == 'EE':
        css = 'background-color: purple'
    elif s == 'FF':
        css = 'background-color: yellow'
    else:
        css = 'background-color: white'

    return [css] * len(row)

def daily_limit_lt2day(fname):
    df = pd.read_excel(fname)
    col_tag = df.columns.tolist()
    col_tag_tmp = []
    col_tag_sel = ['股票代码', '股票简称', '涨停原因类别', '连续涨停天数']
    daily_limit_lt2day_cnt_sort = []

    for item in iter(col_tag):
        item_tmp = item.split(sep='(')[0]
        item_tmp = item_tmp.split(sep='\n')[0]
        item_tmp = item_tmp.split(sep=':')[0]
        col_tag_tmp.append(item_tmp)

        if item.split(sep='\n')[0] == '涨停原因类别':
            dtime = item.split(sep='\n')[1]

    df.columns = col_tag_tmp
    # print(col_tag_tmp)
    # print(dtime)
    # print(df)

    df_tmp = df[col_tag_sel]
    df_tmp_01 = df_tmp.drop(df_tmp.tail(1).index)
    # print(df_tmp_01)

    daily_limit_lt2day_cnt = df_tmp_01.groupby('连续涨停天数').连续涨停天数.count().sort_values(ascending=False)

    for key_value in daily_limit_lt2day_cnt.items():
        daily_limit_lt2day_cnt_sort.append(key_value[0])

    daily_limit_lt2day_cnt_sort.sort(reverse=True)

    stock_name_series = df_tmp_01['股票简称']

    columns_out = [i for i in range(2, 27)]
    index_out = ['0']

    df_out = pd.DataFrame(index=index_out, columns=columns_out)
    df_out.fillna(value='', inplace=True)
    df_out.insert(loc=0, column='date time', value=[dtime])

    for key_value in df_tmp_01['连续涨停天数'].items():
        str_content = df_out[key_value[1]][0]
        str_content += ' {} \n'.format(df_tmp_01['股票简称'][key_value[0]])
        df_out[key_value[1]][0] = str_content
        # print(str_content)

    # print(df_out)
    xlsx_writer = pd.ExcelWriter('../../今日连板.xlsx', engine='xlsxwriter')

    df_out.to_excel(xlsx_writer, sheet_name='今日连板', index=0)
    work_sheet = xlsx_writer.sheets['今日连板']
    for idx in range(df_out.shape[1]):
        work_sheet.set_column(idx, idx, 15)

    xlsx_writer.close()

def daily_limit_lt2day_concat():
    df_01 = pd.read_excel('../../复盘统计_今日连板.xlsx', engine='openpyxl', sheet_name='今日连板')
    df_02 = pd.read_excel('../../今日连板.xlsx', engine='openpyxl', sheet_name='今日连板')
    df_out = pd.concat([df_01, df_02], ignore_index=True)

    xlsx_writer = pd.ExcelWriter('../../复盘统计_今日连板.xlsx', engine='xlsxwriter')

    df_out.to_excel(xlsx_writer, sheet_name='今日连板', index=0)

    work_sheet = xlsx_writer.sheets['今日连板']
    for idx in range(df_out.shape[1]):
        work_sheet.set_column(idx, idx, 15)

    xlsx_writer.close()