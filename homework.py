import logging
import os
import sys
import time

import requests
import telegram

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
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
    required_tokens = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']
    missing_tokens = []

    for token in required_tokens:
        if not os.getenv(token):
            missing_tokens.append(token)

#    if missing_tokens:
#        missing_tokens_str = ', '.join(missing_tokens)
#        logger.critical(f'Отсутствуют следующие переменные окружения: '
#                        f'{missing_tokens_str}. Невозможно продолжить работу.')
#        raise SystemExit(1)
    if not all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)):
        logger.critical('Ошибка в переменных окружения')
        sys.exit(1)


def send_message(bot, message):
    """Отправка сообщения в телеграм чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug('Сообщение успешно отправлено в телеграм чат.')
        return True
    except Exception as error:
        logger.error(f'Ошибка при отправке сообщения в телеграм чат: {error}')
        return False


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
            raise ValueError(f'Отсутствует ключ "{key}" в ответе API')

    homework_name = homework['homework_name']
    homework_status = homework['status']

    verdict = HOMEWORK_VERDICTS.get(homework_status)
    if not verdict:
        raise ValueError(f'Неизвестный статус работы '
                         f'"{homework_name}": {homework_status}')

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
            homeworks = response.get('homeworks', [])
            if homeworks:
                for homework in homeworks:
                    if 'status' in homework:
                        message = parse_status(homework)
                        while not send_message(bot, message):
                            logger.warning(
                                'Попытка отправки сообщения не удалась, '
                                'повторная попытка через 10 минут.')
                            time.sleep(RETRY_PERIOD)
                        raise SystemExit('break')

                logger.debug('Новых заданий нет')
            time.sleep(RETRY_PERIOD)

        except KeyboardInterrupt:
            raise SystemExit("Программа остановлена пользователем.")

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            time.sleep(RETRY_PERIOD)
            return


if __name__ == '__main__':
#    logger = logging.getLogger(__name__)
#    logger.setLevel(logging.DEBUG)
#    stream_handler = logging.StreamHandler(sys.stdout)
#    stream_handler.setFormatter(
#        logging.Formatter(fmt='%(asctime)s [%(levelname)s] %(message)s'))
#    logger.addHandler(stream_handler)

    main()
