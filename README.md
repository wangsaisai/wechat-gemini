# 微信公众号 Gemini AI 助手

一个基于 Google Gemini AI 的微信公众号智能对话助手。

## 功能特点

- 支持与 Gemini AI 进行智能对话（支持文字，图片，语言）
- 支持单次对话和连续对话模式
- 自动处理长消息的分段发送
- 支持 Markdown 格式转换
- 简单易部署，无需额外数据库

## 快速开始

### 1. 环境要求
- Python 3.8+
- 微信公众号账号
- Google Gemini API Key

### 2. 安装依赖 
```bash
pip install -r requirements.txt
```

### 3. 配置文件
创建 `conf.json` 文件：
```json
{
    "app_id": "你的公众号APPID",
    "app_secret": "你的公众号APP Secret",
    "token": "你的公众号Token",
    "encoding_aes_key": "你的公众号消息加解密密钥",
    "genimi": {
        "api_key": "你的Gemini API Key"
    },
    "safety_settings": [
        {
            "category": "HARM_CATEGORY_HARASSMENT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        },
        {
            "category": "HARM_CATEGORY_HATE_SPEECH",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        },
        {
            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        },
        {
            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        }
    ],
    "generation_config": {
        "temperature": 0.9,
        "top_p": 1,
        "top_k": 1,
        "max_output_tokens": 8192
    }
}
```

### 4. 运行服务
```bash
python app_dict.py
```

### 5. 配置公众号
1. 登录微信公众平台
2. 配置服务器地址：`http(s)://你的域名/wx`
3. 配置 Token 和消息加解密密钥
4. 开启服务器配置

## 使用说明

### 基本对话
直接发送消息给公众号即可开始对话。

### 连续对话模式
- 发送 `#开始` 进入连续对话模式
- 在连续对话模式中，AI 会记住上下文
- 发送 `#结束` 结束连续对话模式

## 注意事项

1. 请确保 Gemini API Key 的安全性
2. 建议使用 HTTPS 协议
3. 注意微信公众号的消息限制：
   - 服务端口号，必须为 `80(http)` 或 `443(https)`
   - 单条消息最大长度限制
   - 每日调用次数限制
   - 消息响应时间限制（`5秒`），客服消息接口无此限制（访问AI时使用客服消息接口）

## 错误处理

查看 `debug.log` 文件获取详细的错误信息。

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

如有问题，请提交 Issue。
