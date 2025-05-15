import re
import pandas as pd
import numpy as np
from openpyxl import load_workbook
from styleframe import StyleFrame, Styler

from prev_daily_limit import prev_daily_limit
from prev_daily_limit import prev_daily_limit_concat
from prev_daily_limit_lt2day import prev_daily_limit_lt2day
from prev_daily_limit_lt2day import prev_daily_limit_lt2day_concat
from hhv_statistics import hhv_statistic_proc
from hhv_statistics import hhv_statistic_concat
from daily_limit import daily_limit
from daily_limit import daily_limit_concat
from daily_limit_lt2day import daily_limit_lt2day
from daily_limit_lt2day import daily_limit_lt2day_concat

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

def statistic_run():
    prev_daily_limit('../昨日涨停.xlsx')
    prev_daily_limit_concat()

    prev_daily_limit_lt2day('../昨日连板.xlsx')
    prev_daily_limit_lt2day_concat()

    hhv_statistic_proc('120日新高.xlsx')
    hhv_statistic_concat('120日新高.xlsx')

    hhv_statistic_proc('250日新高.xlsx')
    hhv_statistic_concat('250日新高.xlsx')

    hhv_statistic_proc('历史新高.xlsx')
    hhv_statistic_concat('历史新高.xlsx')

    daily_limit('../今日涨停.xlsx')
    daily_limit_concat()

    daily_limit_lt2day('../今日连板.xlsx')
    daily_limit_lt2day_concat()

    df_01 = pd.read_excel('../../复盘统计_昨日涨停.xlsx', engine='openpyxl', sheet_name='昨日涨停')
    df_02 = pd.read_excel('../../复盘统计_昨日连板.xlsx', engine='openpyxl', sheet_name='昨日连板')
    df_03 = pd.read_excel('../../复盘统计_120日新高.xlsx', engine='openpyxl', sheet_name='120日新高')
    df_04 = pd.read_excel('../../复盘统计_250日新高.xlsx', engine='openpyxl', sheet_name='250日新高')
    df_05 = pd.read_excel('../../复盘统计_历史新高.xlsx', engine='openpyxl', sheet_name='历史新高')
    df_06 = pd.read_excel('../../复盘统计_今日涨停.xlsx', engine='openpyxl', sheet_name='今日涨停')
    df_07 = pd.read_excel('../../复盘统计_今日涨停.xlsx', engine='openpyxl', sheet_name='涨停统计')
    df_08 = pd.read_excel('../../复盘统计_今日连板.xlsx', engine='openpyxl', sheet_name='今日连板')

    xlsx_writer = pd.ExcelWriter('../../复盘统计.xlsx', engine='xlsxwriter')

    df_01.style.apply(color_bk_row, axis=1).\
                applymap(color_bk_col, subset=['赚钱效应', '亏钱效应']).\
                to_excel(xlsx_writer, sheet_name='昨日涨停', index=0)

    df_02.style.apply(color_bk_row, axis=1).\
                applymap(color_bk_col, subset=['赚钱效应', '亏钱效应']).\
                to_excel(xlsx_writer, sheet_name='昨日连板', index=0)

    df_03.style.to_excel(xlsx_writer, sheet_name='120日新高', index=0)
    df_04.style.to_excel(xlsx_writer, sheet_name='250日新高', index=0)
    df_05.style.to_excel(xlsx_writer, sheet_name='历史新高', index=0)

    df_06.style.apply(color_bk_row, axis=1). \
        to_excel(xlsx_writer, sheet_name='今日涨停', index=0)
    work_sheet = xlsx_writer.sheets['今日涨停']
    for idx in range(df_06.shape[1]):
        work_sheet.set_column(idx, idx, 15)

    df_07.to_excel(xlsx_writer, sheet_name='涨停统计', index=0)

    df_08.to_excel(xlsx_writer, sheet_name='今日连板', index=0)
    work_sheet = xlsx_writer.sheets['今日连板']
    for idx in range(df_07.shape[1]):
        work_sheet.set_column(idx, idx, 15)

    xlsx_writer.close()

def statistic_styleframe_construct(sf, df, excel_writer, sh_name):
    index_list = []
    col_list = df.columns.tolist()
    col_row_frz = chr(len(col_list) + 65 - 1) + '2'
    row_list = df.index.values.tolist()

    # print(sh_name)
    sf.apply_column_style(cols_to_style=col_list, styler_obj=Styler(font_size=10.5, bg_color='#DDD9C4', \
                        horizontal_alignment='center', wrap_text=True), style_header=True)
    sf.set_column_width(columns=col_list, width=15)

    if '涨停类别0' in col_list:
        sf.apply_style_by_indexes(indexes_to_style=sf[sf['涨停类别0']=='EE'], styler_obj=Styler(bg_color='#9370DB'))
        sf.apply_style_by_indexes(indexes_to_style=sf[sf['涨停类别0']=='FF'], styler_obj=Styler(bg_color='yellow'))

    if '赚钱效应' in col_list:
        index_list.clear()
        for key_value in sf['赚钱效应'].items():
            if key_value[1]!='FF' and key_value[1]>=5.5:
                index_list.append(int(key_value[0]))
        sf.apply_style_by_indexes(indexes_to_style=index_list, styler_obj=Styler(number_format="0.00", bg_color='red'),\
                                  cols_to_style=['赚钱效应'])

        index_list.clear()
        for key_value in sf['赚钱效应'].items():
            if key_value[1]!='FF' and key_value[1]<=-9.9:
                index_list.append(int(key_value[0]))
        sf.apply_style_by_indexes(indexes_to_style=index_list, styler_obj=Styler(number_format="0.00", bg_color='green'),\
                                  cols_to_style=['赚钱效应'])

    if '亏钱效应' in col_list:
        index_list.clear()
        for key_value in sf['亏钱效应'].items():
            if key_value[1]!='FF' and key_value[1]<=-9.9:
                index_list.append(int(key_value[0]))

        sf.apply_style_by_indexes(indexes_to_style=index_list, styler_obj=Styler(number_format="0.00", bg_color='green'),\
                                  cols_to_style=['亏钱效应'])

    # print(col_list)
    # print(col_row_frz)
    sf.to_excel(excel_writer=excel_writer, sheet_name=sh_name, columns_and_rows_to_freeze=col_row_frz, index=False)
    # if '涨停类别0' in col_list:
    #     sf.to_excel(excel_writer=excel_writer, sheet_name=sh_name, columns_and_rows_to_freeze=col_row_frz, index=False,\
    #                 best_fit=['涨停原因类别'], columns_to_hide=['涨停类别0'])
    # elif '其他情况' in col_list:
    #     sf.to_excel(excel_writer=excel_writer, sheet_name=sh_name, columns_and_rows_to_freeze=col_row_frz, index=False,\
    #                 best_fit=['其他情况'])
    # elif '涨停统计' in col_list:
    #     sf.to_excel(excel_writer=excel_writer, sheet_name=sh_name, columns_and_rows_to_freeze=col_row_frz, index=False,\
    #                 best_fit=['涨停统计'])
    # else:
    #     print('error format')
def statistic_style_reset():
    sheet_names = ['昨日涨停', '昨日连板', '120日新高', '250日新高', '历史新高', '今日涨停', '涨停统计', '今日连板']

    excel_writer = StyleFrame.ExcelWriter('../../复盘统计_01.xlsx')

    for sh_name in sheet_names:
        df = pd.read_excel('../../复盘统计.xlsx', engine='openpyxl', sheet_name=sh_name)
        sf = StyleFrame(df)
        statistic_styleframe_construct(sf, df, excel_writer, sh_name)
    excel_writer.close()

if __name__ == '__main__':
    statistic_run()
    statistic_style_reset()