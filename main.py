from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid
import time
import random
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Для работы с фронтендом

# Временное хранилище (в продакшене используйте БД)
chat_storage = {}
message_storage = {}

# Заглушки для разных типов ИИ ответов
AI_RESPONSES = {
    "create_image": [
        "Отлично! Я могу создать для тебя изображение. Опиши подробно, что ты хочешь увидеть - стиль, цвета, композицию, настроение.",
        "Готов к созданию изображения! Расскажи детально о своей идее, и я воплощу её в картинке.",
        "Давай создадим что-то красивое! Опиши свою идею максимально подробно."
    ],
    "coding": [
        "Привет! Готов помочь с программированием. Какую задачу решаем? На каком языке программирования?",
        "Отлично! Я люблю кодить. Расскажи о своем проекте - что нужно сделать?",
        "Время программировать! 💻 Какая задача перед нами стоит?"
    ],
    "brainstorm": [
        "Супер! Обожаю мозговые штурмы 🧠 Какую область исследуем? О чем генерируем идеи?",
        "Отлично! Давай устроим настоящий взрыв креативности! Какая тема интересует?",
        "Готов к мозговому штурму! ⚡ По какому направлению будем генерировать идеи?"
    ],
    "excuse": [
        "Хаха, понимаю! 😄 Иногда нужна креативная отмазка. Расскажи ситуацию - придумаем что-то правдоподобное!",
        "Окей, давай подумаем над хорошей отмазкой! 😅 Что за ситуация?",
        "Понял задачу! Нужна качественная отмазка. Опиши обстоятельства."
    ]
}

GENERAL_RESPONSES = [
    "Интересный вопрос! Давай разберем его подробнее.",
    "Отлично! Я готов помочь. Расскажи больше деталей.",
    "Хороший запрос! Давай найдем лучшее решение вместе.",
    "Понял! Сейчас подумаем, как лучше подойти к этой задаче.",
    "Отличная идея для обсуждения! Что именно тебя интересует?"
]


def get_ai_response(message: str, tool_type: str = None) -> str:
    """Генерирует ответ ИИ на основе типа инструмента и сообщения"""

    # Имитируем время обработки
    time.sleep(random.uniform(0.5, 1.5))

    if tool_type and tool_type in AI_RESPONSES:
        responses = AI_RESPONSES[tool_type]
    else:
        responses = GENERAL_RESPONSES

    # Простая логика выбора ответа на основе длины сообщения
    if len(message) > 100:
        return f"{random.choice(responses)} Вижу, что у тебя довольно подробный запрос - это отлично! Дай мне немного времени обработать всю информацию."
    else:
        return random.choice(responses)


@app.route('/api/chat/create-tool-chat', methods=['POST'])
def create_tool_chat():
    """Создает новый чат для инструмента"""
    try:
        data = request.get_json()

        if not data or not data.get('tool_type'):
            return jsonify({"error": "Missing required fields"}), 400

        chat_id = str(uuid.uuid4())

        # Сохраняем информацию о чате
        chat_storage[chat_id] = {
            "chat_id": chat_id,
            "tool_type": data.get('tool_type'),
            "tool_title": data.get('tool_title'),
            "description": data.get('description'),
            "created_at": datetime.now().isoformat(),
            "messages": []
        }

        print(f"[DEBUG] Created tool chat: {chat_id} for tool: {data.get('tool_type')}")

        return jsonify({
            "chat_id": chat_id,
            "status": "created",
            "tool_type": data.get('tool_type'),
            "tool_title": data.get('tool_title')
        })

    except Exception as e:
        print(f"[ERROR] Failed to create tool chat: {e}")
        return jsonify({"error": "Failed to create chat"}), 500


@app.route('/api/chat/send', methods=['POST'])
def send_message():
    """Отправляет сообщение в чат"""
    try:
        data = request.get_json()

        if not data or not data.get('message'):
            return jsonify({"error": "Message is required"}), 400

        message_id = str(uuid.uuid4())
        chat_id = data.get('chat_id', str(uuid.uuid4()))

        # Создаем чат если его нет
        if chat_id not in chat_storage:
            chat_storage[chat_id] = {
                "chat_id": chat_id,
                "tool_type": data.get('tool_type'),
                "created_at": datetime.now().isoformat(),
                "messages": []
            }

        # Сохраняем сообщение
        message_data = {
            "message_id": message_id,
            "chat_id": chat_id,
            "message": data.get('message'),
            "tool_type": data.get('tool_type'),
            "timestamp": datetime.now().isoformat(),
            "type": "user"
        }

        chat_storage[chat_id]["messages"].append(message_data)
        message_storage[message_id] = message_data

        print(f"[DEBUG] Sent message to chat {chat_id}: {data.get('message')[:50]}...")

        return jsonify({
            "status": "sent",
            "message_id": message_id,
            "chat_id": chat_id,
            "timestamp": message_data["timestamp"]
        })

    except Exception as e:
        print(f"[ERROR] Failed to send message: {e}")
        return jsonify({"error": "Failed to send message"}), 500


@app.route('/api/ai/generate-response', methods=['POST'])
def generate_ai_response():
    """Генерирует ответ ИИ на сообщение пользователя"""
    try:
        data = request.get_json()

        if not data or not data.get('message'):
            return jsonify({"error": "Message is required"}), 400

        message = data.get('message')
        context = data.get('context', {})
        tool_type = context.get('tool_type')
        chat_id = context.get('chat_id')

        # Генерируем ответ (имитируем задержку)
        ai_message = get_ai_response(message, tool_type)

        response_id = str(uuid.uuid4())

        # Сохраняем ответ ИИ в чат если есть chat_id
        if chat_id and chat_id in chat_storage:
            ai_response_data = {
                "message_id": response_id,
                "chat_id": chat_id,
                "message": ai_message,
                "timestamp": datetime.now().isoformat(),
                "type": "assistant"
            }
            chat_storage[chat_id]["messages"].append(ai_response_data)

        print(f"[DEBUG] Generated AI response for chat {chat_id}: {ai_message[:50]}...")

        return jsonify({
            "message": ai_message,
            "response_id": response_id,
            "tool_type": tool_type,
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        print(f"[ERROR] Failed to generate AI response: {e}")
        return jsonify({"error": "Failed to generate response"}), 500


@app.route('/api/chat/tool-prompt', methods=['POST'])
def send_tool_prompt():
    """Отправляет промпт на основе описания инструмента"""
    try:
        data = request.get_json()

        if not data or not data.get('tool_type'):
            return jsonify({"error": "Tool type is required"}), 400

        chat_id = data.get('chat_id', str(uuid.uuid4()))

        # Создаем или обновляем чат
        if chat_id not in chat_storage:
            chat_storage[chat_id] = {
                "chat_id": chat_id,
                "tool_type": data.get('tool_type'),
                "created_at": datetime.now().isoformat(),
                "messages": []
            }

        print(f"[DEBUG] Sent tool prompt for chat {chat_id}, tool: {data.get('tool_type')}")

        return jsonify({
            "status": "sent",
            "chat_id": chat_id,
            "tool_type": data.get('tool_type'),
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        print(f"[ERROR] Failed to send tool prompt: {e}")
        return jsonify({"error": "Failed to send prompt"}), 500


@app.route('/api/users/chat-history', methods=['GET'])
def get_chat_history():
    """Получает историю чатов пользователя"""
    try:
        limit = int(request.args.get('limit', 10))
        offset = int(request.args.get('offset', 0))

        # Заглушка - возвращаем последние чаты
        all_chats = list(chat_storage.values())
        all_chats.sort(key=lambda x: x["created_at"], reverse=True)

        # Пагинация
        result_chats = all_chats[offset:offset + limit]

        # Формируем упрощенную информацию о чатах
        chat_history = []
        for chat in result_chats:
            last_message = chat["messages"][-1] if chat["messages"] else None

            chat_info = {
                "chat_id": chat["chat_id"],
                "title": chat.get("tool_title", "Чат"),
                "tool_type": chat.get("tool_type"),
                "last_message": last_message["message"] if last_message else None,
                "last_message_time": last_message["timestamp"] if last_message else chat["created_at"],
                "message_count": len(chat["messages"])
            }
            chat_history.append(chat_info)

        print(f"[DEBUG] Retrieved {len(chat_history)} chats from history")

        return jsonify(chat_history)

    except Exception as e:
        print(f"[ERROR] Failed to get chat history: {e}")
        return jsonify({"error": "Failed to get chat history"}), 500


# DEBUG endpoints
@app.route('/api/debug/chats', methods=['GET'])
def debug_get_all_chats():
    """DEBUG: Получить все чаты"""
    return jsonify({
        "total_chats": len(chat_storage),
        "chats": list(chat_storage.keys())
    })


@app.route('/api/debug/chat/<chat_id>', methods=['GET'])
def debug_get_chat(chat_id):
    """DEBUG: Получить конкретный чат"""
    if chat_id not in chat_storage:
        return jsonify({"error": "Chat not found"}), 404

    return jsonify(chat_storage[chat_id])


@app.route('/api/debug/clear-chats', methods=['DELETE'])
def debug_clear_chats():
    """DEBUG: Очистить все чаты"""
    chat_storage.clear()
    message_storage.clear()
    return jsonify({"status": "cleared", "message": "All chats cleared"})


# Обработчики ошибок
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500


if __name__ == '__main__':
    print("🤖 Starting AI Chat API server (Flask)...")
    print("📝 Available endpoints:")
    print("   POST /api/chat/create-tool-chat")