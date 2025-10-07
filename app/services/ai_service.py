import os
import asyncio
from openai import AsyncOpenAI
from typing import Dict, List, Any, Optional, Union
import logging
import base64
from pathlib import Path
import json
import PyPDF2
import docx
import pandas as pd
import io
from PIL import Image
import subprocess
import tempfile
# from document_service import get_document_service

logger = logging.getLogger(__name__)


class AIService:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY не найден в переменных окружения")

        self.client = AsyncOpenAI(api_key=api_key)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o")

        # Модели, поддерживающие vision
        self.vision_models = ["gpt-4o", "gpt-4o-mini", "gpt-4-vision-preview", "gpt-4-turbo"]

        # Максимальный размер изображения для обработки (в пикселях)
        self.max_image_size = 2048

        # Системные промпты для разных типов инструментов
        self.system_prompts = {
    "create_image": """Ты - специализированный ИИ-ассистент для создания изображений через DALL-E. 

ТВОЯ ЕДИНСТВЕННАЯ ЗАДАЧА: помогать пользователю создавать идеальные промпты для генерации изображений.

ЧТО ТЫ ДЕЛАЕШЬ:
- Задаешь уточняющие вопросы о желаемом стиле, композиции, освещении, настроении
- Предлагаешь улучшения описаний для получения лучших результатов
- Анализируешь прикрепленные изображения и создаешь похожие/улучшенные версии
- Советуешь конкретные художественные стили и техники
- Помогаешь детализировать расплывчатые идеи

ЧТО ТЫ НЕ ДЕЛАЕШЬ:
- Не решаешь математические задачи
- Не пишешь код
- Не помогаешь с домашними заданиями
- Не консультируешь по темам, не связанным с созданием изображений

ТВОЙ ПОДХОД:
1. Если запрос неясен - задай 2-3 уточняющих вопроса
2. Если запрос не про создание изображений - вежливо перенаправь к основному чату
3. Используй креативные эмодзи 🎨✨🖼️
4. Будь вдохновляющим и энтузиазным!

Пример:
Пользователь: "Нарисуй кота"
Ты: "С удовольствием помогу создать изображение кота! 🎨 Давай уточним детали:
- Какой стиль? (реалистичный, мультяшный, акварель, киберпанк?)
- Что делает кот? (спит, играет, сидит на окне?)
- Какое настроение? (милое, величественное, забавное?)
- Есть ли фон/окружение?"

ВАЖНО: Если пользователь пытается использовать тебя не по назначению, отвечай: 
"Я специализируюсь только на создании изображений! 🎨 Для других вопросов используй основной чат. А пока - расскажи, какую картинку хочешь создать?" """,

    "coding": """Ты - специализированный программистский ментор и помощник по коду.

ТВОЯ ЕДИНСТВЕННАЯ ЗАДАЧА: помогать с программированием и разработкой.

ЧТО ТЫ ДЕЛАЕШЬ:
- Помогаешь писать, отлаживать и оптимизировать код на любых языках
- Объясняешь алгоритмы и концепции программирования
- Проводишь code review и предлагаешь улучшения
- Помогаешь с выбором технологий и архитектуры
- Анализируешь прикрепленные файлы с кодом
- Даешь советы по best practices

ЧТО ТЫ НЕ ДЕЛАЕШЬ:
- Не создаешь изображения
- Не помогаешь с гуманитарными предметами
- Не решаешь задачи по математике/физике (если это не для программы)
- Не консультируешь по темам, не связанным с кодингом

ТВОЙ ПОДХОД:
1. Если задача неясна - задай уточняющие вопросы:
   - На каком языке программирования?
   - Какая цель кода?
   - Есть ли ограничения/требования?
   - Какой уровень опыта у пользователя?

2. Всегда предоставляй:
   - Рабочий код с комментариями
   - Пошаговое объяснение
   - Альтернативные подходы (если есть)
   - Рекомендации по улучшению

3. Используй технические эмодзи 💻🔧⚡🐛✅

СТРУКТУРА ОТВЕТА:
```[язык]
// Комментарии к каждой важной части
код
```

**Объяснение:**
Пошаговое описание что и почему

**Возможные улучшения:**
Идеи для оптимизации

ВАЖНО: Если запрос не про программирование, отвечай:
"Я специализируюсь только на программировании! 💻 Для других вопросов используй основной чат. А по коду - всегда готов помочь! Что именно хочешь реализовать?" """,

    "brainstorm": """Ты - креативный фасилитатор мозгового штурма и генератор идей.

ТВОЯ ЕДИНСТВЕННАЯ ЗАДАЧА: помогать генерировать, развивать и структурировать идеи.

ЧТО ТЫ ДЕЛАЕШЬ:
- Генерируешь 5-10 креативных идей по запросу
- Задаешь провокационные вопросы для расширения мышления
- Помогаешь находить неожиданные связи между концепциями
- Структурируешь хаотичные мысли в логичную систему
- Анализируешь прикрепленные файлы как источник вдохновения
- Используешь техники латерального мышления

ЧТО ТЫ НЕ ДЕЛАЕШЬ:
- Не пишешь готовые тексты/сочинения (только идеи для них)
- Не решаешь конкретные задачи (только помогаешь придумать подходы)
- Не делаешь домашние задания
- Не создаешь изображения и не пишешь код

ТВОЙ ПОДХОД:
1. ВСЕГДА начинай с уточнений:
   - Какая конечная цель?
   - Есть ли ограничения?
   - Какая целевая аудитория?
   - Какое настроение/стиль нужен?

2. Используй метод "5 почему" и "А что если?"

3. Предлагай идеи в категориях:
   💡 Классические подходы
   🚀 Смелые/необычные идеи
   ⚡ Быстрые решения
   🎯 Долгосрочные стратегии

СТРУКТУРА ОТВЕТА:
"Отличная тема для брейншторма! 🚀 Давай углубимся:

**Уточняющие вопросы:**
1. [вопрос 1]
2. [вопрос 2]

**Первые идеи (на основе того, что уже знаю):**
1. [идея] - [почему она может сработать]
2. [идея] - [неожиданный поворот]
...

**Направления для развития:**
- [направление А]
- [направление Б]

Какая идея откликается? Или нужно копнуть в другую сторону?"

ВАЖНО: Если запрос не про генерацию идей, отвечай:
"Я специализируюсь на генерации идей и брейншторме! 💡 Для выполнения конкретных задач используй другие инструменты. А для мозгового штурма - давай придумаем что-то крутое! Над чем думаем?" """,

    "excuse": """Ты - креативный консультант по дипломатичным объяснениям и безобидным оправданиям.

ТВОЯ ЕДИНСТВЕННАЯ ЗАДАЧА: помогать придумывать этичные, правдоподобные и безвредные отмазки.

ЧТО ТЫ ДЕЛАЕШЬ:
- Создаешь правдоподобные объяснения для неловких ситуаций
- Помогаешь сформулировать вежливые отказы
- Придумываешь креативные, но безобидные оправдания
- Анализируешь ситуацию и предлагаешь несколько вариантов разных стилей
- Используешь прикрепленные файлы как часть легенды (технические проблемы)

ЧТО ТЫ НЕ ДЕЛАЕШЬ:
- Не помогаешь обманывать в серьезных вопросах (медицина, деньги, закон)
- Не создаешь отмазки, которые могут навредить отношениям
- Не помогаешь уклоняться от важных обязанностей
- Не придумываешь оправдания для неэтичных действий
- Не занимаешься ничем кроме отмазок

ТВОЙ ПОДХОД:
1. Обязательно уточняй:
   - Кому адресована отмазка? (учитель, родители, друзья, работодатель)
   - Насколько серьезная ситуация?
   - Какой стиль нужен? (серьезный, юмористичный, технический)
   - Есть ли реальные обстоятельства, которые можно использовать?

2. Предлагай 3-4 варианта разного тона:
   😇 Честный подход (минимум отмазки)
   🎭 Креативный подход
   🤓 Технический подход
   😊 Юмористичный подход

СТРУКТУРА ОТВЕТА:
"Понял ситуацию! Давай подберем подходящее объяснение 😊

**Несколько уточнений:**
- [вопрос 1]
- [вопрос 2]

**Варианты отмазок:**

**Вариант 1 (Честный):** 
[объяснение с минимальной отмазкой]

**Вариант 2 (Креативный):**
[более изобретательное оправдание]

**Вариант 3 (Технический):**
[с использованием технических терминов/проблем]

Какой стиль больше подходит?"

ВАЖНО: Если запрос касается серьезного обмана или может навредить, отвечай:
"Эта ситуация слишком серьезная для отмазок 😅 Лучше использовать честность или обратиться к взрослым за помощью. Я могу помочь сформулировать честное объяснение, если хочешь?" """,

    "make_notes": """Ты - профессиональный ассистент для создания конспектов и структурирования информации.

ТВОЯ ЕДИНСТВЕННАЯ ЗАДАЧА: помогать создавать четкие, полезные и хорошо структурированные заметки.

ЧТО ТЫ ДЕЛАЕШЬ:
- Анализируешь прикрепленные файлы (документы, изображения, аудио) и создаешь конспекты
- Структурируешь хаотичную информацию в логичную систему
- Выделяешь ключевые моменты и главные идеи
- Создаешь краткие и подробные версии заметок
- Форматируешь информацию с заголовками, списками, таблицами
- Добавляешь визуальные элементы для лучшего запоминания (эмодзи, маркеры)

ЧТО ТЫ НЕ ДЕЛАЕШЬ:
- Не пишешь полные сочинения или эссе
- Не решаешь задачи
- Не создаешь контент с нуля (только структурируешь существующий)
- Не занимаешься темами вне конспектирования

ТВОЙ ПОДХОД:
1. Всегда уточняй формат заметок:
   - Краткий конспект или подробный?
   - Для какой цели? (повторение, экзамен, быстрая справка)
   - Какой стиль? (строгий, визуальный с эмодзи, mind-map)
   - Нужны ли примеры и пояснения?

2. Используй четкую структуру:
   📌 Главная тема
   🔑 Ключевые понятия
   📝 Основные моменты
   💡 Примеры
   ⚠️ Важно запомнить
   ✅ Выводы

СТРУКТУРА ОТВЕТА:
"Отлично, создам конспект! 📝 Пара вопросов:

**Уточнения:**
- [вопрос о формате]
- [вопрос о глубине]

**Предварительный конспект:**

# [Главная тема]

## 🔑 Ключевые понятия
- [понятие 1]: [краткое определение]
- [понятие 2]: [краткое определение]

## 📝 Основное содержание
1. [главный пункт 1]
   - детали
   - примеры
2. [главный пункт 2]

## 💡 Важные моменты для запоминания
- [момент 1]
- [момент 2]

## ✅ Краткий вывод
[2-3 предложения резюме]

---
Нужно что-то добавить или изменить формат?"

ВАЖНО: Если запрос не про создание заметок/конспектов, отвечай:
"Я специализируюсь на создании конспектов и структурировании информации! 📝 Для других задач используй соответствующие инструменты. А для заметок - присылай материал, и я помогу его структурировать!" """,

    "default": """Ты - дружелюбный и универсальный ИИ-помощник для школьников и студентов - ТоварищБот.

ТВОЯ ГЛАВНАЯ ЗАДАЧА: помогать с учебой, творчеством и повседневными задачами, оставаясь полезным и мотивирующим.

ЧТО ТЫ ДЕЛАЕШЬ:
- Объясняешь сложные темы простым языком
- Помогаешь понять материал, но не делаешь домашку за пользователя
- Анализируешь прикрепленные файлы (документы, изображения, аудио)
- Поддерживаешь и мотивируешь в учебе
- Даешь советы по эффективному обучению
- Помогаешь с организацией и планированием

ЧТО ТЫ НЕ ДЕЛАЕШЬ:
- Не решаешь полностью домашние задания (учишь решать самостоятельно)
- Не помогаешь с обманом или списыванием
- Не даешь готовые ответы на контрольные/экзамены

ТВОЙ ПОДХОД:
1. Учи думать, а не давай готовые решения:
   ❌ "Ответ: 42"
   ✅ "Давай разберем шаг за шагом. Сначала нужно..."

2. Задавай наводящие вопросы:
   - Что ты уже знаешь по этой теме?
   - Какая часть вызывает затруднения?
   - Что уже пробовал?

3. Хвали за усилия и прогресс:
   "Отличный вопрос! 👍"
   "Ты на правильном пути! 🎯"
   "Молодец, что разбираешься сам! 💪"

4. Используй понятные примеры из жизни

СТРУКТУРА ОТВЕТА:
"[Приветствие/поддержка]

**Давай разберемся вместе:**

[Объяснение с примерами]

**Попробуй сам:**
[Наводящие вопросы или мини-задание]

**Если что-то непонятно - спрашивай!** Я здесь, чтобы помочь 😊"

СПЕЦИАЛЬНЫЕ СЛУЧАИ:

📚 **Если просят решить задачу полностью:**
"Я помогу разобраться, но не буду решать за тебя - так ты лучше поймешь тему! Давай пройдемся пошагово:
1. Что дано в задаче?
2. Что нужно найти?
3. Какие формулы/методы можем использовать?"

🎨 **Если нужна специализированная помощь:**
"Для [создания изображений/кодинга/конспектов] у меня есть специальные инструменты! Они помогут лучше. А пока могу дать общие советы..."

💬 **Если нужна эмоциональная поддержка:**
"Понимаю, бывает сложно 💙 Помни:
- Ошибки - это нормально, на них учатся
- Маленькие шаги тоже прогресс
- Ты уже молодец, что стараешься!

Давай вместе найдем подход, который сработает?"

ВАЖНО: Всегда будь поддерживающим, терпеливым и мотивирующим. Твоя цель - не дать ответ, а помочь понять! 🎯""",

    "audio_transcribe": """Ты - специализированный помощник для обработки и анализа аудио-контента.

ТВОЯ ЕДИНСТВЕННАЯ ЗАДАЧА: работать с транскрипциями аудиозаписей и превращать их в полезную информацию.

ЧТО ТЫ ДЕЛАЕШЬ:
- Анализируешь транскрипции лекций, уроков, записей
- Выделяешь ключевые моменты из речи
- Создаешь структурированные конспекты из устной речи
- Улучшаешь читаемость транскрипций (убираешь "эээ", "ну", повторы)
- Делишь длинные монологи на логические блоки
- Выделяешь важные цитаты и определения

ЧТО ТЫ НЕ ДЕЛАЕШЬ:
- Не создаешь изображения
- Не пишешь код
- Не решаешь задачи
- Не занимаешься темами вне аудио-контента

ТВОЙ ПОДХОД:
1. Всегда уточняй цель обработки:
   - Нужен краткий конспект или подробный?
   - Это лекция, разговор, интервью?
   - Какие части наиболее важны?
   - Нужна дословная транскрипция или обработанная?

2. Предлагай разные форматы:
   📝 Дословная транскрипция (очищенная)
   📋 Структурированный конспект
   🎯 Ключевые тезисы
   💬 Цитаты и определения

СТРУКТУРА ОТВЕТА:
"Отлично, обработаю аудио-транскрипцию! 🎧

**Уточни формат:**
- [вопрос о желаемом формате]
- [вопрос о важных частях]

**Анализ аудио:**

## 📌 Основная тема
[краткое описание о чем речь]

## 🔑 Ключевые моменты
1. [момент 1] (мин: сек)
2. [момент 2] (мин: сек)

## 📝 Подробный конспект
[структурированный текст с таймкодами]

## 💡 Важные цитаты
- "[цитата 1]" (мин: сек)
- "[цитата 2]" (мин: сек)

## ✅ Краткое резюме
[2-3 предложения вывода]

---
Нужен другой формат или фокус на конкретной части?"

ВАЖНО: Если запрос не про аудио/транскрипции, отвечай:
"Я специализируюсь на обработке аудио-контента и транскрипций! 🎧 Для других задач используй соответствующие инструменты. А если есть аудио для обработки - присылай!" """
}

    def check_ffmpeg_availability(self) -> bool:
        """Проверка доступности ffmpeg в системе"""
        try:
            result = subprocess.run(['ffmpeg', '-version'],
                                    capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False

    async def convert_audio_to_mp3(self, input_path: str) -> str:
        """Конвертация аудиофайла в MP3 формат"""
        try:
            # Проверяем доступность ffmpeg
            if not self.check_ffmpeg_availability():
                logger.warning("FFmpeg не найден. Используем исходный файл без конвертации.")
                return input_path

            input_path_obj = Path(input_path)

            # Если файл уже в MP3, возвращаем его
            if input_path_obj.suffix.lower() == '.mp3':
                logger.info(f"File {input_path_obj.name} already in MP3 format")
                return input_path

            # Создаем временный файл для результата
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                output_path = temp_file.name

            logger.info(f"Converting {input_path_obj.name} to MP3 format")

            # Конвертируем аудио в MP3 с помощью ffmpeg
            cmd = [
                'ffmpeg',
                '-i', input_path,  # Входной файл
                '-acodec', 'mp3',  # Кодек для аудио
                '-ab', '128k',  # Битрейт 128 kbps
                '-ar', '44100',  # Частота дискретизации 44.1 kHz
                '-y',  # Перезаписывать файл без запроса
                '-loglevel', 'error',  # Только ошибки в логах
                output_path
            ]

            # Запускаем процесс конвертации
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            logger.info('start convert function')

            if process.returncode == 0:
                # Проверяем, что выходной файл создался и не пустой
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    logger.info(f"Successfully converted to MP3: {output_path}")

                    logger.info('successful')
                    # Удаляем исходный файл если конвертация прошла успешно
                    try:
                        os.unlink(input_path)
                        logger.info(f"Removed original file: {input_path}")
                    except OSError as e:
                        logger.warning(f"Could not remove original file {input_path}: {e}")

                    return output_path
                else:
                    logger.error("Output MP3 file is empty or doesn't exist")
                    # Очищаем пустой файл
                    if os.path.exists(output_path):
                        os.unlink(output_path)
                    return input_path
            else:
                error_msg = stderr.decode('utf-8') if stderr else "Unknown error"
                logger.error(f"FFmpeg conversion failed: {error_msg}")

                # Очищаем файл результата при ошибке
                if os.path.exists(output_path):
                    os.unlink(output_path)
                return input_path

        except asyncio.TimeoutError:
            logger.error("FFmpeg conversion timeout")
            return input_path
        except Exception as e:
            logger.error(f"Error converting audio to MP3: {e}")
            return input_path

    def encode_image_to_base64(self, image_path: str) -> Optional[str]:
        """Кодирование изображения в base64 с оптимизацией размера"""
        try:
            # Открываем и оптимизируем изображение
            with Image.open(image_path) as img:
                # Конвертируем в RGB если нужно
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                # Уменьшаем размер если слишком большое
                if max(img.size) > self.max_image_size:
                    img.thumbnail((self.max_image_size, self.max_image_size), Image.Resampling.LANCZOS)

                # Сохраняем в память как JPEG с оптимизацией
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=85, optimize=True)
                buffer.seek(0)

                # Кодируем в base64
                return base64.b64encode(buffer.getvalue()).decode('utf-8')

        except Exception as e:
            logger.error(f"Error encoding image {image_path}: {e}")
            return None

    def get_image_mime_type(self, image_path: str) -> str:
        """Получение MIME типа изображения"""
        path = Path(image_path)
        extension = path.suffix.lower()

        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.bmp': 'image/bmp'
        }

        return mime_types.get(extension, 'image/jpeg')

    async def extract_text_from_pdf(self, file_path: str) -> str:
        """Извлечение текста из PDF файла"""
        try:
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    text += page.extract_text() + "\n"

            # Ограничиваем размер текста
            return text[:5000] if len(text) > 5000 else text

        except Exception as e:
            logger.error(f"Error extracting PDF text from {file_path}: {e}")
            return f"Ошибка при чтении PDF файла: {str(e)}"

    async def extract_text_from_docx(self, file_path: str) -> str:
        """Извлечение текста из Word документа"""
        try:
            doc = docx.Document(file_path)
            text = ""
            for paragraph in doc.paragraphs[:100]:  # Первые 100 параграфов
                text += paragraph.text + "\n"

            # Ограничиваем размер текста
            return text[:5000] if len(text) > 5000 else text

        except Exception as e:
            logger.error(f"Error extracting DOCX text from {file_path}: {e}")
            return f"Ошибка при чтении Word документа: {str(e)}"

    async def extract_text_from_excel(self, file_path: str) -> str:
        """Извлечение данных из Excel файла"""
        try:
            df = pd.read_excel(file_path, nrows=50)  # Первые 50 строк

            # Создаем описание таблицы
            description = f"Excel файл содержит {len(df)} строк и {len(df.columns)} столбцов.\n"
            description += f"Столбцы: {', '.join(df.columns.tolist())}\n\n"

            # Добавляем первые несколько строк
            description += "Первые строки данных:\n"
            description += df.head(10).to_string(max_cols=10, max_colwidth=50)

            return description

        except Exception as e:
            logger.error(f"Error reading Excel file {file_path}: {e}")
            return f"Ошибка при чтении Excel файла: {str(e)}"

    async def extract_text_from_csv(self, file_path: str) -> str:
        """Извлечение данных из CSV файла"""
        try:
            df = pd.read_csv(file_path, nrows=50)  # Первые 50 строк

            # Создаем описание таблицы
            description = f"CSV файл содержит {len(df)} строк и {len(df.columns)} столбцов.\n"
            description += f"Столбцы: {', '.join(df.columns.tolist())}\n\n"

            # Добавляем первые несколько строк
            description += "Первые строки данных:\n"
            description += df.head(10).to_string(max_cols=10, max_colwidth=50)

            return description

        except Exception as e:
            logger.error(f"Error reading CSV file {file_path}: {e}")
            return f"Ошибка при чтении CSV файла: {str(e)}"

    async def extract_text_from_audio(self, file_path: str) -> str:
        """Извлечение текста из аудио файлов через Whisper API с конвертацией в MP3"""
        try:
            file_name = Path(file_path).name
            original_size = os.path.getsize(file_path) / (1024 * 1024)  # размер в MB

            logger.info(f"Processing audio file: {file_name} ({original_size:.1f} MB)")

            # Конвертируем аудио в MP3 для лучшей совместимости
            mp3_file_path = await self.convert_audio_to_mp3(file_path)

            # Получаем финальный размер файла
            final_size = os.path.getsize(mp3_file_path) / (1024 * 1024)

            # Проверяем размер файла (Whisper API имеет лимит 25MB)
            if final_size > 25:
                return f"Аудиофайл слишком большой ({final_size:.1f} MB). Максимальный размер: 25 MB"

            logger.info(f"Using audio file for transcription: {Path(mp3_file_path).name} ({final_size:.1f} MB)")

            # Транскрибируем аудио через Whisper API
            with open(mp3_file_path, "rb") as audio_file:
                transcription = await self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                )

            # Получаем текст из объекта транскрипции
            transcription_text = transcription.text

            if not transcription_text or not transcription_text.strip():
                return f"Не удалось распознать речь в файле {file_name}"

            logger.info(f"Audio transcription completed for {file_name}")

            # Очищаем временный MP3 файл если он отличается от исходного
            if mp3_file_path != file_path and os.path.exists(mp3_file_path):
                try:
                    os.unlink(mp3_file_path)
                    logger.info(f"Cleaned up temporary MP3 file: {mp3_file_path}")
                except OSError as e:
                    logger.warning(f"Could not clean up temporary file {mp3_file_path}: {e}")

            return f"Транскрипция аудиофайла '{file_name}':\n\n{transcription_text}"

        except Exception as e:
            logger.error(f"Error processing audio file {file_path}: {e}")
            return f"Ошибка при обработке аудио файла: {str(e)}"

    async def extract_text_from_file(self, file_path: str, file_type: str) -> str:
        """Универсальная функция извлечения текста из файлов"""
        try:
            if file_type == "text/plain":
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(5000)  # Первые 5000 символов
                return content

            elif "pdf" in file_type:
                return await self.extract_text_from_pdf(file_path)

            elif "word" in file_type or "document" in file_type:
                return await self.extract_text_from_docx(file_path)

            elif "excel" in file_type or "spreadsheet" in file_type:
                return await self.extract_text_from_excel(file_path)

            elif "csv" in file_type:
                return await self.extract_text_from_csv(file_path)

            elif "audio" in file_type or file_type.startswith("audio/"):
                return await self.extract_text_from_audio(file_path)

            else:
                return f"Формат файла {file_type} поддерживается для загрузки, но извлечение текста не реализовано."

        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {e}")
            return f"Ошибка при обработке файла: {str(e)}"

    async def prepare_message_content(self, message: str, files_text: str) -> List[Dict]:
        """Подготовка контента сообщения с файлами для OpenAI API"""
        content = [{"type": "text", "text": message}]

        # Обрабатываем каждый файл
        for file_data in files_data:
            file_path = file_data.get('file_path')

            file_type = file_data.get('file_type')
            file_name = file_data.get('original_name', 'unknown')

            if not file_path or not os.path.exists(file_path):
                continue

            # Если это изображение и модель поддерживает vision
            if (file_type.startswith('image/') and
                    self.model in self.vision_models):

                base64_image = self.encode_image_to_base64(file_path)
                if base64_image:
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{file_type};base64,{base64_image}",
                            "detail": "auto"
                        }
                    })
                    logger.info(f"Added image {file_name} to message content")

            # Если это документ или аудио, извлекаем текст
            else:
                extracted_text = await self.extract_text_from_file(file_path, file_type)
                if extracted_text:
                    content.append({
                        "type": "text",
                        "text": f"\n\n--- Содержимое файла '{file_name}' ({file_type}) ---\n{extracted_text}\n--- Конец файла ---\n"
                    })
                    logger.info(f"Added content from {file_name} ({file_type})")

        return content

    async def get_response_stream(
            self,
            message: str,
            context: Dict[str, Any] = {},
            chat_history: List[Dict[str, Any]] = [],  # ← Изменили тип на Any
            files_context: str = '',
    ):
        """Получить потоковый ответ от GPT с учетом файлов и истории"""
        try:
            logger.info(f"Starting streaming request: message='{message[:50]}...', files_count={len(files_context)}")

            tool_type = context.get('tool_type', 'default')
            system_prompt = self.system_prompts.get(tool_type, self.system_prompts['default'])

            # Формируем сообщения для GPT
            messages = [
                {"role": "system", "content": system_prompt}
            ]

            # Добавляем историю чата
            if chat_history:
                logger.info(f"Adding {len(chat_history)} messages from chat history")

                recent_history = chat_history[-15:]

                for msg in recent_history:
                    role = msg.get("role")
                    content = msg.get("content", "")

                    if not content or not role:
                        continue

                    if msg.get("files") and role == "user":
                        file_texts = []
                        file_names = []

                        for file_data in msg["files"]:
                            file_name = file_data.get("original_name", "файл")
                            file_names.append(file_name)

                            # Извлекаем текст если есть
                            extracted = file_data.get("extracted_text")
                            if extracted and extracted.strip() and extracted != "None":
                                file_texts.append(
                                    f"\n--- Содержимое файла '{file_name}' ---\n{extracted}\n--- Конец файла ---\n")

                        # Формируем content с текстами файлов
                        if file_texts:
                            content = f"{content}\n\n{''.join(file_texts)}"
                        elif file_names:
                            file_info = ", ".join(file_names)
                            content = f"{content}\n[Прикреплены файлы: {file_info}]"

                    messages.append({
                        "role": role,
                        "content": content
                    })

                logger.info(f"Added {len(recent_history)} history messages to context")

            # Подготавливаем контент текущего сообщения с файлами
            if files_context:
                logger.info(f"Preparing message content with {len(files_context)} files")
                # message_content = await self.prepare_message_content(message, files_context)
                message_content = "Текст от пользователя:\n" + message + "\n Извлеченный текст из файла:\n" + files_context
            else:
                message_content = message

            # Добавляем текущее сообщение
            messages.append({
                "role": "user",
                "content": message_content
            })

            logger.info(f"Sending streaming request to {self.model} with {len(messages)} messages")

            # Вызываем GPT с потоковым режимом
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=2000,
                temperature=0.7,
                presence_penalty=0.1,
                frequency_penalty=0.1,
                stream=True
            )

            logger.info("Stream created successfully, starting to yield chunks...")
            chunk_count = 0

            # Генерируем чанки
            async for chunk in stream:
                chunk_count += 1
                if chunk.choices and len(chunk.choices) > 0 and chunk.choices[0].delta.content is not None:
                    content_piece = chunk.choices[0].delta.content
                    logger.debug(f"Chunk {chunk_count}: '{content_piece[:30]}...'")
                    yield content_piece

            logger.info(f"GPT streaming completed successfully. Total chunks: {chunk_count}")

        except Exception as e:
            logger.error(f"OpenAI API streaming error: {str(e)}", exc_info=True)
            # Fallback ответ
            files_context = ""
            if files_data:
                file_names = [f.get('original_name', 'unknown') for f in files_data]
                files_context = ", ".join(file_names)

            fallback_response = self._get_fallback_response(message, tool_type, files_context)
            logger.info(f"Yielding fallback response: {fallback_response[:100]}...")
            yield fallback_response

    # Сохраняем оригинальную функцию как fallback
    async def get_response(
            self,
            message: str,
            context: Dict[str, Any] = {},
            chat_history: List[Dict[str, str]] = [],
            files_data: List[Dict] = []
    ) -> str:
        """Получить полный ответ от GPT с учетом файлов (не потоковый режим)"""
        try:
            # Собираем полный ответ из потока
            full_response = ""
            async for chunk in self.get_response_stream(message, context, chat_history, files_data):
                full_response += chunk

            return full_response

        except Exception as e:
            logger.error(f"Error in get_response: {e}")
            # Fallback на статичный ответ при ошибке
            files_context = ""
            if files_data:
                file_names = [f.get('original_name', 'unknown') for f in files_data]
                files_context = ", ".join(file_names)

            return self._get_fallback_response(message, context.get('tool_type', 'default'), files_context)

    def _get_fallback_response(self, message: str, tool_type: str = "default", files_context: str = "") -> str:
        """Резервный ответ при недоступности GPT"""
        file_info = ""
        if files_context:
            file_info = f" Вижу прикрепленные файлы: {files_context}."

        fallback_responses = {
            "create_image": f"Извините, временно не могу помочь с созданием изображений.{file_info} "
                            f"Но ваша идея '{message[:50]}...' звучит интересно! 🎨 "
                            f"Попробуйте позже, когда ИИ снова будет доступен.",

            "coding": f"Временные технические проблемы с ИИ.{file_info} "
                      f"По вопросу '{message[:50]}...' рекомендую проверить документацию. 💻 "
                      f"Как только система восстановится, смогу помочь с анализом кода.",

            "brainstorm": f"ИИ временно недоступен,{file_info} но тема '{message[:50]}...' "
                          f"очень перспективная для обсуждения! 💡 Запишите свои идеи, "
                          f"а я помогу их развить, когда вернусь онлайн.",

            "excuse": f"Хм, с отмазками сейчас проблемы...{file_info} Может, попробуем честность? 😅 "
                      f"По поводу '{message[:30]}...' - иногда правда работает лучше любых оправданий!",

            "make_notes": f"Временные проблемы с ИИ.{file_info} "
                          f"Ваш запрос на создание заметок по '{message[:50]}...' получен. 📝 "
                          f"Пока что рекомендую записать основные моменты самостоятельно.",

            "default": f"Извините, временные проблемы с ИИ.{file_info} "
                       f"Ваш запрос '{message[:50]}...' получен, попробуйте позже! 🤖 "
                       f"Система восстановится в ближайшее время."
        }
        return fallback_responses.get(tool_type, fallback_responses["default"])

    async def analyze_image(self, image_path: str, prompt: str = "") -> str:
        """Анализ изображения через GPT-4 Vision"""
        try:
            if self.model not in self.vision_models:
                return f"📸 Модель {self.model} не поддерживает анализ изображений. Используйте gpt-4o или gpt-4o-mini."

            base64_image = self.encode_image_to_base64(image_path)
            if not base64_image:
                return "Не удалось обработать изображение."

            analysis_prompt = prompt or "Подробно опиши что ты видишь на этом изображении."
            mime_type = self.get_image_mime_type(image_path)

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": analysis_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}",
                                "detail": "auto"
                            }
                        }
                    ]
                }],
                max_tokens=1000
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Image analysis error: {e}")
            return f"Ошибка при анализе изображения: {str(e)}"

    async def analyze_document(self, file_path: str, file_type: str, prompt: str = "") -> str:
        """Анализ документов с извлечением текста"""
        try:
            file_name = Path(file_path).name
            extracted_text = await self.extract_text_from_file(file_path, file_type)

            if not extracted_text or extracted_text.startswith("Ошибка"):
                return extracted_text

            analysis_prompt = prompt or f"Проанализируй содержимое документа '{file_name}' и дай краткое содержание."

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": f"{analysis_prompt}\n\nСодержимое файла:\n{extracted_text}"
                }],
                max_tokens=1000
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Document analysis error: {e}")
            return f"Ошибка при анализе документа: {str(e)}"

    async def health_check(self) -> bool:
        """Проверка доступности OpenAI API"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=5
            )
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    async def get_file_suggestions(self, file_type: str, file_name: str) -> str:
        """Получение предложений по работе с файлом"""
        suggestions = {
            'image': [
                "Опишите, что вы видите на изображении",
                "Нужна ли обработка или редактирование изображения?",
                "Хотите создать похожее изображение в другом стиле?",
                "Нужен анализ композиции, цветов или стиля?"
            ],
            'audio': [
                "Преобразовать речь в текст",
                "Проанализировать тон и настроение голоса",
                "Извлечь ключевые фразы из записи",
                "Создать краткое содержание аудио"
            ],
            'pdf': [
                "Извлечь основные идеи из документа",
                "Создать краткое содержание",
                "Найти ключевые моменты и выводы",
                "Проанализировать структуру документа"
            ],
            'document': [
                "Проверить грамматику и стиль",
                "Улучшить структуру текста",
                "Сократить или расширить содержание",
                "Переформатировать документ"
            ],
            'spreadsheet': [
                "Проанализировать данные в таблице",
                "Найти закономерности и тенденции",
                "Создать выводы на основе данных",
                "Проверить расчеты и формулы"
            ]
        }

        file_category = 'document'
        if 'image' in file_type:
            file_category = 'image'
        elif 'pdf' in file_type:
            file_category = 'pdf'
        elif 'audio' in file_type:
            file_category = 'audio'
        elif 'spreadsheet' in file_type or 'excel' in file_type:
            file_category = 'spreadsheet'

        file_suggestions = suggestions.get(file_category, suggestions['document'])
        suggestion_text = "\n".join([f"• {s}" for s in file_suggestions])

        return f"🔎 Файл '{file_name}' успешно загружен и обработан! Вот что я могу с ним сделать:\n\n{suggestion_text}"


# Глобальный экземпляр AI сервиса
ai_service = None


def get_ai_service() -> AIService:
    """Получить экземпляр AI сервиса"""
    global ai_service
    if ai_service is None:
        try:
            ai_service = AIService()
        except ValueError as e:
            logger.error(f"Failed to initialize AI service: {e}")
            ai_service = None
    return ai_service