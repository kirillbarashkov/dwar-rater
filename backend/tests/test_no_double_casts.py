"""A46: двойное приведение типа не должно возвращаться в код.

`x as unknown as T` отключает проверку типов полностью: компилятор не замечает,
что форма объекта не совпадает с ожидаемой, и ошибка вылезает в рантайме как
`undefined` в таблице. До правки таких мест было **7** в пяти файлах.

Худшее было в `App.tsx`: `setCurrentResult(data as unknown as AnalysisResult)` —
`snapshot_data` из базы попадал во вкладки анализа без единой проверки. Слепок
закрытого профиля (совсем другой набор полей) или слепок старой схемы
оказывался «результатом анализа», и пользователь видел пустые таблицы вместо
сообщения об ошибке.

Заменено:
* исходящие payload'ы (`snapshot_data`, сравнение сценария, экспорт, источники
  в `ImprovementTrack`) — на `toPayload()`: поверхностная копия, приведение на
  пустом литерале, данные не переинтерпретируются;
* загрузка слепка — на `asAnalysisResult()`: сначала проверка формы, потом
  приведение в одном месте.

Тесты статические: комментарии из проверки исключаются (в них приём упомянут по
делу — как описание того, что было).
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, 'frontend', 'src')


def _sources():
    for dirpath, _dirnames, filenames in os.walk(SRC):
        for name in filenames:
            if name.endswith(('.ts', '.tsx')):
                yield os.path.join(dirpath, name)


def _code_only(text):
    without_block = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return '\n'.join(
        line for line in without_block.split('\n') if not line.strip().startswith('//')
    )


def test_no_double_casts_in_code():
    offenders = []
    for path in _sources():
        code = _code_only(open(path, encoding='utf-8').read())
        for number, line in enumerate(code.split('\n'), 1):
            if 'as unknown as' in line:
                offenders.append(f'{os.path.relpath(path, SRC)}:{number}')
    assert not offenders, 'двойное приведение снова в коде:\n' + '\n'.join(offenders)


def test_payload_helper_does_not_reinterpret_data():
    source = _code_only(open(os.path.join(SRC, 'utils', 'payload.ts'), encoding='utf-8').read())
    assert 'Object.assign' in source, 'toPayload должен копировать, а не приводить тип значения'
    assert source.count('as Record<string, unknown>') <= 1, 'приведений больше одного'


def test_snapshot_load_validates_shape():
    source = _code_only(open(os.path.join(SRC, 'App.tsx'), encoding='utf-8').read())
    assert 'asAnalysisResult(' in source, 'загрузка слепка не проверяет форму'
    assert 'setCurrentResult(parsed)' in source, 'результат проверки не используется'


def test_guard_distinguishes_closed_profile_snapshots():
    """Слепок закрытого профиля — тоже валидный слепок, его нельзя отвергать."""
    source = _code_only(open(os.path.join(SRC, 'utils', 'analysisShape.ts'),
                             encoding='utf-8').read())
    assert 'closed_info' in source, 'гард не учитывает слепки закрытых профилей'
    assert 'main_stats' in source, 'гард не проверяет характеристики открытого профиля'


def test_guard_returns_typed_value_not_boolean_only():
    source = _code_only(open(os.path.join(SRC, 'utils', 'analysisShape.ts'),
                             encoding='utf-8').read())
    assert 'export function asAnalysisResult' in source, 'нет функции-парсера'
    assert 'AnalysisResult | null' in source, 'парсер не возвращает типизированное значение'
