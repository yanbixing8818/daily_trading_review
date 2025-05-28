import dingtalk_subjob.all_a_stock_data_to_dingtalk as aasd
import dingtalk_subjob.lianbantianti_to_dingtalk as lbtt
import dingtalk_subjob.zhangdietingshuliang_to_dingtalk as zdtsl
import dingtalk_subjob.zhangtingyuanyin_to_dingtalk as ztyy
from apscheduler.schedulers.blocking import BlockingScheduler
from chinese_calendar import is_workday
from datetime import datetime

def main():
    aasd.send_all_a_stock_data_to_dingtalk()
    lbtt.send_lianbantianti_to_dingtalk()
    zdtsl.send_zhangdietingshuliang_to_dingtalk()
    ztyy.send_zhangtingyuanyin_to_dingtalk()

def schedule_jobs():
    scheduler = BlockingScheduler(timezone="Asia/Shanghai")
    def job_if_workday():
        if is_workday(datetime.now()):
            main()
        else:
            print("非交易日，不执行推送。")
    scheduler.add_job(job_if_workday, 'cron', hour=15, minute=30)
    print("定时任务已启动，等待交易日15:30触发...")
    scheduler.start()

if __name__ == "__main__":
    schedule_jobs()














