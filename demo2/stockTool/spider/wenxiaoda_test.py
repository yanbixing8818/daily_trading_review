# -*- coding: utf-8 -*-
'''
通达信-小达
'''
import requests
import browser_cookie3
import pandas as pd
import json, os, random


class TDX_xiaoda:
    '''
    通达信-小达，使用chrome浏览器登录后，此工具可以自动获取ASPSessionID，并实现访问。
    '''

    def __init__(self, cookie=''):
        # 如果类传送Cookie则使用传参
        if cookie == '':
            self.cookie = self.get_cookie_tdx()
        else:
            self.cookie = cookie

    def set_headers(self):
        # 增加UserAgent，防止被反爬虫拦截
        user_agent_list = [
            "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; WOW64) Gecko/20100101 Firefox/61.0",
            "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.186 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.62 Safari/537.36",
            "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.101 Safari/537.36",
            "Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 6.0)",
            "Mozilla/5.0 (Macintosh; U; PPC Mac OS X 10.5; en-US; rv:1.9.2.15) Gecko/20110303 Firefox/3.6.15",
            ]
        headers = {
            'Cookie': self.cookie,
            'User-Agent': random.choice(user_agent_list)}
        return headers

    def _get_cookie_tdx(self):
        # 查找指定域名的指定Cookie值
        cookies = browser_cookie3.edge(
            domain_name='wenda.tdx.com.cn')  # 注意：Chrome浏览器114版无法访问Cookies文件，故修改为edge浏览器，或者改为firefox浏览器。
        for item in cookies:
            if item.name == "ASPSessionID":
                # print('%s = %s' % (item.name, item.value))
                cookie_tdx = 'ASPSessionID=' + item.value + ';'
                return cookie_tdx

    def get_data_option(self, word):
        '''
        获取提示参考
        :param word:
        :return:
        '''
        data = [{"op_flag": 1, "question": word, "POS": 0, "COUNT": 10, "RANG": "AG"}]
        url = 'https://wenda.tdx.com.cn/TQL?Entry=NLPSE.QuestionImagine&RI='
        headers = self.set_headers()
        res = requests.post(url=url, data=json.dumps(data), headers=headers)
        res_json = res.json()
        return res_json

    def get_word_code(self, name):
        '''
        :param name:
        :return:
        '''
        data = [{"message": name, "TDXID": "", "wdbk": "", "RANG": "AG"}]
        url = 'https://wenda.tdx.com.cn/TQL?Entry=NLPSE.StockSelect&RI='
        headers = self.set_headers()
        res = requests.post(url=url, headers=headers, data=json.dumps(data))
        res_json = res.json()
        code = res_json[-1][0]
        return code

    def get_all_option_data(self):
        '''
        获取全部参考
        :return:
        '''
        url = 'https://wenda.tdx.com.cn/TQL?Entry=NLPSE.SmartQuery&RI='
        headers = self.set_headers()
        data = [
            {"op_flag": 1, "order_field": "", "order_flag": 1, "cond_json": "", "POS": 0, "COUNT": -1, "RANG": "AG"}]
        res = requests.post(url=url, headers=headers, data=json.dumps(data))
        res_json = res.json()
        df = pd.DataFrame(res_json)
        df = df.iloc[1:]
        df2 = df.rename(columns=df.iloc[0])
        df3 = df2.iloc[1:]
        return df3

    def get_word_result(self, word, try_times=30):
        '''
        根据关键字分析后获取数据
        :param word:关键字
        :return:字典，包含状态和数据
        '''
        while try_times > 0:
            url = 'https://wenda.tdx.com.cn/TQL?Entry=NLPSE.NLPQuery&RI=6BFD'
            code = self.get_word_code(name=word)
            headers = self.set_headers()
            data = [
                {"nlpse_id": code, "POS": 0, "COUNT": 100000, "order_field": "", "dynamic_order": "", "order_flag": "",
                 "timestamps": 0, "op_flag": 1, "screen_type": 1, "RANG": "AG"}]
            res = requests.post(url=url, headers=headers, data=json.dumps(data))
            text = res.content.decode('utf-8')
            res_json = json.loads(text)
            if len(res_json[1]) < 4:
                try_times -= 1
                print('获取信息失败，剩余' + str(try_times) + '次尝试机会，再次尝试连接......')
            else:
                # print(text)
                df = pd.DataFrame(res_json)
                df = df.iloc[1:]
                df2 = df.rename(columns=df.iloc[0])
                df3 = df2.iloc[2:]
                return {
                    "success": True,
                    "df_data": df3.round(3)
                }
        return {
            "success": False,
            "msg": '获取行情信息结果为None'
        }


# ===============表格美化输出===============
def df_table(df, index):
    import prettytable as pt
    # 利用prettytable对输出结果进行美化,index为索引列名:df_table(df,'market')
    tb = pt.PrettyTable()
    # 如果为trade_time为index转换为日期类型，其它不用管。
    if index == "trade_time":
        df = df.set_index(index)
        df.index = pd.DatetimeIndex(df.index)
    # df.reset_index(level=None, drop=True, inplace=True, col_level=0, col_fill='')
    df = df.reset_index(drop=True)
    tb.add_column(index, df.index)  # 按date排序
    for col in df.columns.values:  # df.columns.values的意思是获取列的名称
        # print('col',col)
        # print('df[col]',df[col])
        tb.add_column(col, df[col])
    print(tb)


if __name__ == '__main__':
    # 以下两种方法均可以，推荐方法2。注册请自行搞定。
    # 方法1：使用任意浏览器登录https://wenda.tdx.com.cn/，并按F12查看网络，找到Cookie复制后替换这里ASPSessionID后数值即可使用。注意不要带分号。
    xd = TDX_xiaoda(cookie = 'ASPSessionID=xxxxxx')
    # 方法2：使用Chrome浏览器登录https://wenda.tdx.com.cn/后，无需手工查找Cookie，程序会自动获取ASPSessionID，并实现访问。但必须使用Chrome浏览器。
    #xd = TDX_xiaoda()

    if 0:
        # 可能获取不到
        ret = xd.get_data_option(word='涨停')
        print(ret)
        # 获取问题转代码
        ret = xd.get_word_code(name='涨停')
        print(ret)
        # 获取全部的参考，具体看通达信
        ret = xd.get_all_option_data()
        # print(ret)
        df_table(ret, 'df')

    if 1:
        # 获取问题的结果
        words = '涨停'
        ret = xd.get_word_result(word=words)
        if ret['success']:
            df = ret['df_data']
            # print(df)
            df_table(df, 'df')
            filename = os.path.dirname(__file__) + '\\' + '通达信-小达选股_' + words + '.xlsx'
            df.to_excel(filename)
            print('选股完成，结果写入：', filename)

