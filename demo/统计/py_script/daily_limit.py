import re
import pandas as pd
import numpy as np
from openpyxl import load_workbook


def color_bk_col(s):
    if s == 'FF':
        color = 'yellow'
    elif s >= 5.5:
        color = 'red'
    elif s <= -9.9:
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


def daily_limit(fname):
    df = pd.read_excel(fname)
    col_tag = df.columns.tolist()
    col_tag_tmp = []
    col_tag_sel = ['股票代码', '股票简称', '连续涨停天数', '涨停开板次数', '最终涨停时间', '涨停原因类别', '涨停类型']
    col_tag_out = ['股票代码', '股票简称', '连续涨停天数', '涨停开板次数', '最终涨停时间', '涨停原因类别', '涨停类型', '涨停类别0']
    daily_limit_style = []
    str_daily_limit_style = ''
    daily_limit_style_cnt_lt3 = []

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


    for value in df_tmp_01['涨停原因类别']:
        daily_limit_style.append(value.split(sep='+')[0])

    series_tmp = pd.Series(daily_limit_style)
    df_tmp_01['涨停类别0'] = series_tmp

    daily_limit_cnt = df_tmp_01.groupby('涨停类别0').涨停类别0.count().sort_values(ascending=False)
    for key_value in daily_limit_cnt.items():
        if key_value[1] >= 3:
            daily_limit_style_cnt_lt3.append(key_value[0])
            str_daily_limit_style += ' {}: {}'.format(key_value[0], key_value[1])

    for key_value in df_tmp_01['涨停类别0'].items():
        if key_value[1] in daily_limit_style_cnt_lt3:
            df_tmp_01['涨停类别0'][key_value[0]] = 'EE'

    daily_limit_style_statistic = pd.Series([str_daily_limit_style])
    # print(daily_limit_style_statistic)

    daily_limit_style_columns_out = ['涨停统计']
    daily_limit_style_index_out = ['0']

    daily_limit_style_df_out = pd.DataFrame(index=daily_limit_style_index_out, columns=daily_limit_style_columns_out)
    daily_limit_style_df_out.fillna(value='', inplace=True)
    daily_limit_style_df_out.insert(loc=0, column='date time', value=[dtime])
    daily_limit_style_df_out['涨停统计'][0] = str_daily_limit_style
    # print(daily_limit_style_df_out)

    df_out = df_tmp_01[col_tag_out]

    dtime_list = [''for i in range(df_out.shape[0])]
    dtime_list[0] = dtime
    df_out.insert(loc=0, column='date time', value=dtime_list)
    col_cnt = df_out.shape[1]
    df_out_01 = pd.concat([df_out, pd.DataFrame([['FF'for i in range(col_cnt)]], columns=df_out.columns)],\
                          ignore_index=True)

    xlsx_writer = pd.ExcelWriter('../../今日涨停.xlsx', engine='xlsxwriter')

    df_out_01.style.apply(color_bk_row, axis=1).\
                to_excel(xlsx_writer, sheet_name='今日涨停', index=0)
    daily_limit_style_df_out.style.to_excel(xlsx_writer, sheet_name='涨停统计', index=0)

    work_sheet = xlsx_writer.sheets['今日涨停']
    for idx in range(df_out.shape[1]):
        work_sheet.set_column(idx, idx, 15)
    xlsx_writer.close()

def daily_limit_concat():
    df_01 = pd.read_excel('../../复盘统计_今日涨停.xlsx', engine='openpyxl', sheet_name='今日涨停')
    df_02 = pd.read_excel('../../今日涨停.xlsx', engine='openpyxl', sheet_name='今日涨停')
    df_03 = pd.read_excel('../../复盘统计_今日涨停.xlsx', engine='openpyxl', sheet_name='涨停统计')
    df_04 = pd.read_excel('../../今日涨停.xlsx', engine='openpyxl', sheet_name='涨停统计')

    df_out = pd.concat([df_01, df_02], ignore_index=True)
    df_out_01 = pd.concat([df_03, df_04], ignore_index=True)

    xlsx_writer = pd.ExcelWriter('../../复盘统计_今日涨停.xlsx', engine='xlsxwriter')
    df_out.style.apply(color_bk_row, axis=1). \
        to_excel(xlsx_writer, sheet_name='今日涨停', index=0)
    df_out_01.to_excel(xlsx_writer, sheet_name='涨停统计', index=0)

    work_sheet = xlsx_writer.sheets['今日涨停']
    for idx in range(df_out.shape[1]):
        work_sheet.set_column(idx, idx, 15)
    xlsx_writer.close()
