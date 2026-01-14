# CargoChats

Единый коммуникационный хаб (ядро + адаптеры + очереди), с единой историей клиента. И с синхронизацией клиентов в разных чатах.

## Быстрый старт (DEV)

1) Создать env:
- `cp .env.example .env.dev`

2) Запуск:
- `docker compose -f docker-compose.dev.yml up -d --build`

3) Проверка:
- `GET http://localhost:8000/health`

## Миграции (Alembic)

Контейнер `api` содержит Alembic конфиг.
Пример:
- `docker compose -f docker-compose.dev.yml exec api bash`
- `alembic revision -m "init" --autogenerate`
- `alembic upgrade head`
