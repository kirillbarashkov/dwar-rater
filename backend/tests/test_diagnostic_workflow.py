"""A24: пароль из workflow_dispatch не должен попадать в лог диагностики.

Значения `workflow_dispatch` input GitHub **не маскирует** — маскируются только
secrets. Пароль администратора уходил в `diagnostic.yml` подстановкой прямо в
текст удалённого скрипта: это и утечка в лог, и инъекция команд (пароль с
кавычкой или `$( )` ломал скрипт).

Тесты читают YAML как данные: проверяют порядок шагов (маска — до SSH),
отсутствие подстановки секрета в тело скрипта и то, что значение реально
передаётся через `envs`.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

yaml = pytest.importorskip('yaml')

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORKFLOW = os.path.join(ROOT, '.github', 'workflows', 'diagnostic.yml')


@pytest.fixture(scope='module')
def workflow():
    with open(WORKFLOW, encoding='utf-8') as fh:
        return yaml.safe_load(fh)


@pytest.fixture(scope='module')
def steps(workflow):
    return workflow['jobs']['diagnose']['steps']


def _ssh_step(steps):
    return next(s for s in steps if 'ssh' in str(s.get('uses', '')).lower())


def test_password_input_is_masked_before_the_remote_step(steps):
    names = [s.get('name', '') for s in steps]
    mask_index = next((i for i, n in enumerate(names) if 'Mask the password' in n), None)
    ssh_index = steps.index(_ssh_step(steps))

    assert mask_index is not None, 'нет шага маскировки входа — пароль попадёт в лог'
    assert mask_index < ssh_index, 'маска объявлена после шага, который печатает пароль'

    mask_step = steps[mask_index]
    assert '::add-mask::' in mask_step['run'], 'шаг не регистрирует значение в маске'
    assert 'github.event.inputs.new_password' in str(mask_step['env']), (
        'маска берёт не значение входа'
    )


def test_password_is_not_interpolated_into_the_script(steps):
    script = _ssh_step(steps)['with']['script']
    assert 'github.event.inputs.new_password' not in script, (
        'пароль подставляется в текст скрипта — утечка в лог и инъекция команд'
    )
    assert 'github.event.inputs.action' not in script, 'действие тоже должно идти через env'


def test_password_is_forwarded_through_envs(steps):
    ssh = _ssh_step(steps)
    envs = str(ssh['with'].get('envs', ''))
    env = ssh.get('env') or {}

    assert 'DIAG_PASSWORD' in envs, 'значение не пробрасывается на VM через envs'
    assert 'github.event.inputs.new_password' in str(env.get('DIAG_PASSWORD')), (
        'env не связан с введённым паролем'
    )


def test_script_reads_password_from_environment(steps):
    script = _ssh_step(steps)['with']['script']
    assert 'NEWPASS="$DIAG_PASSWORD"' in script, 'скрипт не берёт пароль из окружения'


def test_workflow_is_still_valid_yaml(workflow):
    # PyYAML по правилам YAML 1.1 разбирает ключ `on` как булево True — это
    # ловушка, а не ошибка файла.
    trigger = workflow.get('on') or workflow.get(True)
    assert trigger['workflow_dispatch']['inputs']['action']['required'] is True
    assert len(workflow['jobs']['diagnose']['steps']) >= 3
