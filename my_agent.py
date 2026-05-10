from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI
import re
import os
import json
import io
import contextlib
import requests
from urllib.parse import quote

app = Flask(__name__)

DEEPSEEK_API_KEY = "sk-821d2c47b2df4d5e8519fa0723424e3d"
client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

MEMORY_FILE = "memory.json"

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"preferences": {}, "history": []}

def save_memory(memory):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)

def update_preference(memory, key, value):
    memory["preferences"][key] = value
    save_memory(memory)
    return f"✅ 已记住：{key} = {value}"

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>🍊 小橘 | 智能修复版</title>
    <style>
        body {
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            font-family: system-ui;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }
        .chat-container {
            width: 900px;
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 32px;
            overflow: hidden;
        }
        .chat-header {
            background: #0f3460;
            padding: 20px;
            text-align: center;
            color: white;
            font-size: 24px;
        }
        .chat-messages {
            height: 400px;
            overflow-y: auto;
            padding: 20px;
            background: rgba(0,0,0,0.3);
        }
        .message {
            margin-bottom: 15px;
        }
        .user-message {
            text-align: right;
        }
        .user-message .bubble {
            background: #00b4d8;
            color: white;
            display: inline-block;
            padding: 10px 16px;
            border-radius: 20px;
        }
        .agent-message .bubble {
            background: #e0e0e0;
            color: #1a1a2e;
            display: inline-block;
            padding: 10px 16px;
            border-radius: 20px;
        }
        .input-area {
            display: flex;
            padding: 20px;
            background: #0f3460;
            gap: 10px;
        }
        .input-area input {
            flex: 1;
            padding: 12px;
            border: none;
            border-radius: 28px;
            outline: none;
        }
        .input-area button {
            padding: 12px 24px;
            border: none;
            border-radius: 28px;
            background: #00b4d8;
            color: white;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">🍊 小橘 | 智能修复版</div>
        <div class="chat-messages" id="messages">
            <div class="agent-message"><div class="bubble">🍊 我是小橘，我能聊天、查天气、干活、搜索。<br>试试「你好」「沈阳天气」「帮我整理桌面」「王者荣耀」</div></div>
        </div>
        <div class="input-area">
            <input type="text" id="taskInput" placeholder="说点什么..." onkeypress="if(event.keyCode==13) send()">
            <button onclick="send()">发送</button>
        </div>
    </div>
    <script>
        async function send() {
            const input = document.getElementById('taskInput');
            const task = input.value.trim();
            if (!task) return;
            addMessage('user', task);
            input.value = '';
            const response = await fetch('/run', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({task: task})
            });
            const data = await response.json();
            if (data.output) {
                addMessage('agent', data.output);
            } else if (data.error) {
                addMessage('agent', '❌ ' + data.error);
            }
        }
        function addMessage(role, text) {
            const div = document.createElement('div');
            div.className = role + '-message';
            div.innerHTML = '<div class="bubble">' + text + '</div>';
            document.getElementById('messages').appendChild(div);
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

@app.route('/run', methods=['POST'])
def run():
    task = request.get_json().get('task', '')

    # 记忆指令
    if task.startswith("记住"):
        if "=" not in task:
            return jsonify({'output': '格式：记住 偏好名 = 值'})
        parts = task.split("=", 1)
        key = parts[0].replace("记住", "").strip()
        value = parts[1].strip()
        memory = load_memory()
        msg = update_preference(memory, key, value)
        return jsonify({'output': msg})

    # 干活任务
    for kw in ['整理', '移动', '删除', '桌面', '下载', 'C盘', '空间']:
        if kw in task:
            try:
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "system", "content": "只返回Python代码，不要解释。"}, {"role": "user", "content": task}]
                )
                code = response.choices[0].message.content
                code = re.sub(r'^python\s*\n', '', code.strip())
                f = io.StringIO()
                with contextlib.redirect_stdout(f):
                    exec(code, {})
                    output = f.getvalue()
                    return jsonify({'output': output if output.strip() else "✅ 执行完成"})
            except Exception as e:
                return jsonify({'error': f"执行出错：{str(e)}"})

    # 天气任务
    if '天气' in task:
        import re
        city_match = re.search(r'([\u4e00-\u9fa5]{2,5})(?:天气|明天|后天)?', task)
        city = city_match.group(1) if city_match else "沈阳"
        try:
            url = f"https://wttr.in/{city}?format=3"
            r = requests.get(url, timeout=5)
            return jsonify({'output': f"🌤️ {city}天气：{r.text.strip()}"})
        except:
            return jsonify({'output': f"⚠️ 天气服务暂时不可用，试试「{city}天气」"})

    # 游戏任务
    if '游戏' in task or '接星星' in task:
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "system", "content": "只返回完整HTML游戏代码，不要解释。"}, {"role": "user", "content": task}]
            )
            html = response.choices[0].message.content
            match = re.search(r'<!DOCTYPE html>.*?</html>', html, re.DOTALL)
            if match:
                html = match.group(0)
            return jsonify({'html': html})
        except:
            return jsonify({'error': '游戏生成失败'})

    # 默认：AI 聊天（不搜索）
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "system", "content": "你叫小橘，是用户的个人AI助手，友好可爱。正常聊天，不要说代码，不要主动搜索。"}, {"role": "user", "content": task}]
        )
        return jsonify({'output': response.choices[0].message.content})
    except:
        return jsonify({'error': 'AI 聊天失败'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)