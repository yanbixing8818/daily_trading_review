#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import dingtalk_subjob.all_a_stock_data_to_dingtalk as aasd
import dingtalk_subjob.lianbantianti_to_dingtalk as lbtt
import dingtalk_subjob.zhangdietingshuliang_to_dingtalk as zdtsl
import dingtalk_subjob.zhangtingyuanyin_to_dingtalk as ztyy
from core.utils import schedule_trade_day_job

def main():
    aasd.send_all_a_stock_data_to_dingtalk()
    lbtt.send_lianbantianti_to_dingtalk()
    zdtsl.send_zhangdietingshuliang_to_dingtalk()
    ztyy.send_zhangtingyuanyin_to_dingtalk()

if __name__ == "__main__":
    schedule_trade_day_job(main, 16, 0)














