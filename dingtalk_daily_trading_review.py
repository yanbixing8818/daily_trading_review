import subjob.all_a_stock_data_to_dingtalk as aasd
import subjob.lianbantianti_to_dingtalk as lbt
import subjob.zhangdietingshuliang_to_dingtalk as zds
import subjob.zhangtingyuanyin_to_dingtalk as zty


def main():
    aasd.send_all_a_stock_data_to_dingtalk()
    lbt.send_lianbantianti_to_dingtalk()
    zds.send_zhangdietingshuliang_to_dingtalk()
    zty.send_zhangtingyuanyin_to_dingtalk()


if __name__ == "__main__":
    main()














