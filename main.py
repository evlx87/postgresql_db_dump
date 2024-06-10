import os
import subprocess
import datetime

# Добавляем путь к pg_dump к переменной среды PATH
os.environ["PATH"] += os.pathsep + "C:\\Program Files\\PostgreSQL\\16\\bin"

# Список баз данных для резервного копирования
databases = ['task_tracker', 'help_desk', 'contract_control']

# Параметры подключения к базе данных PostgreSQL
db_host = 'localhost'
db_port = '5432'
db_user = 'postgres'
db_password = 'Grave1987'

# Директория для сохранения бэкапов
backup_dir = 'C:\\Users\\evlx.OKK\\Documents'

current_date = datetime.datetime.now().strftime("%Y-%m-%d")
backup_dir_today = os.path.join(backup_dir, current_date)

# Создаем директорию с текущей датой, если она еще не существует
if not os.path.exists(backup_dir_today):
    os.makedirs(backup_dir_today)

# Цикл для создания резервного копирования для каждой базы данных
for db_name in databases:
    backup_file = f'{db_name}_backup_{datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.sql'

    # Полный путь к файлу резервной копии
    backup_file_path = os.path.join(backup_dir_today, backup_file)

    # Команда pg_dump для создания резервной копии базы данных
    pg_dump_command = f'pg_dump -h {db_host} -p {db_port} -U {db_user} -d {db_name} -Fc -w --no-password --dbname=postgres://{db_user}:{db_password}@{db_host}/{db_name} -f "{backup_file_path}"'

    # Запускаем процесс создания резервной копии базы данных
    process = subprocess.Popen(pg_dump_command, shell=True)
    process.wait()

    print(f'Дамп базы данных {db_name} прошел успешно')

print(f'Резервные копии баз данных успешно созданы и сохранены в директории {backup_dir_today}.')
