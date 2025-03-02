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
model = genai.GenerativeModel('gemini-2.0-flash-lite', 
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

# 使用客服消息接口进行异步回复：原因如下
# https://developers.weixin.qq.com/doc/offiaccount/Message_Management/Passive_user_reply_message.html
# 假如服务器无法保证在五秒内处理并回复,必须做出下述回复,这样微信服务器才不会对此作任何处理,并且不会发起重试(这种情况下,可以使用客服消息接口进行异步回复),否则,将出现严重的错误提示。
# 详见下面说明: 
# 1、直接回复success(推荐方式) 2、直接回复空串(指字节长度为0的空字符串,而不是XML结构体中content字段的内容为空) 
# 一旦遇到以下情况,微信都会在公众号会话中,向用户下发系统提示“该公众号暂时无法提供服务,请稍后再试”
# 1、开发者在5秒内未回复任何内容 2、开发者回复了异常数据，比如JSON数据等
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
                # 如果是token过期错误(errcode=40001)，应该刷新token后重试
                if response.get('errcode') == 40001:
                    token_manager.access_token = None
                    return send(user, message, message_type)
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

def clean_chat():
    # 添加会话数量限制
    if len(user2session) > 10000:  # 设置合理的最大会话数
        # 清理最早的会话
        oldest_users = sorted(user2session.keys())[:1000]  # 清理1000个最早的会话
        for old_user in oldest_users:
            user2session.pop(old_user, None)

def chat(user, message, image_url=None):
    clean_chat()
    
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
        
        # 处理带图片的消息
        if image_url:
            try:
                image_data = requests.get(image_url).content
                response = model.generate_content([message, image_data]).text
            except Exception as e:
                logging.error("Error processing image: %s", e)
                response = "抱歉，图片处理失败，请稍后重试。"
        else:
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

        user = msg_dict.get('FromUserName')
        to_user = msg_dict.get('ToUserName')
        msg_type = msg_dict.get('MsgType')

        # 仅在不支持的消息类型时使用XML回复，其他情况使用客服消息接口
        response_text = None

        if msg_type == 'text':
            content = msg_dict.get('Content')
            chat(user, content)
            return 'success'  # 直接返回成功，回复通过客服消息接口发送
            
        elif msg_type == 'voice':
            # 获取语音识别结果
            content = msg_dict.get('Recognition', '未能识别语音内容')
            chat(user, content)
            return 'success'  # 直接返回成功，回复通过客服消息接口发送
            
        elif msg_type == 'image':
            # 获取图片URL
            pic_url = msg_dict.get('PicUrl')
            chat(user, "请描述这张图片", image_url=pic_url)
            return 'success'  # 直接返回成功，回复通过客服消息接口发送
        
        else:
            response_text = "抱歉，暂不支持此类型的消息。"

        # 只有在设置了response_text时才构造XML返回
        # 该返回方式必须在5s内返回（微信限制），否则用户无法接收消息。AI处理消息耗时很容易超过5s, 调AI接口时走客户消息接口，不使用此方式
        if response_text:
            reply = {
                'xml': {
                    'ToUserName': user,
                    'FromUserName': to_user,
                    'CreateTime': str(int(time.time())),
                    'MsgType': 'text',
                    'Content': response_text
                }
            }
            return xmltodict.unparse(reply)
        
        return 'success'
    except Exception as e:
        logging.error("Error processing request: %s", e)
        return 'error'

if __name__ == '__main__':
    # 微信限制了端口号必须是 80(http) 或 443(https)
    app.run(host="0.0.0.0", port=80, debug=False)

