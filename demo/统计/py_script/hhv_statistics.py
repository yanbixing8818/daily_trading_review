import re
import pandas as pd
import numpy as np
from openpyxl import load_workbook

def hhv_statistic_proc(fname):
    df = pd.read_excel('../'+fname)
    col_tag = df.columns.tolist()
    col_tag_tmp = []
    industry_group = []
    str_industry_group = ''

    for item in iter(col_tag):
        item_tmp = item.split(sep='(')[0]
        item_tmp = item_tmp.split(sep='\n')[0]
        item_tmp = item_tmp.split(sep=':')[0]
        col_tag_tmp.append(item_tmp)

        if item.split(sep='\n')[0] == '动态市盈率':
            dtime = item.split(sep='\n')[1]

    df.columns = col_tag_tmp
    # print(col_tag_tmp)
    # print(dtime)
    # print(df)

    df_tmp = df.drop(df.tail(1).index)

    for value in df_tmp['所属同花顺行业']:
        industry_group.append(value.split(sep='-')[0])

    series_tmp = pd.Series(industry_group)
    df_tmp['所属同花顺行业0'] = series_tmp

    industry_group_cnt = df_tmp.groupby('所属同花顺行业0').所属同花顺行业0.count().sort_values(ascending=False)
    itotal = 0
    for key_value in industry_group_cnt.items():
        itotal += key_value[1]
        if key_value[1] >= 2:
            str_industry_group += ' {}: {}'.format(key_value[0], key_value[1])

    # print(str_industry_group)
    df_out = pd.DataFrame(data={
                '日期': [dtime],
                '新高个数': [itotal],
                '最大板块': [industry_group_cnt.index[0]],
                '最大板个数': [industry_group_cnt[0]],
                '其他情况': [str_industry_group],})

    xlsx_writer = pd.ExcelWriter('../../' + fname, engine='xlsxwriter')
    df_out.to_excel(xlsx_writer, sheet_name=fname[:-5], index=0)
    #work_sheet = xlsx_writer.sheets['昨日涨停']
    #for idx in range(df_out.shape[1]):
        #work_sheet.set_column(idx, idx, 15)
    xlsx_writer.close()

def hhv_statistic_concat(fname):
    df_01 = pd.read_excel('../../复盘统计_' + fname, engine='openpyxl', sheet_name=fname[:-5])
    df_02 = pd.read_excel('../../' + fname, engine='openpyxl', sheet_name=fname[:-5])
    df_out = pd.concat([df_01, df_02], ignore_index=True)

    xlsx_writer = pd.ExcelWriter('../../复盘统计_' + fname, engine='xlsxwriter')
    df_out.style.to_excel(xlsx_writer, sheet_name=fname[:-5], index=0)

    xlsx_writer.close()
