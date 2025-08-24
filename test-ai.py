#!/usr/bin/env python3
"""
Простой скрипт для тестирования AI chat endpoints
"""

import requests
import json
import time
from typing import Dict, Any

# Конфигурация
BASE_URL = "http://127.0.0.1:8000"
TEST_TOKEN = "mock_token_123456789"

# Заголовки для авторизации
HEADERS = {
    "Authorization": f"Bearer {TEST_TOKEN}",
    "Content-Type": "application/json"
}


def test_endpoint(method: str, endpoint: str, data: Dict[Any, Any] = None) -> Dict[Any, Any]:
    """Тестирует конкретный endpoint"""
    url = f"{BASE_URL}{endpoint}"

    print(f"\n🧪 Тестируем: {method.upper()} {endpoint}")

    try:
        if method.lower() == "get":
            response = requests.get(url, headers=HEADERS)
        elif method.lower() == "post":
            response = requests.post(url, headers=HEADERS, json=data)
        elif method.lower() == "delete":
            response = requests.delete(url, headers=HEADERS)
        else:
            print(f"❌ Неподдерживаемый метод: {method}")
            return {}

        print(f"📤 Отправлено: {json.dumps(data, ensure_ascii=False) if data else 'Нет данных'}")
        print(f"📥 Статус: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"✅ Ответ: {json.dumps(result, ensure_ascii=False, indent=2)}")
            return result
        else:
            print(f"❌ Ошибка: {response.text}")
            return {}

    except requests.exceptions.ConnectionError:
        print("❌ Не удается подключиться к серверу. Убедитесь, что сервер запущен.")
        return {}
    except Exception as e:
        print(f"❌ Произошла ошибка: {e}")
        return {}


def main():
    """Основная функция тестирования"""
    print("🤖 Тестирование AI Chat API")
    print("=" * 50)

    # Проверяем что сервер работает
    print("🔍 Проверяем работу сервера...")
    health = test_endpoint("GET", "/")
    if not health:
        print("❌ Сервер недоступен. Завершаем тесты.")
        return

    # Тест 1: Создание чата для инструмента
    print("\n" + "=" * 50)
    print("📝 ТЕСТ 1: Создание AI чата")
    tool_chat_data = {
        "tool_type": "coding",
        "tool_title": "Программирование",
        "description": "Тестовое описание для программирования",
        "is_tool_description": True
    }

    # Отправляем данные как параметры формы, а не JSON
    response = requests.post(
        f"{BASE_URL}/api/chat/create-tool-chat",
        headers=HEADERS,
        params=tool_chat_data
    )

    print(f"📤 Отправлено: {tool_chat_data}")
    print(f"📥 Статус: {response.status_code}")

    if response.status_code == 200:
        chat_result = response.json()
        print(f"✅ Создан чат: {json.dumps(chat_result, ensure_ascii=False, indent=2)}")
        chat_id = chat_result.get("chat_id")
    else:
        print(f"❌ Ошибка создания чата: {response.text}")
        chat_id = None

    # Тест 2: Генерация ответа ИИ
    print("\n" + "=" * 50)
    print("🧠 ТЕСТ 2: Генерация ответа ИИ")
    ai_response_data = {
        "message": "Привет! Как дела?",
        "context": {
            "tool_type": "coding",
            "chat_id": chat_id
        }
    }
    ai_response = test_endpoint("POST", "/api/ai/generate-response", ai_response_data)

    # Тест 3: Отправка промпта
    print("\n" + "=" * 50)
    print("📨 ТЕСТ 3: Отправка tool prompt")
    prompt_data = {
        "tool_type": "brainstorm",
        "description": "Мозговой штурм для новых идей",
        "chat_id": chat_id,
        "is_tool_description": True
    }
    prompt_response = test_endpoint("POST", "/api/chat/tool-prompt", prompt_data)

    # Тест 4: Получение истории чатов
    print("\n" + "=" * 50)
    print("📋 ТЕСТ 4: История чатов")
    history = test_endpoint("GET", "/api/users/chat-history?limit=5")

    # Тест 5: Отправка обычного сообщения в чат
    print("\n" + "=" * 50)
    print("💬 ТЕСТ 5: Отправка сообщения")
    message_data = {
        "message": "Тестовое сообщение для ИИ",
        "tool_type": "coding",
        "chat_id": chat_id
    }
    message_response = test_endpoint("POST", "/api/chat/send", message_data)

    # Debug endpoints
    print("\n" + "=" * 50)
    print("🔧 DEBUG: Получение всех AI чатов")
    debug_chats = test_endpoint("GET", "/api/debug/ai-chats")

    if chat_id:
        print(f"\n🔧 DEBUG: Получение конкретного чата {chat_id}")
        debug_chat = test_endpoint("GET", f"/api/debug/ai-chat/{chat_id}")

    # Итоги
    print("\n" + "=" * 50)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ")
    print("✅ Тесты завершены!")
    print("💡 Если есть ошибки, проверьте:")
    print("   • Запущен ли сервер на http://127.0.0.1:8000")
    print("   • Правильно ли настроены CORS")
    print("   • Валиден ли токен авторизации")


if __name__ == "__main__":
    main()