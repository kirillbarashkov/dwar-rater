workspace "Dwar Rater" "Модель C4: контекст, контейнеры, развёртывание. Источник истины о структуре — этот файл; меняется тем же коммитом, что и топология (docker-compose, внешние интеграции)." {

    !identifiers hierarchical
    !impliedRelationships false

    model {

        user = person "Игрок" "Пользователь приложения: разбирает своих и чужих персонажей, ведёт треки и сценарии"

        dwar = softwareSystem "Dwar Rater" "Разбор персонажей и кланов dwar.ru, снапшоты, треки улучшений, сравнение, клановая аналитика" {

            web = container "Frontend" "SPA: карточки персонажей, сравнение, админка, треки" "React 19, TypeScript, Vite" {
                tags "Container"
                properties {
                    "compose.service" "frontend"
                }
            }

            api = container "Backend API" "REST API: 14 blueprint-модулей, RBAC, TOTP, парсинг, миграции Alembic при старте" "Python, Flask, Gunicorn" {
                tags "Container"
                properties {
                    "compose.service" "backend"
                }
            }

            db = container "PostgreSQL" "Персонажи, снапшоты, треки, сценарии, кланы, audit_log; там же ежечасный pg_dump с ротацией BACKUP_KEEP_DAYS в том postgres_backups" "PostgreSQL 16" {
                tags "Container"
                properties {
                    "compose.service" "postgres"
                }
            }

        }

        dwarfru = softwareSystem "dwar.ru" "Сайт игры: HTML-страницы персонажей и кланов" {
            tags "External"
        }

        github = softwareSystem "GitHub" "Код и GitHub Actions: сборка образов, деплой" {
            tags "External"
        }

        vm = softwareSystem "Cloud.ru VM" "Хост docker compose: backend, frontend, postgres" {
            tags "External"
        }

        user -> dwar "работает в браузере"
        user -> dwar.web "открывает карточку персонажа" "HTTPS"
        dwar.web -> dwar.api "запросы к API" "JSON/HTTPS"
        dwar.api -> dwar.db "читает и пишет" "SQL"
        dwar.api -> dwarfru "загружает страницу персонажа" "HTTPS"
        github -> vm "деплой" "SSH/GH Actions"

        dwar -> dwarfru "парсит HTML"
        dwar -> github "код, CI/CD"
        dwar -> vm "развёрнут на"

        deploymentEnvironment "Production" {
            deploymentNode "Cloud.ru VM" "Одна виртуальная машина, docker compose" "Ubuntu, Docker Engine" {
                containerInstance dwar.db
                containerInstance dwar.api
                containerInstance dwar.web
            }
        }
    }

    views {

        systemContext dwar "context" "Уровень 1: Dwar Rater и внешние системы" {
            include *
            autolayout lr
        }

        container dwar "containers" "Уровень 2: контейнеры" {
            include *
            autolayout tb
        }

        dynamic dwar "analyze" "Сценарий: разбор персонажа" {
            user -> dwar.web "Открывает карточку"
            dwar.web -> dwar.api "GET /api/analyze/<nick>"
            dwar.api -> dwarfru "Загружает HTML персонажа"
            dwar.api -> dwar.db "Сохраняет снапшот"
            dwar.api -> dwar.web "JSON: характеристики, экипировка, эффекты"
            autolayout tb
        }

        deployment * "Production" "prod" "Развёртывание: одна VM, docker compose" {
            include *
            autolayout tb
        }

        styles {
            element "Person" {
                shape Person
                background #08427b
                color #ffffff
            }
            element "Software System" {
                background #1168bd
                color #ffffff
            }
            element "Container" {
                background #438dd5
                color #ffffff
            }
            element "External" {
                background #999999
                color #ffffff
            }
        }
    }

    configuration {
        scope softwaresystem
    }
}
