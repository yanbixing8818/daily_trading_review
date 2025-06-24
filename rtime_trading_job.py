import rtime_subjob.hongpanjiashu as hpjs
import rtime_subjob.jingjiashujukuaibao as jjsjkb
import rtime_subjob.shichanggailan as scgl
import rtime_subjob.xingutixing as xgtx
import rtime_subjob.kaipanla_sector as kplsec
from concurrent.futures import ThreadPoolExecutor


def main():
    with ThreadPoolExecutor() as executor:
        executor.submit(jjsjkb.jingjiashujukuaibao_rtime_jobs)
        executor.submit(hpjs.hongpanjiashu_rtime_jobs)
        executor.submit(scgl.shichanggailan_rtime_jobs)
        executor.submit(xgtx.xingutixing_rtime_jobs)
        executor.submit(kplsec.kaipanla_sector_rtime_jobs)
#实时任务，由各个小模块自己控制发送时间，这里只作为一个启动入口
if __name__ == "__main__":
    main()
    


