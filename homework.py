import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(
    logging.Formatter(fmt='%(asctime)s [%(levelname)s] %(message)s'))
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
    required_tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    missing_tokens = []

    for token_name, token_value in required_tokens.items():
        if not token_value:
            missing_tokens.append(token_name)

    if missing_tokens:
        error_message = (f"Отсутствуют переменные окружения: "
                         f"{', '.join(missing_tokens)}")
        logger.critical(error_message)
        exit(1)


def send_message(bot, message):
    """Отправка сообщения в телеграм чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug('Сообщение успешно отправлено в телеграм чат.')
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
    except requests.exceptions.RequestException as error:
        logger.error(f'Ошибка запроса API: {error}')
        return response.json()
    except requests.exceptions.HTTPError as error:
        logger.error(f'Ошибка запроса API: {error.response.status_code}')
        return response.json()

    if response.status_code != 200:
        raise AssertionError('Произошла ошибка при запросе API')

    return response.json()


def check_response(response):
    """Проверка ответа от API-сервиса."""
    if not isinstance(response, dict):
        error_message = 'Ответ от API должен быть представлен в виде словаря'
        logger.error(error_message)
        raise TypeError(error_message)
    if 'homeworks' not in response:
        error_message = 'Отсутствует ключ "homeworks" в ответе от API'
        logger.error(error_message)
        raise KeyError(error_message)

    if not isinstance(response['homeworks'], list):
        error_message = 'Данные для ключа "homeworks" '
        'должны быть представлены в виде списка'
        logger.error(error_message)
        raise TypeError(error_message)


def parse_status(homework):
    """Извлечение статуса домашней работы."""
    required_keys = ['homework_name', 'status']

    for key in required_keys:
        if key not in homework:
            error_message = f'Отсутствует ключ "{key}" в ответе API'
            logger.debug(error_message)
            raise ValueError(error_message)

    homework_name = homework['homework_name']
    homework_status = homework['status']

    if homework_status not in HOMEWORK_VERDICTS:
        error_message = (f'Неизвестный статус работы '
                         f'"{homework_name}": {homework_status}')
        logger.debug(error_message)
        raise ValueError(error_message)

    verdict = HOMEWORK_VERDICTS[homework_status]

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)

            homeworks = response['homeworks']
            if homeworks:
                for homework in homeworks:
                    message = parse_status(homework)
                    send_message(bot, message)

            timestamp = response['current_date']
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)
    main()
