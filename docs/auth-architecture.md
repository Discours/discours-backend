# Архитектура системы авторизации

## Схема потоков данных

```mermaid
graph TB
    subgraph "Frontend"
        FE[Web Frontend]
        MOB[Mobile App]
    end

    subgraph "Auth Layer"
        MW[AuthMiddleware]
        DEC[GraphQL Decorators]
        HANDLER[Auth Handlers]
    end

    subgraph "Core Auth"
        IDENTITY[Identity]
        JWT[JWT Codec]
        OAUTH[OAuth Manager]
        PERM[Permissions]
    end

    subgraph "Token System"
        TS[TokenStorage]
        STM[SessionTokenManager]
        VTM[VerificationTokenManager]
        OTM[OAuthTokenManager]
        BTM[BatchTokenOperations]
        MON[TokenMonitoring]
    end

    subgraph "Storage"
        REDIS[(Redis)]
        DB[(PostgreSQL)]
    end

    subgraph "External"
        GOOGLE[Google OAuth]
        GITHUB[GitHub OAuth]
        FACEBOOK[Facebook]
        OTHER[Other Providers]
    end

    FE --> MW
    MOB --> MW
    MW --> IDENTITY
    MW --> JWT

    DEC --> PERM
    HANDLER --> OAUTH

    IDENTITY --> STM
    OAUTH --> OTM

    TS --> STM
    TS --> VTM
    TS --> OTM

    STM --> REDIS
    VTM --> REDIS
    OTM --> REDIS
    BTM --> REDIS
    MON --> REDIS

    IDENTITY --> DB
    OAUTH --> DB
    PERM --> DB

    OAUTH --> GOOGLE
    OAUTH --> GITHUB
    OAUTH --> FACEBOOK
    OAUTH --> OTHER
```

## Диаграмма компонентов

```mermaid
graph LR
    subgraph "HTTP Layer"
        REQ[HTTP Request]
        RESP[HTTP Response]
    end

    subgraph "Middleware"
        AUTH_MW[Auth Middleware]
        CORS_MW[CORS Middleware]
    end

    subgraph "GraphQL"
        RESOLVER[GraphQL Resolvers]
        DECORATOR[Auth Decorators]
    end

    subgraph "Auth Core"
        VALIDATION[Validation]
        IDENTIFICATION[Identity Check]
        AUTHORIZATION[Permission Check]
    end

    subgraph "Token Management"
        CREATE[Token Creation]
        VERIFY[Token Verification]
        REVOKE[Token Revocation]
        REFRESH[Token Refresh]
    end

    REQ --> CORS_MW
    CORS_MW --> AUTH_MW
    AUTH_MW --> RESOLVER
    RESOLVER --> DECORATOR

    DECORATOR --> VALIDATION
    VALIDATION --> IDENTIFICATION
    IDENTIFICATION --> AUTHORIZATION

    AUTHORIZATION --> CREATE
    AUTHORIZATION --> VERIFY
    AUTHORIZATION --> REVOKE
    AUTHORIZATION --> REFRESH

    CREATE --> RESP
    VERIFY --> RESP
    REVOKE --> RESP
    REFRESH --> RESP
```

## Схема OAuth потока

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend
    participant A as Auth Service
    participant R as Redis
    participant P as OAuth Provider
    participant D as Database

    U->>F: Click "Login with Provider"
    F->>A: GET /oauth/{provider}?state={csrf}
    A->>R: Store OAuth state
    A->>P: Redirect to Provider
    P->>U: Show authorization page
    U->>P: Grant permission
    P->>A: GET /oauth/{provider}/callback?code={code}&state={state}
    A->>R: Verify state
    A->>P: Exchange code for token
    P->>A: Return access token + user data
    A->>D: Find/create user
    A->>A: Generate JWT session token
    A->>R: Store session in Redis
    A->>F: Redirect with JWT token
    F->>U: User logged in
```

## Схема сессионного управления

```mermaid
stateDiagram-v2
    [*] --> Anonymous
    Anonymous --> Authenticating: Login attempt
    Authenticating --> Authenticated: Valid credentials
    Authenticating --> Anonymous: Invalid credentials
    Authenticated --> Refreshing: Token near expiry
    Refreshing --> Authenticated: Successful refresh
    Refreshing --> Anonymous: Refresh failed
    Authenticated --> Anonymous: Logout/Revoke
    Authenticated --> Anonymous: Token expired
```

## Redis структура данных

```
├── Sessions
│   ├── session:{user_id}:{token}     → Hash {user_id, username, device_info, last_activity}
│   ├── user_sessions:{user_id}       → Set {token1, token2, ...}
│   └── {user_id}-{username}-{token}  → Hash (legacy format)
│
├── Verification
│   └── verification_token:{token}    → JSON {user_id, type, data, created_at}
│
├── OAuth
│   ├── oauth_access:{user_id}:{provider}   → JSON {token, expires_in, scope}
│   ├── oauth_refresh:{user_id}:{provider}  → JSON {token, provider_data}
│   └── oauth_state:{state}                 → JSON {provider, redirect_uri, code_verifier}
│
└── Monitoring
    └── token_stats                   → Hash {session_count, oauth_count, memory_usage}
```

## Компоненты безопасности

```mermaid
graph TD
    subgraph "Input Validation"
        EMAIL[Email Format]
        PASS[Password Strength]
        TOKEN[Token Format]
    end

    subgraph "Authentication"
        BCRYPT[bcrypt + SHA256]
        JWT_SIGN[JWT Signing]
        OAUTH_VERIFY[OAuth Verification]
    end

    subgraph "Authorization"
        ROLE[Role-based Access]
        PERM[Permission Checks]
        RESOURCE[Resource Access]
    end

    subgraph "Session Security"
        TTL[Token TTL]
        REVOKE[Token Revocation]
        REFRESH[Secure Refresh]
    end

    EMAIL --> BCRYPT
    PASS --> BCRYPT
    TOKEN --> JWT_SIGN

    BCRYPT --> ROLE
    JWT_SIGN --> ROLE
    OAUTH_VERIFY --> ROLE

    ROLE --> PERM
    PERM --> RESOURCE

    RESOURCE --> TTL
    RESOURCE --> REVOKE
    RESOURCE --> REFRESH
```

## Масштабирование и производительность

### Горизонтальное масштабирование
- **Stateless JWT** токены
- **Redis Cluster** для высокой доступности
- **Load Balancer** aware session management

### Оптимизации
- **Connection pooling** для Redis
- **Batch operations** для массовых операций
- **Pipeline использование** для атомарности
- **LRU кэширование** для часто используемых данных

### Мониторинг производительности
- **Response time** auth операций
- **Redis memory usage** и hit rate
- **Token creation/validation** rate
- **OAuth provider** response times
