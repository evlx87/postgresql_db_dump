import asyncio
import datetime
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
dot_env = os.path.join(BASE_DIR, '.env')
load_dotenv(dotenv_path=dot_env)

logs_dir = os.path.join(BASE_DIR, 'logs')
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)

log_file = os.path.join(BASE_DIR, 'backup_logs.log')

if not os.path.exists(log_file):
    print(f"Log file path does not exist: {log_file}")

logging.basicConfig(level=logging.INFO,
                    filename=log_file,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

backup_dir = "C:\\Users\\evlx.OKK\\Documents"
pg_bin_dir = "C:\\Program Files\\PostgreSQL\\16\\bin"

db_host = os.getenv('DB_HOST')
db_port = os.getenv('DB_PORT')
db_user = os.getenv('DB_USER')
db_password = os.getenv('DB_PASS')

databases = {'task_tracker', 'help_desk', 'contract_control'}

current_date = datetime.datetime.now().strftime("%Y-%m-%d")
backup_dir_today = os.path.join(backup_dir, current_date)

if not os.path.exists(backup_dir_today):
    os.makedirs(backup_dir_today)


async def create_backup(db_name):
    backup_file = f'{db_name}_backup_{datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.sql'
    backup_file_path = os.path.join(backup_dir_today, backup_file)

    pg_dump_command = (
        f'pg_dump -h {db_host} -p {db_port} -U {db_user} -d {db_name} -Fc -w --no-password '
        f'--dbname=postgres://{db_user}:{db_password}@{db_host}/{db_name} -f "{backup_file_path}"')

    process = await asyncio.create_subprocess_shell(pg_dump_command)
    await process.wait()

    return f'Дамп базы данных {db_name} прошел успешно'


async def main():
    logging.basicConfig(level=logging.INFO)
    logging.info('Начало создания резервных копий баз данных')

    tasks = [create_backup(db_name) for db_name in databases]
    results = await asyncio.gather(*tasks)

    for result in results:
        logging.info(result)

    logging.info(
        f'Резервные копии баз данных успешно созданы и сохранены в директории {backup_dir_today}')


if __name__ == "__main__":
    asyncio.run(main())
