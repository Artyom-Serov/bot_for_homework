import os
import sys
import time
import requests
import telegram
import logging
from dotenv import load_dotenv

load_dotenv()

log_formatter = logging.Formatter(
    fmt='%(asctime)s [%(levelname)s] %(message)s'
)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(log_formatter)
logger = logging.getLogger(__name__)
logger.addHandler(stream_handler)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка доступности переменных окружения."""
    required_tokens = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']
    missing_tokens = []

    for token in required_tokens:
        if os.getenv(token) is None or os.getenv(token) == '':
            missing_tokens.append(token)

    if missing_tokens:
        missing_tokens_str = ', '.join(missing_tokens)
        logger.critical(f'Отсутствуют следующие переменные окружения: '
                        f'{missing_tokens_str}. Невозможно продолжить работу.')
        exit(1)


def send_message(bot, message):
    """Отправка сообщения в телеграм чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as error:
        logger.error(f'Ошибка при отправке сообщения в телеграм чат: {error}')


def get_api_answer(timestamp):
    """Запрос к API-сервису."""
    params = {
        'from_date': timestamp,
    }

    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        response.raise_for_status()
    except requests.exceptions.HTTPError as error:
        logger.error(f'Ошибка запроса API: {error}')
        raise SystemExit(error)

    return response.json()


def check_response(response):
    """Проверка ответа от API-сервиса."""
    if 'homeworks' not in response:
        error_message = 'Не найден ключ "homeworks" в ответе API'
        logger.error(error_message)
        raise ValueError(error_message)
    return response


def parse_status(homework):
    """Извлечение статуса домашней работы."""
    homework_name = homework.get('name', '<неизвестно>')
    verdict = homework.get('verdict', '<неизвестно>')
    if verdict in HOMEWORK_VERDICTS:
        return (f'Изменился статус проверки работы "{homework_name}". '
                f'{HOMEWORK_VERDICTS[verdict]}')
    else:
        return (f'Изменился статус проверки работы "{homework_name}". '
                f'Новый статус: {verdict}')


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            # Сделать запрос к API
            response = get_api_answer(timestamp)

            # Проверить ответ
            check_response(response)

            # Если есть обновления - получить статус работы и
            # отправить сообщение в Telegram
            if response['status'] == 'ok':
                for homework in response['homeworks']:
                    message = parse_status(homework)
                    send_message(bot, message)

            # Подождать некоторое время
            time.sleep(RETRY_PERIOD)
            timestamp = int(time.time())

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)


if __name__ == '__main__':
    main()
