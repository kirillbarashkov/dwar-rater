import type { KeyboardEvent } from 'react';

/**
 * A58: свойства для кликабельного не-`<button>` элемента.
 *
 * Раньше в пяти местах `ClanOverview`, в строке казны `TreasuryTab` и в
 * переключателе `CharacterPanel` клик висел на `<div>`/`<td>`: мышью работает,
 * с клавиатуры — нет. У `CharacterPanel` были `role="button"` и `tabIndex={0}`,
 * но без `onKeyDown` Enter и Space не срабатывали — элемент попадал в порядок
 * табуляции и молчал.
 *
 * Где можно, элемент должен быть настоящим `<button>`. Этот помощник — для
 * случаев, когда разметка диктует иное (`<td>` внутри таблицы, контейнер строки
 * дерева): он даёт роль, фокус и обе клавиши активации.
 *
 * Space гасится через `preventDefault`, иначе страница прокрутится вместе с
 * активацией — так же ведёт себя нативная кнопка.
 */
export function clickableProps(onActivate: () => void) {
  return {
    role: 'button' as const,
    tabIndex: 0,
    onClick: onActivate,
    onKeyDown: (event: KeyboardEvent<HTMLElement>) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        onActivate();
      }
    },
  };
}
