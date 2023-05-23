import utils
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
        raise utils.BreakInfiniteLoop(
            "Отсутствуют обязательные переменные окружения.")


def send_message(bot, message):
    """Отправка сообщения в телеграм чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as error:
        logger.error(f'Ошибка при отправке сообщения в телеграм чат: {error}')
        return False
    else:
        logger.debug('Сообщение успешно отправлено в телеграм чат.')
        return True


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
        return {}
    except requests.exceptions.HTTPError as error:
        logger.error(f'Ошибка запроса API: {error.response.status_code}')
        return {}

    if response.status_code != 200:
        raise AssertionError('Произошла ошибка при запросе API')

    return response.json()


def check_response(response):
    """Проверка ответа от API-сервиса."""
    if isinstance(response, list):
        error_message = 'Ответ от API должен быть представлен в виде словаря'
        logger.error(error_message)
        raise TypeError(error_message)
    if not isinstance(response.get('homeworks'), list):
        error_message = ('Данные для ключа "homeworks" должны '
                         'быть представлены в виде списка')
        logger.error(error_message)
        raise TypeError(error_message)
    return response


def parse_status(homework):
    """Извлечение статуса домашней работы."""
    homework_name = homework.get('homework_name')
    if homework_name is None:
        raise ValueError('Отсутствует ключ "homework_name" в ответе API')

    status = homework.get('status')
    if status is None:
        raise ValueError('Отсутствует ключ "status" в ответе API')

    verdict = HOMEWORK_VERDICTS.get(status)
    if verdict is None:
        raise ValueError(
            f'Неизвестный статус работы "{homework_name}": {status}')

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
            if 'homeworks' in response and len(response['homeworks']) > 0:
                for homework in response['homeworks']:
                    if 'status' in homework:
                        message = parse_status(homework)
                        while not send_message(bot, message):
                            logger.warning(
                                'Попытка отправки сообщения не удалась, '
                                'повторная попытка через 10 минут.')
                            time.sleep(RETRY_PERIOD)
            else:
                logger.debug('Новых заданий нет')
            time.sleep(1)
            continue
        except KeyboardInterrupt:
            raise SystemExit("Программа остановлена пользователем.")
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            time.sleep(RETRY_PERIOD)
            raise SystemExit(str(error))


if __name__ == '__main__':
    main()
