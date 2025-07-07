import os
import pandas as pd
import csv
from mootdx.affair import Affair

def get_outstanding_map_from_tdx(tdx_path, csv_path='outstanding_map.csv', zip_filename=None):
    """
    从本地通达信财务数据（gpcw*.zip）提取所有A股流通股本，保存为csv，并返回dict。
    :param tdx_path: 通达信目录
    :param csv_path: 输出csv路径
    :param zip_filename: 财务zip文件名（如gpcw20241231.zip），默认自动查找最新
    :return: {code: outstanding}
    """
    tmp_dir = os.path.join(tdx_path, 'tmp')
    os.makedirs(tmp_dir, exist_ok=True)
    affair_reader = Affair()
    # 下载所有财务文件到tmp目录
    affair_reader.fetch(downdir=tmp_dir)
    # 自动查找最新zip
    if zip_filename is None:
        files = [f for f in os.listdir(tmp_dir) if f.startswith('gpcw') and f.endswith('.zip')]
        if not files:
            raise FileNotFoundError('未找到gpcw*.zip财务文件')
        zip_filename = sorted(files)[-1]
    # 解析zip
    data = affair_reader.parse(downdir=tmp_dir, filename=zip_filename)
    out_rows = []
    for code in data.index:
        row = data.loc[code]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        outstanding = None
        val = row.get('已上市流通A股')
        if '已上市流通A股' in data.columns and pd.notna(val):
            outstanding = val
        else:
            val = row.get('自由流通股(股)')
            if '自由流通股(股)' in data.columns and pd.notna(val):
                outstanding = val
            else:
                val = row.get('总股本')
                if '总股本' in data.columns and pd.notna(val):
                    outstanding = val
        if outstanding is not None:
            out_rows.append({'code': str(code).zfill(6), 'outstanding': outstanding})
    df_out = pd.DataFrame(out_rows)
    df_out['code'] = df_out['code'].astype(str).str.zfill(6)
    df_out.to_csv(csv_path, index=False, quoting=csv.QUOTE_ALL)
    return dict(zip(df_out['code'], df_out['outstanding']))