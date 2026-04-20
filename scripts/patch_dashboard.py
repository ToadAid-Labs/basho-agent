import re

with open('backend/templates/dashboard.html', 'r') as f:
    content = f.read()

# Add CSS for chat widget
chat_css = """
        /* Chat Widget Styles */
        .chat-widget {
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 350px;
            height: 500px;
            background: #16213e;
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            display: flex;
            flex-direction: column;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            z-index: 1000;
            overflow: hidden;
            transition: transform 0.3s ease;
            transform: translateY(calc(100% - 50px));
        }

        .chat-widget.open {
            transform: translateY(0);
        }

        .chat-header {
            background: linear-gradient(90deg, #1a1a2e, #16213e);
            padding: 15px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            font-weight: bold;
        }
        
        .chat-header:hover {
            background: rgba(255, 255, 255, 0.05);
        }

        .chat-messages {
            flex: 1;
            padding: 15px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .message {
            max-width: 80%;
            padding: 10px 15px;
            border-radius: 12px;
            font-size: 0.9em;
            line-height: 1.4;
            word-wrap: break-word;
        }

        .message.user {
            background: rgba(0, 212, 255, 0.1);
            color: #00d4ff;
            align-self: flex-end;
            border-bottom-right-radius: 2px;
        }

        .message.agent {
            background: rgba(255, 255, 255, 0.05);
            color: #e0e0e0;
            align-self: flex-start;
            border-bottom-left-radius: 2px;
        }

        .chat-input {
            padding: 15px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            display: flex;
            gap: 10px;
        }

        .chat-input input {
            flex: 1;
            padding: 10px;
            border-radius: 6px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            background: rgba(0, 0, 0, 0.2);
            color: white;
            outline: none;
        }

        .chat-input button {
            padding: 10px 15px;
            border-radius: 6px;
            border: none;
            background: #00d4ff;
            color: #1a1a2e;
            font-weight: bold;
            cursor: pointer;
            transition: background 0.3s;
        }

        .chat-input button:hover {
            background: #00b8e6;
        }
        
        .typing-indicator {
            font-size: 0.8em;
            color: #888;
            font-style: italic;
            display: none;
            margin-top: 5px;
        }
"""

# Add HTML for chat widget
chat_html = """
    <!-- Chat Widget -->
    <div class="chat-widget" id="chatWidget">
        <div class="chat-header" onclick="toggleChat()">
            <span>🤖 Trade Agent</span>
            <span id="chatToggleIcon">▲</span>
        </div>
        <div class="chat-messages" id="chatMessages">
            <div class="message agent">Hello! I am your AI Trading Agent. Ask me to check prices, execute a trade, or analyze your portfolio.</div>
        </div>
        <div class="typing-indicator" id="typingIndicator">Agent is typing...</div>
        <div class="chat-input">
            <input type="text" id="chatInput" placeholder="Ask agent..." onkeypress="handleChatKeyPress(event)">
            <button onclick="sendChatMessage()">Send</button>
        </div>
    </div>
"""

# Add JS for chat widget
chat_js = """
        // Chat Widget Logic
        function toggleChat() {
            const widget = document.getElementById('chatWidget');
            const icon = document.getElementById('chatToggleIcon');
            widget.classList.toggle('open');
            icon.textContent = widget.classList.contains('open') ? '▼' : '▲';
            if (widget.classList.contains('open')) {
                document.getElementById('chatInput').focus();
            }
        }

        function handleChatKeyPress(event) {
            if (event.key === 'Enter') {
                sendChatMessage();
            }
        }

        async function sendChatMessage() {
            const input = document.getElementById('chatInput');
            const message = input.value.trim();
            if (!message) return;

            input.value = '';
            appendMessage('user', message);
            document.getElementById('typingIndicator').style.display = 'block';
            scrollToBottom();

            try {
                const response = await fetch('/api/agent/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        message: message,
                        telegram_id: telegramId
                    })
                });
                
                const data = await response.json();
                document.getElementById('typingIndicator').style.display = 'none';
                
                if (data.error) {
                    appendMessage('agent', 'Error: ' + data.error);
                } else {
                    appendMessage('agent', data.response);
                    // Reload dashboard to reflect any potential portfolio changes
                    loadDashboard(); 
                }
            } catch (error) {
                document.getElementById('typingIndicator').style.display = 'none';
                appendMessage('agent', 'Connection error: ' + error.message);
            }
            scrollToBottom();
        }

        function appendMessage(sender, text) {
            const messages = document.getElementById('chatMessages');
            const msgDiv = document.createElement('div');
            msgDiv.className = `message ${sender}`;
            
            // Basic markdown/line break conversion
            const formattedText = text.replace(/\\n/g, '<br>').replace(/\\*\\*(.*?)\\*\\*/g, '<b>$1</b>');
            msgDiv.innerHTML = formattedText;
            
            messages.appendChild(msgDiv);
        }

        function scrollToBottom() {
            const messages = document.getElementById('chatMessages');
            messages.scrollTop = messages.scrollHeight;
        }
"""

# Inject into content
if "chat-widget" not in content:
    content = content.replace("</style>", chat_css + "\n    </style>")
    content = content.replace("</body>", chat_html + "\n</body>")
    content = content.replace("document.addEventListener('DOMContentLoaded', loadDashboard);", chat_js + "\n        document.addEventListener('DOMContentLoaded', loadDashboard);")
    
    with open('backend/templates/dashboard.html', 'w') as f:
        f.write(content)
    print("Chat widget added to dashboard.html")
else:
    print("Chat widget already exists")
