/**
 * Copy text to the clipboard — including from an insecure origin.
 *
 * The app is served over plain HTTP (http://<ip>), and the async clipboard API
 * only exists in a secure context (HTTPS or localhost): there
 * `navigator.clipboard` is `undefined`, so `navigator.clipboard.writeText(...)`
 * throws a TypeError and every copy button does nothing (silently, when the
 * handler has no catch). Fall back to the legacy textarea + execCommand path,
 * which still works on HTTP.
 *
 * Returns whether the text actually reached the clipboard, so callers can tell
 * the user instead of failing silently.
 */
export async function copyText(text: string): Promise<boolean> {
  const clipboard = navigator.clipboard as Clipboard | undefined;
  if (window.isSecureContext && clipboard && typeof clipboard.writeText === 'function') {
    try {
      await clipboard.writeText(text);
      return true;
    } catch {
      // Permissions, focus or policy refused — try the legacy path below.
    }
  }
  return legacyCopy(text);
}

function legacyCopy(text: string): boolean {
  if (typeof document.execCommand !== 'function') return false;

  const area = document.createElement('textarea');
  area.value = text;
  area.setAttribute('readonly', '');
  area.style.position = 'fixed';
  area.style.top = '0';
  area.style.left = '-9999px';
  document.body.appendChild(area);

  const selection = document.getSelection();
  const previousRange =
    selection && selection.rangeCount > 0 ? selection.getRangeAt(0) : null;

  let copied = false;
  try {
    area.select();
    area.setSelectionRange(0, area.value.length);
    copied = document.execCommand('copy');
  } catch {
    copied = false;
  }

  document.body.removeChild(area);
  if (selection && previousRange) {
    selection.removeAllRanges();
    selection.addRange(previousRange);
  }
  return copied;
}
