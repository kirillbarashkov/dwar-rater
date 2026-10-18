import type { ReactNode } from 'react';
import './Markdown.css';

/**
 * Рендер markdown для вкладки «О проекте».
 *
 * Почему свой, а не библиотека: текстов всего четыре файла, а зависимость за собой
 * тянет бандл и обновления. Поддержано ровно то, что встречается в документах —
 * заголовки (1–4), абзацы, списки (`-`, `1.`, чек-листы `- [x]`), таблицы, цитаты,
 * линейки, блоки ``` и внутри строки: **жирный**, *курсив*, `код`, [ссылка](url).
 *
 * Сырой HTML не поддерживается намеренно: разметка собирается в React-узлы, поэтому
 * вставить тег из текста документа нельзя — XSS тут негде появиться.
 */

type ListItem = { text: string; checked?: boolean };

type Block =
  | { kind: 'heading'; level: number; text: string }
  | { kind: 'paragraph'; text: string }
  | { kind: 'list'; ordered: boolean; items: ListItem[] }
  | { kind: 'table'; head: string[]; rows: string[][] }
  | { kind: 'code'; text: string }
  | { kind: 'quote'; text: string }
  | { kind: 'rule' };

const HEADING = /^(#{1,4})\s+(.*)$/;
const RULE = /^\s*(-{3,}|\*{3,}|_{3,})\s*$/;
const QUOTE = /^\s*>\s?(.*)$/;
const LIST_ITEM = /^\s*(?:([-*+])|(\d+)\.)\s+(.*)$/;
const CHECKBOX = /^\[( |x|X)\]\s*(.*)$/;
const FENCE = /^\s*```/;
const TABLE_ROW = /^\s*\|/;
const TABLE_DIVIDER = /^\s*\|?[\s:|-]+\|[\s:|-]*$/;

function splitRow(line: string): string[] {
  const trimmed = line.trim().replace(/^\|/, '').replace(/\|$/, '');
  return trimmed.split('|').map((cell) => cell.trim());
}

/** Разбор markdown в блоки. Строки, не попавшие ни в один блок, склеиваются в абзац. */
function parseBlocks(markdown: string): Block[] {
  const lines = markdown.split(/\r?\n/);
  const blocks: Block[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];

    if (!line.trim()) {
      index += 1;
      continue;
    }

    if (FENCE.test(line)) {
      const code: string[] = [];
      index += 1;
      while (index < lines.length && !FENCE.test(lines[index])) {
        code.push(lines[index]);
        index += 1;
      }
      index += 1; // закрывающий забор
      blocks.push({ kind: 'code', text: code.join('\n') });
      continue;
    }

    const heading = HEADING.exec(line);
    if (heading) {
      blocks.push({ kind: 'heading', level: heading[1].length, text: heading[2].trim() });
      index += 1;
      continue;
    }

    if (RULE.test(line)) {
      blocks.push({ kind: 'rule' });
      index += 1;
      continue;
    }

    if (QUOTE.test(line)) {
      const quoted: string[] = [];
      while (index < lines.length) {
        const match = QUOTE.exec(lines[index]);
        if (!match) break;
        quoted.push(match[1].trim());
        index += 1;
      }
      blocks.push({ kind: 'quote', text: quoted.join(' ') });
      continue;
    }

    if (TABLE_ROW.test(line)) {
      const rows: string[][] = [];
      while (index < lines.length && TABLE_ROW.test(lines[index])) {
        // Разделитель шапки (`|---|:--:|`) — служебная строка, в вывод не идёт.
        if (!TABLE_DIVIDER.test(lines[index])) {
          rows.push(splitRow(lines[index]));
        }
        index += 1;
      }
      const [head = [], ...body] = rows;
      blocks.push({ kind: 'table', head, rows: body });
      continue;
    }

    const listItem = LIST_ITEM.exec(line);
    if (listItem) {
      const ordered = Boolean(listItem[2]);
      const items: ListItem[] = [];
      while (index < lines.length) {
        const match = LIST_ITEM.exec(lines[index]);
        if (!match) break;
        const checkbox = CHECKBOX.exec(match[3]);
        items.push(
          checkbox
            ? { text: checkbox[2].trim(), checked: checkbox[1].toLowerCase() === 'x' }
            : { text: match[3].trim() },
        );
        index += 1;
      }
      blocks.push({ kind: 'list', ordered, items });
      continue;
    }

    // Абзац: тянем строки до первой пустой или до начала следующего блока.
    const paragraph: string[] = [];
    while (index < lines.length) {
      const current = lines[index];
      if (
        !current.trim() ||
        HEADING.test(current) ||
        RULE.test(current) ||
        QUOTE.test(current) ||
        LIST_ITEM.test(current) ||
        FENCE.test(current) ||
        TABLE_ROW.test(current)
      ) {
        break;
      }
      paragraph.push(current.trim());
      index += 1;
    }
    blocks.push({ kind: 'paragraph', text: paragraph.join(' ') });
  }

  return blocks;
}

const INLINE = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g;

/** Адреса, которые вообще допустимо превращать в ссылку. */
function safeHref(url: string): string | null {
  const trimmed = url.trim();
  return /^(https?:\/\/|mailto:|\/)/i.test(trimmed) ? trimmed : null;
}

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  return text
    .split(INLINE)
    .filter((part) => part !== '')
    .map((part, i) => {
      const key = `${keyPrefix}-i${i}`;

      if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
        return <strong key={key}>{part.slice(2, -2)}</strong>;
      }
      if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
        return (
          <code className="md-inline-code" key={key}>
            {part.slice(1, -1)}
          </code>
        );
      }
      if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
        return <em key={key}>{part.slice(1, -1)}</em>;
      }

      const link = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(part);
      if (link) {
        const href = safeHref(link[2]);
        return href ? (
          <a key={key} href={href} target="_blank" rel="noreferrer noopener">
            {link[1]}
          </a>
        ) : (
          <span key={key}>{link[1]}</span>
        );
      }

      return <span key={key}>{part}</span>;
    });
}

function renderBlock(block: Block, index: number): ReactNode {
  const key = `b${index}`;

  switch (block.kind) {
    case 'heading': {
      const Tag = (`h${Math.min(block.level + 1, 5)}`) as 'h2' | 'h3' | 'h4' | 'h5';
      return (
        <Tag className={`md-heading md-h${block.level}`} key={key}>
          {renderInline(block.text, key)}
        </Tag>
      );
    }
    case 'paragraph':
      return (
        <p className="md-paragraph" key={key}>
          {renderInline(block.text, key)}
        </p>
      );
    case 'list':
      return block.ordered ? (
        <ol className="md-list" key={key}>
          {block.items.map((item, i) => (
            <li key={`${key}-l${i}`}>{renderInline(item.text, `${key}-l${i}`)}</li>
          ))}
        </ol>
      ) : (
        <ul className={`md-list${block.items.some((i) => i.checked !== undefined) ? ' md-checklist' : ''}`} key={key}>
          {block.items.map((item, i) => (
            <li key={`${key}-l${i}`}>
              {item.checked !== undefined && (
                <span className={`md-check ${item.checked ? 'is-done' : ''}`} aria-hidden="true">
                  {item.checked ? '☑' : '☐'}
                </span>
              )}
              {renderInline(item.text, `${key}-l${i}`)}
            </li>
          ))}
        </ul>
      );
    case 'table':
      return (
        <div className="md-table-wrap" key={key}>
          <table className="md-table">
            <thead>
              <tr>
                {block.head.map((cell, i) => (
                  <th key={`${key}-h${i}`}>{renderInline(cell, `${key}-h${i}`)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((row, r) => (
                <tr key={`${key}-r${r}`}>
                  {row.map((cell, c) => (
                    <td key={`${key}-r${r}c${c}`}>{renderInline(cell, `${key}-r${r}c${c}`)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    case 'code':
      return (
        <pre className="md-code" key={key}>
          <code>{block.text}</code>
        </pre>
      );
    case 'quote':
      return (
        <blockquote className="md-quote" key={key}>
          {renderInline(block.text, key)}
        </blockquote>
      );
    case 'rule':
      return <hr className="md-rule" key={key} />;
    default:
      return null;
  }
}

export function Markdown({ text }: { text: string }) {
  if (!text.trim()) return null;
  return <div className="md-body">{parseBlocks(text).map(renderBlock)}</div>;
}
