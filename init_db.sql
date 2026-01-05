-- Инициализация базы данных для агентской системы
-- Выполняется автоматически при первом запуске PostgreSQL контейнера

-- Создаем расширения
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Устанавливаем локаль для полнотекстового поиска
-- (если не установлена при инициализации)

-- Создаем схему для агента
CREATE SCHEMA IF NOT EXISTS agent;

-- Устанавливаем права
GRANT ALL PRIVILEGES ON SCHEMA agent TO agent_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA agent TO agent_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA agent TO agent_user;

-- Создаем таблицы (будут созданы агентом при первом запуске)
-- Здесь только подготовительные операции

-- Создаем индексы для производительности (если таблицы уже существуют)
-- Эти команды выполнятся только если таблицы созданы

-- Функция для автоматического обновления timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Настройки для полнотекстового поиска
ALTER DATABASE agent_memory SET default_text_search_config = 'russian';

-- Создаем пользователя для чтения (если нужен)
-- CREATE USER agent_reader WITH PASSWORD 'reader_password';
-- GRANT CONNECT ON DATABASE agent_memory TO agent_reader;
-- GRANT USAGE ON SCHEMA public TO agent_reader;
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO agent_reader;

COMMIT;