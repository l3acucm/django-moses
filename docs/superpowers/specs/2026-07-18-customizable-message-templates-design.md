# Настраиваемые шаблоны сообщений (SMS/email)

**Дата:** 2026-07-18
**Статус:** дизайн утверждён, готов к плану реализации

## Проблема

Все тексты SMS и email захардкожены в `moses/constants/strings.py` и инлайн в
`moses/views/user.py`. Проекты, использующие django-moses, не могут переопределить
эти тексты под свой бренд/язык, как они уже делают с обработчиком SMS через
`SEND_SMS_HANDLER`.

Конкретное бизнес-требование прод-проекта: **в SMS должен приходить только код,
без сопроводительного текста.**

## Решение (обзор)

Ввести настройку `MESSAGE_TEMPLATES` — словарь строковых шаблонов, которые проект
переопределяет **частично** через свой блок `MOSES = {...}`. Дефолты живут в
`constants/strings.py` как `gettext_lazy`. Рендер централизуется в одном хелпере,
который подставляет именованные плейсхолдеры и локализует под язык пользователя.

### Ключевые решения (из интервью)

1. **Механизм:** строковые шаблоны в настройках (не callable, не Django-шаблоны).
2. **i18n:** через `gettext_lazy`; moses **не** отгружает каталоги `.po/.mo` —
   только механизм. Проект, которому нужны переводы, ведёт свои каталоги или
   передаёт `gettext_lazy`-строки. Плоская строка (`"{pin}"`) не переводится —
   это ожидаемо и желаемо для SMS-с-одним-кодом.
3. **Плейсхолдеры:** именованные, через `str.format`. Всегда доступны `{pin}`,
   `{user}` (+ атрибуты: `{user.name}`, `{user.email}`), `{domain}`.
4. **Переопределение:** частичное, с merge поверх дефолтов.
5. **Объём:** покрыть все исходящие тексты (12 ключей), включая уведомления
   «Password/Email/Phone changed».
6. **Единственный источник дефолтов:** `constants/strings.py`.

## Полный набор ключей (12)

SMS и email-каналы разделены, чтобы можно было сделать SMS «только код», сохранив
полный текст в письмах.

| Ключ | Канал | Плейсхолдеры | Откуда сейчас |
|------|-------|--------------|----------------|
| `EMAIL_CONFIRMATION_PIN_TITLE` | email subject | `{pin}` | strings.py |
| `EMAIL_CONFIRMATION_PIN_BODY` | email body | `{pin}` | strings.py |
| `PHONE_NUMBER_CONFIRMATION_PIN_BODY` | **SMS** | `{pin}` | strings.py |
| `PASSWORD_RESET_PIN_TITLE` | email subject | `{pin}` | strings.py |
| `PASSWORD_RESET_EMAIL_BODY` | email body | `{pin}` | strings.py (split) |
| `PASSWORD_RESET_SMS_BODY` | **SMS** | `{pin}` | strings.py (split) |
| `PASSWORD_CHANGED_TITLE` | email subject | — | user.py:234 |
| `PASSWORD_CHANGED_BODY` | email body | `{domain}` | user.py:235 |
| `EMAIL_CHANGED_TITLE` | email subject | — | user.py:417 |
| `EMAIL_CHANGED_BODY` | email body | `{domain}` | user.py:418 |
| `PHONE_NUMBER_CHANGED_TITLE` | email subject | — | user.py:443 |
| `PHONE_NUMBER_CHANGED_BODY` | email body | `{domain}` | user.py:444 |

Единственные SMS-ключи: `PHONE_NUMBER_CONFIRMATION_PIN_BODY`,
`PASSWORD_RESET_SMS_BODY`.

**Важно — разделение `PASSWORD_RESET`:** сейчас `PASSWORD_RESET_PIN_BODY` один на
email и SMS. Разбиваем на `PASSWORD_RESET_EMAIL_BODY` и `PASSWORD_RESET_SMS_BODY`,
иначе требование «SMS только код» невозможно без порчи письма.

## Компоненты

### 1. `moses/constants/strings.py` — источник дефолтов

- Сменить `from django.utils.translation import gettext as _` →
  `gettext_lazy as _`.
  *Почему:* `gettext` в модуле резолвит строку один раз на языке импорта и
  «застывает»; `gettext_lazy` откладывает резолв до рендера под
  `translation.override`.
- Плейсхолдеры `%s` → `{pin}` (переход на `str.format`).
- Добавить недостающие 7 строк (split password-reset body + 6 строк уведомлений),
  перенеся тексты из `user.py`. Тексты уведомлений используют `{domain}` вместо
  вшитого f-string `support@{domain}`.

### 2. `moses/conf.py` — настройка + багфикс

- В `default_settings` добавить `"MESSAGE_TEMPLATES": { <ключ>: strings.X, ... }`
  (ссылки на strings.py, без дублирования текста).
- **Багфикс `_load_default_settings`:** копировать dict-дефолты —
  `setattr(self, name, dict(value) if isinstance(value, dict) else value)`.
  *Почему:* существующий merge в `_override_settings` делает
  `getattr(self, name).update(...)` in-place; без копии это мутирует модульный
  `default_settings` между инстансами `Settings`. `MESSAGE_TEMPLATES` — первый
  dict-дефолт, поэтому проблема всплывает именно сейчас.
- **Переопределение работает на существующем merge:** `_override_settings` уже
  обрабатывает dict-значения через `default.update(project_dict)` → частичный
  override из коробки. `import_string` к значениям шаблонов не применяется, т.к.
  `ObjDict` резолвит пути только при доступе через атрибут (`obj.KEY`), а шаблоны
  читаются как `MESSAGE_TEMPLATES[key]`.

### 3. `moses/services/messages.py` — рендер (новый модуль)

```python
from django.utils import translation
from moses.conf import settings as moses_settings


def render_message(key: str, user, *, pin=None, **extra) -> str:
    template = moses_settings.MESSAGE_TEMPLATES[key]
    context = {"user": user, "pin": pin, "domain": moses_settings.DOMAIN, **extra}
    with translation.override(user.preferred_language):
        return str(template).format(**context)
```

- `str.format` вызывается **после** резолва gettext → плейсхолдеры переживают
  перевод.
- `{pin}`, `{user}`, `{domain}` доступны всегда (pin=None для уведомлений) —
  меньше сюрпризов `KeyError` в шаблонах проекта.
- `domain` унифицируется на `moses_settings.DOMAIN`.

### 4. Точки вызова

- **`moses/services/credentials_confirmation.py`:** удалить обёртку
  `send_email_confirmation_message`; телефон → `render_message(...PIN_BODY)` →
  `SEND_SMS_HANDLER`; email → `render_message` для title и body →
  `send_mail(...)`.
- **`moses/services/reset_password.py`:** email-ветка →
  `render_message(PASSWORD_RESET_PIN_TITLE / PASSWORD_RESET_EMAIL_BODY,
  pin=user.password_reset_code)`; SMS-ветка →
  `render_message(PASSWORD_RESET_SMS_BODY, pin=...)`.
- **`moses/views/user.py`:** три уведомления (password/email/phone changed) →
  `render_message(...TITLE / ...BODY, domain=...)`; тексты убрать из кода.

## Пример override в прод-проекте

```python
MOSES = {
    # ... прочие настройки без изменений ...
    "MESSAGE_TEMPLATES": {
        "PHONE_NUMBER_CONFIRMATION_PIN_BODY": "{pin}",
        "PASSWORD_RESET_SMS_BODY": "{pin}",
    },
}
```

Остальные 10 ключей берут дефолты. i18n для переопределённых строк — по желанию
проекта через `gettext_lazy` + свои каталоги.

## Обработка ошибок / ограничения

- **`str.format`:** литеральные `{`/`}` в тексте экранируются `{{`/`}}`;
  неизвестный плейсхолдер (`{code}`) даёт `KeyError` — намеренно вскрывает ошибку
  конфига проекта.
- **Нет каталогов в moses:** дефолты рендерятся как английский msgid, пока проект
  не заведёт `.po/.mo`. Совпадает с текущим поведением.

## Побочная польза (исправляется попутно)

Сейчас `reset_password.py` и уведомления «Password changed» **не** оборачиваются в
`translation.override(user.preferred_language)` → отправляются на языке активного
потока, а не пользователя. После централизации в `render_message` — локализуются
по языку пользователя корректно.

## Тестирование

Инфраструктура есть: `test_project/app_for_tests/` + pytest-django
(`DJANGO_SETTINGS_MODULE = test_project.settings`). SMS мокается через
`mocks.send_sms_handler` → `utils.remember_pin` (извлекает первое число из тела).

Новый `test_project/app_for_tests/test_message_templates.py`:

1. **Дефолтный рендер** — `render_message` для каждого канала даёт ожидаемый текст.
2. **Частичный override** — `override_settings(MOSES={... "MESSAGE_TEMPLATES":
   {"PHONE_NUMBER_CONFIRMATION_PIN_BODY": "{pin}"}})`: переопределённый ключ =
   кастом, остальные = дефолты (проверить merge и что `default_settings` не
   замутирован между тестами — багфикс копирования).
3. **Плейсхолдер `{user.name}`** — подстановка атрибута пользователя.
4. **Локализация** — `preferred_language` влияет на резолв `gettext_lazy` (с
   временным тестовым каталогом или monkeypatch перевода).
5. **SMS = только код** — сквозной сценарий: с override `"{pin}"` тело SMS равно
   строке кода (существующие тесты подтверждения телефона не ломаются, т.к.
   `remember_pin` берёт первое число).

## Вне объёма

- Отгрузка каталогов переводов из moses (ru/kg) — решено «нет, только механизм».
- HTML-письма / шаблоны-файлы Django.
- Настройка from-адресов (`noreply@...`, `SENDER_EMAIL`).
