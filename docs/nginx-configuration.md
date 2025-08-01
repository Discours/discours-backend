# Nginx Configuration для Dokku

## Обзор

Улучшенная конфигурация nginx для Dokku с поддержкой:
- Глобального gzip сжатия
- Продвинутых настроек прокси
- Безопасности и производительности
- Поддержки Dokku переменных

## Основные улучшения

### 1. Gzip сжатие
```nginx
gzip on;
gzip_vary on;
gzip_min_length 1024;
gzip_proxied any;
gzip_comp_level 6;
gzip_types
    text/plain
    text/css
    text/xml
    text/javascript
    application/javascript
    application/xml+rss
    application/json
    application/xml
    image/svg+xml
    font/ttf
    font/otf
    font/woff
    font/woff2;
```

### 2. Продвинутые настройки прокси
- **Proxy buffering**: Оптимизированные буферы для производительности
- **X-Forwarded headers**: Правильная передача заголовков прокси
- **Keepalive connections**: Поддержка постоянных соединений
- **Rate limiting**: Ограничение запросов для защиты от DDoS

### 3. Безопасность
- **Security headers**: HSTS, CSP, X-Frame-Options и др.
- **SSL/TLS**: Современные протоколы и шифры
- **Rate limiting**: Защита от атак
- **Content Security Policy**: Защита от XSS

### 4. Кэширование
- **Static assets**: Агрессивное кэширование (1 год)
- **Dynamic content**: Умеренное кэширование (10 минут)
- **GraphQL**: Отключение кэширования
- **API endpoints**: Умеренное кэширование (5 минут)

## Использование Dokku переменных

### Доступные переменные
- `{{ $.APP }}` - имя приложения
- `{{ $.SSL_SERVER_NAME }}` - домен для SSL
- `{{ $.NOSSL_SERVER_NAME }}` - домен для HTTP
- `{{ $.APP_SSL_PATH }}` - путь к SSL сертификатам
- `{{ $.DOKKU_ROOT }}` - корневая директория Dokku

### Настройка через nginx:set

```bash
# Установка формата логов
dokku nginx:set core access-log-format detailed

# Установка размера тела запроса
dokku nginx:set core client-max-body-size 100M

# Установка таймаутов
dokku nginx:set core proxy-read-timeout 60s
dokku nginx:set core proxy-connect-timeout 60s

# Отключение логов
dokku nginx:set core access-log-path off
dokku nginx:set core error-log-path off
```

### Поддерживаемые свойства
- `access-log-format` - формат access логов
- `access-log-path` - путь к access логам
- `client-max-body-size` - максимальный размер тела запроса
- `proxy-read-timeout` - таймаут чтения от прокси
- `proxy-connect-timeout` - таймаут подключения к прокси
- `proxy-send-timeout` - таймаут отправки к прокси
- `bind-address-ipv4` - привязка к IPv4 адресу
- `bind-address-ipv6` - привязка к IPv6 адресу

## Локации (Locations)

### 1. Основное приложение (`/`)
- Проксирование всех запросов
- Кэширование динамического контента
- Поддержка WebSocket
- Rate limiting

### 2. GraphQL (`/graphql`)
- Отключение кэширования
- Увеличенные таймауты (300s)
- Специальные заголовки кэширования

### 3. Статические файлы
- Агрессивное кэширование (1 год)
- Gzip сжатие
- Заголовки `immutable`

### 4. API endpoints (`/api/`)
- Умеренное кэширование (5 минут)
- Rate limiting
- Заголовки статуса кэша

### 5. Health check (`/health`)
- Отключение логов
- Отключение кэширования
- Быстрые ответы

## Мониторинг и логирование

### Логи
- **Access logs**: `/var/log/nginx/core-access.log`
- **Error logs**: `/var/log/nginx/core-error.log`
- **Custom formats**: JSON и detailed

### Команды для просмотра логов
```bash
# Access логи
dokku nginx:access-logs core

# Error логи
dokku nginx:error-logs core

# Следование за логами
dokku nginx:access-logs core -t
dokku nginx:error-logs core -t
```

### Дополнительные конфигурации

Для добавления custom log formats и других настроек, создайте файл на сервере Dokku:

```bash
# Подключитесь к серверу Dokku
ssh dokku@your-server

# Создайте файл с log formats
sudo mkdir -p /etc/nginx/conf.d
sudo nano /etc/nginx/conf.d/00-log-formats.conf
```

Содержимое файла `/etc/nginx/conf.d/00-log-formats.conf`:
```nginx
# Custom log format for JSON logging (as per Dokku docs)
log_format json_combined escape=json
  '{'
    '"time_local":"$time_local",'
    '"remote_addr":"$remote_addr",'
    '"remote_user":"$remote_user",'
    '"request":"$request",'
    '"status":"$status",'
    '"body_bytes_sent":"$body_bytes_sent",'
    '"request_time":"$request_time",'
    '"http_referrer":"$http_referer",'
    '"http_user_agent":"$http_user_agent",'
    '"http_x_forwarded_for":"$http_x_forwarded_for",'
    '"http_x_forwarded_proto":"$http_x_forwarded_proto"'
  '}';

# Custom log format for detailed access logs
log_format detailed
  '$remote_addr - $remote_user [$time_local] '
  '"$request" $status $body_bytes_sent '
  '"$http_referer" "$http_user_agent" '
  'rt=$request_time uct="$upstream_connect_time" '
  'uht="$upstream_header_time" urt="$upstream_response_time"';
```

### Валидация конфигурации
```bash
# Проверка конфигурации
dokku nginx:validate-config core

# Пересборка конфигурации
dokku proxy:build-config core
```

## Производительность

### Оптимизации
1. **Gzip сжатие**: Уменьшение размера передаваемых данных
2. **Proxy buffering**: Оптимизация буферов
3. **Keepalive**: Переиспользование соединений
4. **Кэширование**: Уменьшение нагрузки на бэкенд
5. **Rate limiting**: Защита от перегрузки

### Мониторинг
- Заголовок `X-Cache-Status` для отслеживания кэша
- Детальные логи с временем ответа
- Метрики upstream соединений

## Безопасность

### Заголовки безопасности
- `Strict-Transport-Security`: Принудительный HTTPS
- `Content-Security-Policy`: Защита от XSS
- `X-Frame-Options`: Защита от clickjacking
- `X-Content-Type-Options`: Защита от MIME sniffing
- `Referrer-Policy`: Контроль referrer

### Rate Limiting
- Общие запросы: 20 r/s с burst 20
- API endpoints: 10 r/s
- GraphQL: 5 r/s
- Соединения: 100 одновременных

## Troubleshooting

### Частые проблемы

1. **SSL ошибки**
   ```bash
   dokku certs:report core
   dokku certs:add core <cert-file> <key-file>
   ```

2. **Проблемы с кэшем**
   ```bash
   # Очистка кэша nginx
   sudo rm -rf /var/cache/nginx/*
   sudo systemctl reload nginx
   ```

3. **Проблемы с логами**
   ```bash
   # Проверка прав доступа
   sudo chown -R nginx:nginx /var/log/nginx/
   ```

4. **Валидация конфигурации**
   ```bash
   dokku nginx:validate-config core --clean
   dokku proxy:build-config core
   ```

## Обновление конфигурации

После изменения `nginx.conf.sigil`:
```bash
git add nginx.conf.sigil
git commit -m "Update nginx configuration"
git push dokku dev:dev
```

Конфигурация автоматически пересоберется при деплое.
