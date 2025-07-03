import os
import requests
import zipfile
from tqdm import tqdm

# -------------------------------
# 下载文件函数（稳定单行进度）
# -------------------------------
def download_file(url, dest_path):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Referer': 'https://www.tdx.com.cn/',
        'Accept': '*/*',
        'Connection': 'keep-alive'
    }

    try:
        with requests.get(url, headers=headers, stream=True, timeout=10) as response:
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            block_size = 1024 * 100  # 100KB 块提升性能

            with tqdm(
                total=total_size,
                unit='B',
                unit_scale=True,
                desc=f"下载中: {os.path.basename(dest_path)}",
                leave=True
            ) as progress_bar:

                with open(dest_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=block_size):
                        if chunk:
                            f.write(chunk)
                            progress_bar.update(len(chunk))

        print(f"✅ 下载完成：{dest_path}")

    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP 错误：{e}")
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求异常：{e}")

# -------------------------------
# 解压 zip 文件并覆盖到目标目录
# -------------------------------
def unzip_file(zip_path, extract_to):
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            os.makedirs(extract_to, exist_ok=True)
            for member in zip_ref.namelist():
                target_path = os.path.join(extract_to, member)
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with open(target_path, 'wb') as outfile:
                    outfile.write(zip_ref.read(member))
            print(f"✅ 解压完成：{zip_path} → {extract_to}")
    except zipfile.BadZipFile:
        print(f"❌ 文件损坏或不是有效的 ZIP：{zip_path}")

# -------------------------------
# 主程序入口（顺序下载）
# -------------------------------
def main():
    urls = [
        "https://data.tdx.com.cn/vipdoc/tdxgp.zip",
        "https://data.tdx.com.cn/vipdoc/tdxfin.zip"
    ]

    temp_download_dir = "temp_download"
    os.makedirs(temp_download_dir, exist_ok=True)
    extract_path = r"/mnt/c/new_tdx/vipdoc/cw"

    for url in urls:
        filename = os.path.basename(url)
        zip_path = os.path.join(temp_download_dir, filename)
        download_file(url, zip_path)
        unzip_file(zip_path, extract_path)

    print("🎉 所有文件下载并解压完成。")

# -------------------------------
# 程序运行入口
# -------------------------------
if __name__ == "__main__":
    main()
