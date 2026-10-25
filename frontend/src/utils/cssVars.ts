import type { CSSProperties } from 'react';

/**
 * A59: единственное место, где CSS-переменная подставляется в инлайн-стиль.
 *
 * Раньше в компоненте стояло `style={{ '--prof-color': … } as React.CSSProperties}`:
 * TypeScript не знает про кастомные свойства, и приведение глушило проверку
 * целиком — опечатка в имени переменной (`--prof-colour`) прошла бы молча и
 * просто не применилась бы.
 *
 * Ключ типа `--${string}` не даёт передать обычное свойство (`color`, `width`) —
 * для них есть CSS-классы и токены. Значение остаётся свободным: это либо
 * `var(--…)`, либо вычисленное в рантайме.
 */
export function cssVars(vars: Record<`--${string}`, string | number>): CSSProperties {
  return vars as CSSProperties;
}
