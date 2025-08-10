import argparse
import asyncio
import datetime
import logging
import os
import platform
import shutil
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

# Настройка логирования
logging.basicConfig(
    filename=BASE_DIR / 'logs' / 'backup_logs.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


# Загрузка и проверка переменных окружения
def load_config():
    """
    Загружает и проверяет переменные окружения.

    Returns:
        dict: Словарь с конфигурацией.
    """
    required_vars = [
        'DB_HOST',
        'DB_PORT',
        'DB_USER',
        'DB_PASS',
        'BACKUP_DIR',
        'PG_BIN_DIR']
    config = {}
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            logging.error(f"Переменная окружения {var} не установлена.")
            sys.exit(1)
        config[var] = value

    databases = os.getenv('DATABASES')
    if not databases:
        logging.error("Переменная окружения DATABASES не установлена.")
        sys.exit(1)
    config['DATABASES'] = set(databases.split(','))
    return config


def get_pg_dump_path() -> Path:
    """
    Возвращает путь к утилите pg_dump с учетом операционной системы.

    Returns:
        Path: Путь к pg_dump.
    """
    pg_bin_dir = Path(config['PG_BIN_DIR'])
    pg_dump = pg_bin_dir / \
        ('pg_dump.exe' if platform.system() == 'Windows' else 'pg_dump')
    if not pg_dump.exists():
        logging.error(f"Утилита pg_dump не найдена по пути: {pg_dump}")
        sys.exit(1)
    return pg_dump


def send_notification(subject: str, body: str) -> None:
    """
    Отправляет уведомление по email о статусе резервного копирования.

    Args:
        subject (str): Тема письма.
        body (str): Текст письма.
    """
    try:
        email_config = {
            'SMTP_SERVER': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
            'SMTP_PORT': int(os.getenv('SMTP_PORT', 587)),
            'SMTP_USER': os.getenv('SMTP_USER'),
            'SMTP_PASS': os.getenv('SMTP_PASS'),
            'NOTIFY_EMAIL': os.getenv('NOTIFY_EMAIL')
        }
        if not email_config['NOTIFY_EMAIL']:
            logging.warning("Адрес для уведомлений не настроен.")
            return

        msg = EmailMessage()
        msg.set_content(body)
        msg['Subject'] = subject
        msg['From'] = email_config['SMTP_USER']
        msg['To'] = email_config['NOTIFY_EMAIL']

        with smtplib.SMTP(email_config['SMTP_SERVER'], email_config['SMTP_PORT']) as server:
            server.starttls()
            server.login(email_config['SMTP_USER'], email_config['SMTP_PASS'])
            server.send_message(msg)
        logging.info("Уведомление успешно отправлено.")
    except Exception as e:
        logging.error(f"Ошибка отправки уведомления: {str(e)}")


def cleanup_old_backups(max_age_days: int = 7):
    """
    Удаляет резервные копии, старше указанного количества дней.
    """
    try:
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=max_age_days)
        for dir_name in os.listdir(backup_dir):
            dir_path = os.path.join(backup_dir, dir_name)
            if os.path.isdir(dir_path):
                try:
                    dir_date = datetime.datetime.strptime(dir_name, "%Y-%m-%d")
                    if dir_date < cutoff_date:
                        shutil.rmtree(dir_path)
                        logging.info(
                            f"Удалена старая директория резервных копий: {dir_path}")
                except ValueError:
                    logging.warning(
                        f"Пропущена директория с неверным форматом даты: {dir_path}")
                    continue
    except Exception as e:
        logging.error(f"Ошибка при очистке старых резервных копий: {str(e)}")


async def create_backup(db_name: str, semaphore: asyncio.Semaphore) -> bool:
    """
    Создает сжатую резервную копию базы данных PostgreSQL с помощью pg_dump.

    Args:
        db_name (str): Имя базы данных для резервного копирования.
        semaphore (asyncio.Semaphore): Семафор для ограничения параллелизма.

    Returns:
        bool: True, если резервное копирование успешно, иначе False.
    """
    async with semaphore:
        try:
            backup_dir_today = Path(backup_dir) / \
                datetime.datetime.now().strftime("%Y-%m-%d")
            backup_dir_today.mkdir(parents=True, exist_ok=True)

            backup_file = f'{db_name}_backup_{
                datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.sql.gz'
            backup_file_path = backup_dir_today / backup_file

            pg_dump_path = get_pg_dump_path()
            pg_dump_command = (
                f'"{pg_dump_path}" --host={db_host} --port={db_port} '
                f'--username={db_user} --no-password {db_name} | gzip > "{backup_file_path}"'
            )

            process = await asyncio.create_subprocess_shell(
                pg_dump_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                logging.info(
                    f"Резервное копирование успешно для {db_name}: {backup_file_path}")
                return True
            else:
                logging.error(
                    f"Ошибка резервного копирования для {db_name}: {
                        stderr.decode()}")
                return False
        except Exception as e:
            logging.error(
                f"Ошибка при резервном копировании {db_name}: {
                    str(e)}")
            return False


async def main() -> None:
    """
    Выполняет резервное копирование всех указанных баз данных с ограничением параллелизма.
    """
    semaphore = asyncio.Semaphore(2)
    cleanup_old_backups(max_age_days=7)
    tasks = [create_backup(db_name, semaphore) for db_name in databases]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    failed = [db_name for db_name, result in zip(
        databases, results) if result is not True]
    if failed:
        send_notification(
            subject="Ошибка резервного копирования",
            body=f"Резервное копирование не удалось для баз: {
                ', '.join(failed)}")
    else:
        send_notification(
            subject="Успешное резервное копирование",
            body="Все резервные копии успешно созданы."
        )

    for db_name, result in zip(databases, results):
        if result is True:
            print(f"Резервное копирование завершено для {db_name}")
        else:
            print(f"Ошибка резервного копирования для {db_name}")


def parse_args():
    """
    Парсит аргументы командной строки.
    """
    parser = argparse.ArgumentParser(
        description="Скрипт резервного копирования баз данных PostgreSQL")
    parser.add_argument(
        '--databases',
        type=str,
        help="Список баз данных через запятую")
    parser.add_argument(
        '--backup-dir',
        type=str,
        help="Директория для хранения резервных копий")
    return parser.parse_args()


if __name__ == "__main__":
    config = load_config()
    db_host = config['DB_HOST']
    db_port = config['DB_PORT']
    db_user = config['DB_USER']
    db_password = config['DB_PASS']
    backup_dir = config['BACKUP_DIR']
    databases = config['DATABASES']

    args = parse_args()
    if args.databases:
        databases = set(args.databases.split(','))
    if args.backup_dir:
        config['BACKUP_DIR'] = args.backup_dir
        # Обновляем глобальную переменную
        globals()['backup_dir'] = args.backup_dir
    asyncio.run(main())
