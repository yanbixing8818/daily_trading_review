#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from sqlalchemy import DATE, VARCHAR, FLOAT, BIGINT, SmallInteger, DATETIME
_COLLATE = "utf8mb4_general_ci"


TABLE_CN_STOCK_SPOT = {'name': 'cn_stock_spot', 'cn': '每日股票数据',
                       'columns': {'date': {'type': DATE, 'cn': '日期', 'size': 0},
                                   'code': {'type': VARCHAR(6, _COLLATE), 'cn': '代码', 'size': 60},
                                   'name': {'type': VARCHAR(20, _COLLATE), 'cn': '名称', 'size': 70},
                                   'new_price': {'type': FLOAT, 'cn': '最新价', 'size': 70},
                                   'change_rate': {'type': FLOAT, 'cn': '涨跌幅', 'size': 70},
                                   'ups_downs': {'type': FLOAT, 'cn': '涨跌额', 'size': 70},
                                   'volume': {'type': BIGINT, 'cn': '成交量', 'size': 90},
                                   'deal_amount': {'type': BIGINT, 'cn': '成交额', 'size': 100},
                                   'amplitude': {'type': FLOAT, 'cn': '振幅', 'size': 70},
                                   'turnoverrate': {'type': FLOAT, 'cn': '换手率', 'size': 70},
                                   'volume_ratio': {'type': FLOAT, 'cn': '量比', 'size': 70},
                                   'open_price': {'type': FLOAT, 'cn': '今开', 'size': 70},
                                   'high_price': {'type': FLOAT, 'cn': '最高', 'size': 70},
                                   'low_price': {'type': FLOAT, 'cn': '最低', 'size': 70},
                                   'pre_close_price': {'type': FLOAT, 'cn': '昨收', 'size': 70},
                                   'speed_increase': {'type': FLOAT, 'cn': '涨速', 'size': 70},
                                   'speed_increase_5': {'type': FLOAT, 'cn': '5分钟涨跌', 'size': 70},
                                   'speed_increase_60': {'type': FLOAT, 'cn': '60日涨跌幅', 'size': 70},
                                   'speed_increase_all': {'type': FLOAT, 'cn': '年初至今涨跌幅', 'size': 70},
                                   'dtsyl': {'type': FLOAT, 'cn': '市盈率动', 'size': 70},
                                   'pe9': {'type': FLOAT, 'cn': '市盈率TTM', 'size': 70},
                                   'pe': {'type': FLOAT, 'cn': '市盈率静', 'size': 70},
                                   'pbnewmrq': {'type': FLOAT, 'cn': '市净率', 'size': 70},
                                   'basic_eps': {'type': FLOAT, 'cn': '每股收益', 'size': 70},
                                   'bvps': {'type': FLOAT, 'cn': '每股净资产', 'size': 70},
                                   'per_capital_reserve': {'type': FLOAT, 'cn': '每股公积金', 'size': 70},
                                   'per_unassign_profit': {'type': FLOAT, 'cn': '每股未分配利润', 'size': 70},
                                   'roe_weight': {'type': FLOAT, 'cn': '加权净资产收益率', 'size': 70},
                                   'sale_gpr': {'type': FLOAT, 'cn': '毛利率', 'size': 70},
                                   'debt_asset_ratio': {'type': FLOAT, 'cn': '资产负债率', 'size': 70},
                                   'total_operate_income': {'type': BIGINT, 'cn': '营业收入', 'size': 120},
                                   'toi_yoy_ratio': {'type': FLOAT, 'cn': '营业收入同比增长', 'size': 70},
                                   'parent_netprofit': {'type': BIGINT, 'cn': '归属净利润', 'size': 110},
                                   'netprofit_yoy_ratio': {'type': FLOAT, 'cn': '归属净利润同比增长', 'size': 70},
                                   'report_date': {'type': DATE, 'cn': '报告期', 'size': 110},
                                   'total_shares': {'type': BIGINT, 'cn': '总股本', 'size': 120},
                                   'free_shares': {'type': BIGINT, 'cn': '已流通股份', 'size': 120},
                                   'total_market_cap': {'type': BIGINT, 'cn': '总市值', 'size': 120},
                                   'free_cap': {'type': BIGINT, 'cn': '流通市值', 'size': 120},
                                   'industry': {'type': VARCHAR(20, _COLLATE), 'cn': '所处行业', 'size': 100},
                                   'listing_date': {'type': DATE, 'cn': '上市时间', 'size': 110}}}



def get_field_types(cols):
    data = {}
    for k in cols:
        data[k] = cols[k]['type']
    return data




