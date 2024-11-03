# encoding=utf-8
import json
import logging
import re
import time
from hashlib import sha1
import google.generativeai as genai
import requests
import xmltodict
from flask import Flask, request

# 配置日志
logging.basicConfig(
    format='%(asctime)s %(filename)s %(lineno)s %(levelname)s - %(message)s',
    filename="debug.log", 
    level=logging.DEBUG
)

# 用户会话存储
user2session = {}

# 加载配置
with open('conf.json') as f:
    dic = json.load(f)
    
# 初始化配置
app_id = dic['app_id']
app_secret = dic['app_secret']
token = dic['token']
gemini_api_key = dic['genimi']['api_key']
generation_config = dic['generation_config']
safety_settings = dic['safety_settings']

# 初始化 Gemini
genai.configure(api_key=gemini_api_key)
model = genai.GenerativeModel('gemini-pro', 
                            generation_config=generation_config,
                            safety_settings=safety_settings)

app = Flask(__name__)

class TokenManager:
    def __init__(self):
        self.access_token = None
        self.expires_at = 0

    def get_token(self):
        """获取公众号access_token，如果过期则自动刷新"""
        if self.access_token and time.time() < self.expires_at:
            return self.access_token
            
        params = {
            'grant_type': 'client_credential',
            'appid': app_id,
            'secret': app_secret
        }
        try:
            res = requests.get('https://api.weixin.qq.com/cgi-bin/token', 
                             params=params).json()
            if 'access_token' in res:
                self.access_token = res['access_token']
                self.expires_at = time.time() + 7000  # 设置过期时间为7000秒
                return self.access_token
            logging.error("Failed to get access_token: %s", res)
            return None
        except Exception as e:
            logging.error("Error refreshing token: %s", e)
            return None

# 创建token管理器实例
token_manager = TokenManager()

def cut_message(message, max_length=2000):
    """将长消息切分成小段"""
    if len(message.encode()) <= max_length:
        return [message]
        
    messages = []
    lines = message.split("\n")
    current = []
    current_length = 0
    
    for line in lines:
        line_length = len((line + "\n").encode())
        if current_length + line_length > max_length:
            messages.append("\n".join(current))
            current = [line]
            current_length = line_length
        else:
            current.append(line)
            current_length += line_length
            
    if current:
        messages.append("\n".join(current))
    return messages

def send(user, message, message_type="text"):
    """发送消息到公众号用户"""
    access_token = token_manager.get_token()
    if not access_token:
        logging.error("Failed to get access token")
        return
        
    messages = cut_message(message)
    
    for msg in messages:
        if not msg.strip():
            continue
            
        data = {
            "touser": user,
            "msgtype": message_type,
            message_type: {"content": msg}
        }
            
        try:
            response = requests.post(
                f'https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token={access_token}',
                json=data
            ).json()
            
            if response.get('errcode', 0) != 0:
                logging.error("Failed to send message: %s", response)
            time.sleep(0.5)  # 避免发送太快
        except Exception as e:
            logging.error("Error sending message: %s", e)
            time.sleep(5)
            send(user, message)  # 失败重试

def convert_to_text(input_str):
    """简单的移除markdown标记"""
    # 移除代码块
    text = re.sub(r'```[\s\S]*?```', '', input_str)
    # 移除其他markdown标记
    text = re.sub(r'[*#>`~_\[\]\(\)]+', '', text)
    return text.strip()

def chat(user, message):
    """处理聊天消息"""
    logging.debug("%s ask gemini: %s", user, message)
    
    try:
        if message == "#开始":
            chat_session = model.start_chat(history=[])
            user2session[user] = chat_session
            send(user, "对话模式开始...")
            return
            
        if message == "#结束":
            user2session.pop(user, None)
            send(user, "对话模式结束...")
            return
            
        # 处理普通消息
        chat_session = user2session.get(user)
        if chat_session:
            response = chat_session.send_message(message).text
        else:
            response = model.generate_content(message).text
            
        send(user, convert_to_text(response))
        logging.info("Gemini answer: %s", response)
        
    except Exception as e:
        logging.error("Error in chat: %s", e)
        send(user, "抱歉，服务出现异常，请稍后重试。")

@app.route("/wx", methods=["GET", "POST"])
def wx_handler():
    """处理微信服务器请求"""
    if request.method == "GET":
        # 处理服务器配置验证
        params = request.args
        signature = params.get('signature', '')
        timestamp = params.get('timestamp', '')
        nonce = params.get('nonce', '')
        echostr = params.get('echostr', '')
        
        # 验证签名
        tmp_list = [token, timestamp, nonce]
        tmp_list.sort()
        tmp_str = ''.join(tmp_list)
        if sha1(tmp_str.encode('utf-8')).hexdigest() == signature:
            return echostr
        return 'error'
        
    # 处理POST请求
    try:
        xml_data = request.get_data(as_text=True)
        msg_dict = xmltodict.parse(xml_data)['xml']
        
        if msg_dict.get('MsgType') == 'text':
            chat(msg_dict.get('FromUserName'), msg_dict.get('Content'))
        
        return 'success'
    except Exception as e:
        logging.error("Error processing request: %s", e)
        return 'error'

if __name__ == '__main__':
    app.run(host="127.0.0.1", port=8081, debug=True)

