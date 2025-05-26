import requests
import io

# 企业内部应用参数
APPKEY = 'dingdh0hnt40b7eqyivc'
APPSECRET = 'eXbAsAG5HRYMNFW4x3ffL1kSLepZcldVfyEeiSvsuhb5js_foSRZHtOtXrWo_5_f'
CHATID = 'chat9652245847eebc05ee9e1a1fea02ceda'  # 你的目标群chatid

def get_access_token(appkey, appsecret):
    url = f"https://oapi.dingtalk.com/gettoken?appkey={appkey}&appsecret={appsecret}"
    resp = requests.get(url)
    data = resp.json()
    if data.get('errcode', 0) != 0:
        raise Exception(f"获取access_token失败: {data}")
    return data["access_token"]

def upload_image_to_dingtalk(access_token, image, filename='image.png'):
    url = f"https://oapi.dingtalk.com/media/upload?access_token={access_token}&type=image"
    if isinstance(image, (str, bytes)):
        # 文件路径或字节流
        with open(image, 'rb') as f:
            files = {'media': f}
            res = requests.post(url, files=files)
    elif isinstance(image, io.BytesIO):
        image.seek(0)
        files = {'media': (filename, image, 'image/png')}
        res = requests.post(url, files=files)
    else:
        raise ValueError('image参数必须是文件路径或BytesIO对象')
    data = res.json()
    if data.get('errcode', 0) != 0:
        raise Exception(f"上传图片失败: {data}")
    return data["media_id"]

def send_image_to_group(access_token, chatid, media_id):
    url = f"https://oapi.dingtalk.com/chat/send?access_token={access_token}"
    data = {
        "chatid": chatid,
        "msg": {
            "msgtype": "image",
            "image": {
                "media_id": media_id
            }
        }
    }
    res = requests.post(url, json=data)
    print('发送图片返回:', res.json())

def send_to_dingtalk(img):
    access_token = get_access_token(APPKEY, APPSECRET)
    media_id = upload_image_to_dingtalk(access_token, img)
    send_image_to_group(access_token, CHATID, media_id)

if __name__ == "__main__":
    send_to_dingtalk("test.png")
