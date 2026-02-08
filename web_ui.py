"""
Web UI for Telegram bot - looks like Telegram interface.
Connects to bot API for real data.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os

web_app = FastAPI()

API_URL = os.getenv("API_URL", "http://localhost:8000")


@web_app.get("/", response_class=HTMLResponse)
async def root():
    return f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Финансовый Бот 📈</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}

            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
                background: #f5f5f5;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                padding: 20px;
            }}

            .chat-container {{
                width: 100%;
                max-width: 500px;
                background: white;
                border-radius: 12px;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
                display: flex;
                flex-direction: column;
                height: 80vh;
                max-height: 700px;
            }}

            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 16px;
                border-radius: 12px 12px 0 0;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}

            .header h1 {{
                font-size: 18px;
                font-weight: 600;
            }}

            .header .status {{
                font-size: 12px;
                opacity: 0.9;
            }}

            .messages {{
                flex: 1;
                overflow-y: auto;
                padding: 16px;
                display: flex;
                flex-direction: column;
                gap: 12px;
            }}

            .message {{
                display: flex;
                gap: 8px;
                margin-bottom: 4px;
            }}

            .message.bot {{
                justify-content: flex-start;
            }}

            .message.user {{
                justify-content: flex-end;
            }}

            .message-bubble {{
                max-width: 70%;
                padding: 10px 12px;
                border-radius: 12px;
                word-wrap: break-word;
                line-height: 1.4;
                font-size: 15px;
            }}

            .message.bot .message-bubble {{
                background: #e5e5ea;
                color: #000;
            }}

            .message.user .message-bubble {{
                background: #667eea;
                color: white;
            }}

            .buttons-container {{
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
                margin-top: 8px;
                flex-direction: column;
            }}

            .button {{
                background: #667eea;
                border: none;
                color: white;
                padding: 12px 16px;
                border-radius: 20px;
                cursor: pointer;
                font-size: 14px;
                font-weight: 500;
                transition: all 0.2s;
                width: 100%;
                text-align: center;
            }}

            .button:hover {{
                background: #5568d3;
                transform: translateY(-2px);
                box-shadow: 0 4px 8px rgba(102, 126, 234, 0.3);
            }}

            .button:disabled {{
                background: #ccc;
                cursor: not-allowed;
                transform: none;
            }}

            .button-inline {{
                display: inline-block;
                width: auto;
            }}

            .button-row {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 8px;
                width: 100%;
            }}

            .button-row .button {{
                width: 100%;
            }}

            .input-area {{
                border-top: 1px solid #e5e5ea;
                padding: 12px;
                display: flex;
                gap: 8px;
                background: #f9f9f9;
                border-radius: 0 0 12px 12px;
            }}

            .input-area input {{
                flex: 1;
                border: 1px solid #d0d0d5;
                border-radius: 20px;
                padding: 10px 16px;
                font-size: 15px;
                outline: none;
                transition: border-color 0.2s;
            }}

            .input-area input:focus {{
                border-color: #667eea;
            }}

            .input-area button {{
                background: #667eea;
                border: none;
                color: white;
                width: 36px;
                height: 36px;
                border-radius: 50%;
                cursor: pointer;
                font-size: 18px;
                transition: background 0.2s;
                display: flex;
                align-items: center;
                justify-content: center;
            }}

            .input-area button:hover {{
                background: #5568d3;
            }}

            .input-area button:disabled {{
                background: #ccc;
                cursor: not-allowed;
            }}

            .messages::-webkit-scrollbar {{
                width: 6px;
            }}

            .messages::-webkit-scrollbar-track {{
                background: transparent;
            }}

            .messages::-webkit-scrollbar-thumb {{
                background: #d0d0d5;
                border-radius: 3px;
            }}

            .messages::-webkit-scrollbar-thumb:hover {{
                background: #b0b0b5;
            }}

            .welcome-message {{
                text-align: center;
                color: #999;
                padding: 20px;
                font-size: 14px;
            }}

            .loading {{
                display: inline-block;
                width: 8px;
                height: 8px;
                background: #667eea;
                border-radius: 50%;
                margin: 0 2px;
                animation: bounce 1.4s ease-in-out infinite;
            }}

            .loading:nth-child(1) {{
                animation-delay: 0s;
            }}

            .loading:nth-child(2) {{
                animation-delay: 0.2s;
            }}

            .loading:nth-child(3) {{
                animation-delay: 0.4s;
            }}

            @keyframes bounce {{
                0%, 80%, 100% {{
                    opacity: 0.3;
                    transform: scale(0.8);
                }}
                40% {{
                    opacity: 1;
                    transform: scale(1);
                }}
            }}

            @media (max-width: 480px) {{
                .chat-container {{
                    height: 100vh;
                    max-height: none;
                    border-radius: 0;
                }}

                .header {{
                    border-radius: 0;
                }}

                .input-area {{
                    border-radius: 0;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="chat-container">
            <div class="header">
                <h1>📈 Финансовый Бот</h1>
                <div class="status" id="status">🔄 Подключение...</div>
            </div>

            <div class="messages" id="messages"></div>

            <div class="input-area">
                <input type="text" id="input" placeholder="Введите сообщение..." onkeypress="handleKeyPress(event)">
                <button id="sendBtn" onclick="sendMessage()">➤</button>
            </div>
        </div>

        <script>
            const API_URL = "{API_URL}";
            const messagesDiv = document.getElementById('messages');
            const inputField = document.getElementById('input');
            const statusDiv = document.getElementById('status');
            const sendBtn = document.getElementById('sendBtn');
            let isLoading = false;

            // Check API connection
            async function checkConnection() {{
                try {{
                    const res = await fetch(`${{API_URL}}/api/status`);
                    if (res.ok) {{
                        statusDiv.textContent = '🟢 Online';
                        statusDiv.style.color = '#4caf50';
                        // Load main menu
                        loadMainMenu();
                    }}
                }} catch (e) {{
                    statusDiv.textContent = '🔴 Offline';
                    statusDiv.style.color = '#f44336';
                    messagesDiv.innerHTML = '<div class="welcome-message">⚠️ Бот недоступен. Проверьте соединение.</div>';
                }}
            }}

            function addMessage(text, isUser = false, buttons = null) {{
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${{isUser ? 'user' : 'bot'}}`;
                
                const bubble = document.createElement('div');
                bubble.className = 'message-bubble';
                bubble.innerHTML = text;
                
                if (buttons && !isUser) {{
                    const buttonsDiv = document.createElement('div');
                    buttonsDiv.className = 'buttons-container';
                    buttons.forEach(btn => {{
                        const button = document.createElement('button');
                        button.className = 'button';
                        button.textContent = btn.text;
                        button.onclick = () => handleAction(btn.action);
                        buttonsDiv.appendChild(button);
                    }});
                    bubble.appendChild(buttonsDiv);
                }}
                
                messageDiv.appendChild(bubble);
                messagesDiv.appendChild(messageDiv);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            }}

            async function handleAction(action) {{
                setLoading(true);
                try {{
                    const res = await fetch(`${{API_URL}}/api/action`, {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{action, user_id: 123456}})
                    }});
                    
                    const data = await res.json();
                    addMessage(data.text || 'Error');
                    
                    if (data.buttons) {{
                        setTimeout(() => {{
                            messagesDiv.lastChild.querySelector('.message-bubble').innerHTML += '<div class="buttons-container" id="temp"></div>';
                            const buttonsDiv = messagesDiv.lastChild.querySelector('#temp');
                            buttonsDiv.id = '';
                            data.buttons.forEach(btn => {{
                                const button = document.createElement('button');
                                button.className = 'button';
                                button.textContent = btn.text;
                                button.onclick = () => handleAction(btn.action);
                                buttonsDiv.appendChild(button);
                            }});
                        }}, 100);
                    }}
                    
                    if (data.input) {{
                        inputField.focus();
                    }}
                }} catch (e) {{
                    addMessage('❌ Ошибка: ' + e.message);
                }} finally {{
                    setLoading(false);
                }}
            }}

            function loadMainMenu() {{
                messagesDiv.innerHTML = '';
                addMessage('Я финансовый помощник по акциям.');
                addMessage('Могу сделать теханализ акции, AI-обзор новостей и разбор портфеля.');
                handleAction('nav:main');
            }}

            async function sendMessage() {{
                const text = inputField.value.trim();
                if (!text || isLoading) return;
                
                addMessage(text, true);
                inputField.value = '';
                setLoading(true);
                
                try {{
                    const res = await fetch(`${{API_URL}}/api/chat`, {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{message: text, user_id: 123456}})
                    }});
                    
                    const data = await res.json();
                    addMessage(data.response || '❌ No response');
                }} catch (e) {{
                    addMessage('❌ Ошибка: ' + e.message);
                }} finally {{
                    setLoading(false);
                    inputField.focus();
                }}
            }}

            function setLoading(loading) {{
                isLoading = loading;
                sendBtn.disabled = loading;
                inputField.disabled = loading;
            }}

            function handleKeyPress(event) {{
                if (event.key === 'Enter' && !isLoading) {{
                    sendMessage();
                }}
            }}

            // Initialize
            window.addEventListener('load', () => {{
                checkConnection();
                inputField.focus();
            }});
        </script>
    </body>
    </html>
    """


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(web_app, host="0.0.0.0", port=8001)
