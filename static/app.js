let authHeader = null;
let lastAnalysisResult = null;
let lastAnalysisUrl = null;
let selectedSnapshotId = null;

async function fetchServerHistory() {
    try {
        const resp = await fetch('/api/snapshots', {
            headers: { 'Authorization': authHeader || '' }
        });
        if (resp.ok) {
            const data = await resp.json();
            return data.snapshots || [];
        }
    } catch (e) {
        console.error('Failed to fetch server history:', e);
    }
    return [];
}

async function renderHistory() {
    const list = document.getElementById('history-list');
    if (!list) return;

    const snapshots = await fetchServerHistory();
    console.log('renderHistory: snapshots count =', snapshots.length, 'selectedId =', selectedSnapshotId);

    if (snapshots.length === 0) {
        list.innerHTML = '<div class="history-empty">Нет сохранённых слепков</div>';
        return;
    }

    list.innerHTML = snapshots.map((snap) => {
        const isSelected = selectedSnapshotId && Number(selectedSnapshotId) === Number(snap.id);
        console.log(`  snap id=${snap.id}, selectedSnapshotId=${selectedSnapshotId}, match=${isSelected}`);
        return `
        <div class="history-item ${isSelected ? 'selected' : ''}">
            <div class="history-item-info" data-snapshot-id="${snap.id}">
                <span class="history-nick">${esc(snap.nick)}</span>
                <span class="history-snapshot-name">💾 ${esc(snap.snapshot_name || snap.name)}</span>
                <span class="history-date">${formatDate(snap.analyzed_at)}</span>
            </div>
            <button class="history-delete-db-btn" data-snapshot-id="${snap.id}" title="Удалить из БД">🗑</button>
        </div>`;
    }).join('');
}

function formatDate(isoStr) {
    if (!isoStr) return '';
    const d = new Date(isoStr);
    return d.toLocaleDateString('ru-RU') + ' ' + d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
}

function extractNick(url) {
    const match = url.match(/nick=([^&]+)/);
    if (match) return decodeURIComponent(match[1]);
    return url;
}

function selectHistoryItem(snapshotId) {
    selectedSnapshotId = String(snapshotId);
    console.log('selectHistoryItem called with:', selectedSnapshotId);
    fetch(`/api/snapshots/${snapshotId}`, {
        headers: { 'Authorization': authHeader || '' }
    })
    .then(resp => {
        console.log('Fetch response status:', resp.status);
        return resp.json();
    })
    .then(data => {
        console.log('Loaded snapshot:', data.snapshot_name, 'nick:', data.nick);
        renderResults(data);
        document.getElementById('results').classList.remove('hidden');
        updateSelectedLabel(data);
        expandHistory();
        renderHistory().then(() => {
            console.log('renderHistory done, selectedSnapshotId:', selectedSnapshotId);
            setTimeout(() => {
                const el = document.querySelector('.history-item.selected');
                console.log('Selected element found:', el !== null);
                if (el) el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
            }, 100);
        });
    })
    .catch(err => console.error('Failed to load snapshot:', err));
}

function updateSelectedLabel(data) {
    const label = document.getElementById('history-selected');
    if (!label) return;
    const name = data.snapshot_name || data.name || '';
    const nick = data.nick || '';
    label.textContent = `💾 ${nick} — ${name}`;
}

function toggleHistory() {
    const list = document.getElementById('history-list');
    const header = document.querySelector('.history-header');
    if (!list || !header) return;
    list.classList.toggle('hidden');
    header.classList.toggle('collapsed');
}

function collapseHistory() {
    const list = document.getElementById('history-list');
    const header = document.querySelector('.history-header');
    if (!list || !header) return;
    list.classList.add('hidden');
    header.classList.add('collapsed');
}

function expandHistory() {
    const list = document.getElementById('history-list');
    const header = document.querySelector('.history-header');
    if (!list || !header) return;
    list.classList.remove('hidden');
    header.classList.remove('collapsed');
}

// Event delegation for history list
document.getElementById('history-list').addEventListener('click', function(e) {
    const deleteDbBtn = e.target.closest('.history-delete-db-btn');
    if (deleteDbBtn) {
        e.stopPropagation();
        const snapshotId = deleteDbBtn.getAttribute('data-snapshot-id');
        deleteSnapshotFromDb(snapshotId);
        return;
    }
    const historyItem = e.target.closest('.history-item');
    if (historyItem) {
        const itemInfo = historyItem.querySelector('.history-item-info');
        if (itemInfo) {
            const snapshotId = itemInfo.getAttribute('data-snapshot-id');
            console.log('Clicked history item, snapshotId:', snapshotId);
            selectHistoryItem(snapshotId);
        }
    }
});

// Toggle history on header click
document.querySelector('.history-header').addEventListener('click', function(e) {
    toggleHistory();
});

// Login
document.getElementById('login-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    const user = document.getElementById('login-user').value.trim();
    const pass = document.getElementById('login-pass').value;
    const loginError = document.getElementById('login-error');

    if (!user || !pass) return;

    const encoded = btoa(`${user}:${pass}`);
    authHeader = `Basic ${encoded}`;

    try {
        const resp = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Authorization': authHeader }
        });

        if (resp.status === 401) {
            loginError.textContent = 'Неверный логин или пароль';
            loginError.classList.remove('hidden');
            authHeader = null;
            return;
        }

        document.getElementById('login-section').classList.add('hidden');
        document.getElementById('main-section').classList.remove('hidden');
        document.getElementById('history-section').classList.remove('hidden');
        renderHistory().catch(e => console.error('Failed to load history:', e));
        collapseHistory();
    } catch (err) {
        loginError.textContent = 'Ошибка подключения';
        loginError.classList.remove('hidden');
        authHeader = null;
    }
});

// Logout
document.getElementById('logout-btn').addEventListener('click', function() {
    authHeader = null;
    document.getElementById('main-section').classList.add('hidden');
    document.getElementById('history-section').classList.add('hidden');
    document.getElementById('login-section').classList.remove('hidden');
    document.getElementById('results').classList.add('hidden');
    document.getElementById('login-user').value = '';
    document.getElementById('login-pass').value = '';
});

// Clear input
document.getElementById('clear-btn').addEventListener('click', function() {
    document.getElementById('url-input').value = '';
    document.getElementById('url-input').focus();
});

// Search form
document.getElementById('search-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    const url = document.getElementById('url-input').value.trim();
    if (!url) return;

    const btn = document.getElementById('analyze-btn');
    const loading = document.getElementById('loading');
    const results = document.getElementById('results');
    const errorMsg = document.getElementById('error-msg');

    btn.disabled = true;
    btn.textContent = 'Загрузка...';
    loading.classList.remove('hidden');
    results.classList.add('hidden');
    errorMsg.classList.add('hidden');

    try {
        const resp = await fetch('/api/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': authHeader || ''
            },
            body: JSON.stringify({ url, save_to_db: false })
        });

        const data = await resp.json();

        if (!resp.ok) {
            throw new Error(data.error || 'Неизвестная ошибка');
        }

        lastAnalysisResult = data;
        lastAnalysisUrl = url;

        renderResults(data);
        results.classList.remove('hidden');
    } catch (err) {
        errorMsg.textContent = err.message;
        errorMsg.classList.remove('hidden');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Анализировать';
        loading.classList.add('hidden');
    }
});

function renderResults(data) {
    const content = document.getElementById('results-content');

    if (data.profile_closed) {
        content.innerHTML = renderClosedProfile(data);
        return;
    }

    content.innerHTML = `
        ${renderCharHeader(data)}
        ${renderTabs(data)}
    `;
    initTabs();
}

function renderClosedProfile(d) {
    const ci = d.closed_info || {};
    const rankNames = {
        '1': 'Новичок', '2': 'Боец', '3': 'Страж', '4': 'Гладиатор',
        '5': 'Чемпион', '6': 'Ветеран', '7': 'Полководец', '8': 'Мастер войны',
        '9': 'Герой', '10': 'Легенда'
    };
    const rankLabel = rankNames[ci.rank] || `Ранг ${ci.rank}`;

    return `
    <div class="section closed-profile-section">
        <div class="section-title" style="color:var(--accent)">🔒 Профиль закрыт</div>
        <div class="closed-profile-card">
            <div class="closed-profile-header">
                <div>
                    <div class="char-name">${esc(d.name)}</div>
                    <div style="color:var(--text-secondary);margin-top:4px">
                        ${ci.level ? `Уровень ${ci.level} · ` : ''}${rankLabel}
                    </div>
                    ${ci.premium_level && ci.premium_level !== '0' ? `<div style="color:var(--gold);font-size:0.85rem;margin-top:2px">⭐ Premium аккаунт</div>` : ''}
                </div>
            </div>
            ${ci.description ? `<div class="closed-profile-desc">${esc(ci.description)}</div>` : ''}
            <div class="closed-profile-notice">
                Игрок скрыл информацию о своём персонаже. Доступны только базовые данные.
            </div>
        </div>
    </div>`;
}

function renderCharHeader(d) {
    return `
    <div class="char-header">
        <div>
            <div class="char-name">${esc(d.name)}</div>
            <div style="color:var(--text-secondary);margin-top:4px">${esc(d.race)} · ${esc(d.rank)}</div>
            ${d.clan ? `<div style="color:var(--text-muted);font-size:0.85rem">${esc(d.clan)} · ${esc(d.clan_rank)}</div>` : ''}
        </div>
        <div class="char-meta">
            <div class="meta-item">
                <div class="label">Победы</div>
                <div class="value gold">${d.wins}</div>
            </div>
            <div class="meta-item">
                <div class="label">Поражения</div>
                <div class="value">${d.losses}</div>
            </div>
            <div class="meta-item">
                <div class="label">Winrate</div>
                <div class="value accent">${d.winrate}%</div>
            </div>
            <div class="meta-item">
                <div class="label">Предметов</div>
                <div class="value">${Object.values(d.equipment_by_kind).flat().length}</div>
            </div>
        </div>
    </div>`;
}

function renderTabs(d) {
    const tabs = [
        { id: 'tab-stats', label: 'Характеристики' },
        { id: 'tab-equip', label: 'Экипировка' },
        { id: 'tab-effects', label: 'Эффекты' },
        { id: 'tab-records', label: 'Рекорды' },
        { id: 'tab-medals', label: 'Медали' },
        { id: 'tab-other', label: 'Прочее' },
    ];

    return `
    <div class="tabs">
        ${tabs.map((t, i) => `<button class="tab-btn ${i === 0 ? 'active' : ''}" data-tab="${t.id}">${t.label}</button>`).join('')}
    </div>
    <div class="tab-content active" id="tab-stats">${renderStats(d)}</div>
    <div class="tab-content" id="tab-equip">${renderEquipment(d)}</div>
    <div class="tab-content" id="tab-effects">${renderEffects(d)}</div>
    <div class="tab-content" id="tab-records">${renderRecords(d)}</div>
    <div class="tab-content" id="tab-medals">${renderMedals(d)}</div>
    <div class="tab-content" id="tab-other">${renderOther(d)}</div>
    `;
}

function renderStats(d) {
    let html = '';

    html += `<div class="section"><div class="section-title">Основные характеристики</div><div class="stats-grid">`;
    for (const [k, v] of Object.entries(d.main_stats)) {
        html += `<div class="stat-item"><span class="stat-label">${esc(k)}</span><span class="stat-value">${v}</span></div>`;
    }
    html += `</div></div>`;

    html += `<div class="section"><div class="section-title">Боевые характеристики</div><div class="stats-grid">`;
    for (const [k, v] of Object.entries(d.combat_stats)) {
        html += `<div class="stat-item"><span class="stat-label">${esc(k)}</span><span class="stat-value">${v}</span></div>`;
    }
    html += `</div></div>`;

    html += `<div class="section"><div class="section-title">Магические характеристики</div><div class="stats-grid">`;
    for (const [k, v] of Object.entries(d.magic_stats)) {
        html += `<div class="stat-item"><span class="stat-label">${esc(k)}</span><span class="stat-value">${v}</span></div>`;
    }
    html += `</div></div>`;

    return html;
}

function renderEquipment(d) {
    let html = '';

    const setKeys = Object.keys(d.sets);
    if (setKeys.length > 0) {
        html += `<div class="section"><div class="section-title">Комплекты</div><div class="sets-section">`;
        for (const setName of setKeys) {
            const items = d.sets[setName];
            html += `<span class="set-tag"><span class="set-name">${esc(setName)}</span> <span class="set-count">(${items.length} шт.)</span></span>`;
        }
        html += `</div></div>`;
    }

    const slotOrder = ['Шлем', 'Наплечники', 'Кираса', 'Кольчуга', 'Наручи', 'Поножи', 'Обувь', 'Основное', 'Двуручное', 'Лук', 'Легкий щит', 'Кольца', 'Амулет'];

    html += `<div class="section"><div class="section-title">Экипировка по слотам</div>`;

    for (const slot of slotOrder) {
        const items = d.equipment_by_kind[slot];
        if (!items || items.length === 0) continue;

        html += `<div class="equip-slot"><div class="equip-slot-title">${esc(slot)}</div>`;

        for (const item of items) {
            const hasSet = item.set ? 'has-set' : '';
            html += `<div class="equip-item ${hasSet}">`;
            html += `<div class="equip-header">`;
            html += `<span class="equip-name">${esc(item.title)}</span>`;
            html += `<div class="equip-badges">`;
            html += `<span class="badge badge-quality" style="background:${item.quality.color}">${item.quality.emoji} ${item.quality.name}</span>`;
            if (item.level !== '—') html += `<span class="badge badge-level">Ур. ${item.level}</span>`;
            html += `<span class="badge badge-trend">${esc(item.trend)}</span>`;
            if (item.set) html += `<span class="badge badge-set">${esc(item.set)}</span>`;
            html += `</div></div>`;

            html += `<div style="font-size:0.8rem;color:var(--text-muted);margin-bottom:6px">Прочность: ${item.durability}</div>`;

            if (item.skills.length > 0) {
                html += `<div style="font-size:0.8rem;color:var(--text-muted);margin-bottom:4px">Характеристики:</div>`;
                html += `<div class="skills-list">`;
                for (const sk of item.skills) {
                    html += `<span class="skill-tag">${esc(sk.title)}: <span class="skill-val">${esc(sk.value)}</span></span>`;
                }
                html += `</div>`;
            }

            if (item.skills_e.length > 0) {
                html += `<div style="font-size:0.8rem;color:var(--text-muted);margin-top:6px;margin-bottom:4px">Доп. характеристики:</div>`;
                html += `<div class="skills-list">`;
                for (const sk of item.skills_e) {
                    html += `<span class="skill-tag">${esc(sk.title)}: <span class="skill-val">${esc(sk.value)}</span></span>`;
                }
                html += `</div>`;
            }

            if (item.enchants.length > 0) {
                html += `<div class="enchants-list">`;
                for (const ench of item.enchants) {
                    html += `<div class="enchant-item"><span class="enchant-type">${ench.type}:</span> ${esc(ench.value)}</div>`;
                }
                html += `</div>`;
            }

            html += `</div>`;
        }

        html += `</div>`;
    }

    html += `</div>`;
    return html;
}

function renderEffects(d) {
    let html = '';

    const permEff = d.permanent_effects || [];
    const tempEff = d.temp_effects || [];
    const totalEffects = permEff.length + tempEff.length;

    if (totalEffects === 0) {
        return `<div class="section"><div class="section-title">Эффекты</div><p style="color:var(--text-muted)">Нет активных эффектов</p></div>`;
    }

    if (permEff.length > 0) {
        html += `<div class="section"><div class="section-title">Постоянные эффекты</div>`;
        html += renderEffectTable(permEff, false);
        html += `</div>`;
    }

    const categories = {
        buff: { label: 'Баффы', items: [] },
        elixir: { label: 'Эликсиры', items: [] },
        mount: { label: 'Маунты', items: [] },
        debuff: { label: 'Дебаффы', items: [] },
        other: { label: 'Прочее', items: [] },
    };

    for (const eff of tempEff) {
        const cat = eff.category || 'other';
        if (categories[cat]) {
            categories[cat].items.push(eff);
        } else {
            categories.other.items.push(eff);
        }
    }

    for (const [key, cat] of Object.entries(categories)) {
        if (cat.items.length === 0) continue;
        html += `<div class="section"><div class="section-title">${cat.label} (${cat.items.length})</div>`;
        html += renderEffectTable(cat.items, true);
        html += `</div>`;
    }

    return html;
}

function renderEffectTable(effects, isTemp) {
    let html = `<table class="data-table effect-table"><thead><tr>`;
    html += `<th style="width:30%">Название</th>`;
    html += `<th style="width:10%">Качество</th>`;
    if (isTemp) html += `<th style="width:10%">Время</th>`;
    html += `<th style="width:40%">Характеристики</th>`;
    html += `<th style="width:10%">Тип</th>`;
    html += `</tr></thead><tbody>`;

    for (const eff of effects) {
        html += `<tr>`;
        html += `<td><strong>${esc(eff.title)}</strong></td>`;
        html += `<td><span class="badge badge-quality" style="background:${eff.quality.color}">${eff.quality.emoji} ${eff.quality.name}</span></td>`;
        if (isTemp) {
            html += `<td><span class="badge badge-time">⏱ ${esc(eff.time_left)}</span></td>`;
        }
        html += `<td>`;
        if (eff.skills && eff.skills.length > 0) {
            html += `<div class="effect-table-skills">`;
            for (const sk of eff.skills) {
                html += `<span class="skill-tag">${esc(sk.title)}: <span class="skill-val">${esc(sk.value)}</span></span>`;
            }
            html += `</div>`;
        } else {
            html += `<span style="color:var(--text-muted);font-size:0.8rem">—</span>`;
        }
        html += `</td>`;
        html += `<td>`;
        if (isTemp) {
            const catLabels = { buff: 'Бафф', elixir: 'Эликсир', mount: 'Маунт', debuff: 'Дебафф', other: '—' };
            html += `<span style="font-size:0.8rem;color:var(--text-secondary)">${catLabels[eff.category] || '—'}</span>`;
        } else {
            html += `<span style="font-size:0.8rem;color:var(--text-secondary)">Пост.</span>`;
        }
        html += `</td>`;
        html += `</tr>`;
    }

    html += `</tbody></table>`;
    return html;
}

function renderRecords(d) {
    let html = `<div class="section"><div class="section-title">Боевые рекорды</div>`;
    html += `<table class="data-table"><thead><tr><th>Параметр</th><th style="text-align:right">Значение</th></tr></thead><tbody>`;
    for (const [k, v] of Object.entries(d.combat_records)) {
        html += `<tr><td>${esc(k)}</td><td class="num">${v}</td></tr>`;
    }
    html += `</tbody></table></div>`;

    html += `<div class="section"><div class="section-title">Великие битвы</div>`;
    html += `<table class="data-table"><tbody>`;
    html += `<tr><td>Победы</td><td class="num">${d.great_battles.wins}</td></tr>`;
    html += `<tr><td>Участие</td><td class="num">${d.great_battles.total}</td></tr>`;
    html += `<tr><td>Winrate</td><td class="num">${d.great_battles.winrate}%</td></tr>`;
    html += `</tbody></table></div>`;

    return html;
}

function renderMedals(d) {
    const REP_POINTS = {
        'Серый': 10,
        'Зелёный': 20,
        'Синий': 50,
        'Фиолетовый': 100,
        'Красный': 300,
        'Оранжевый': 200,
        'Уникальный': 500,
    };

    const QUALITY_ORDER = ['Серый', 'Зелёный', 'Синий', 'Фиолетовый', 'Красный', 'Оранжевый', 'Уникальный'];

    const groups = {};
    let totalRep = 0;

    for (const m of d.medals) {
        const qName = m.quality.name;
        if (!groups[qName]) {
            groups[qName] = { quality: m.quality, items: [], repTotal: 0, byRep: {} };
        }
        groups[qName].items.push(m);
        const points = REP_POINTS[qName] || 0;
        groups[qName].repTotal += points;
        totalRep += points;

        const rep = m.reputation || 'Общая';
        if (!groups[qName].byRep[rep]) {
            groups[qName].byRep[rep] = [];
        }
        groups[qName].byRep[rep].push(m);
    }

    let html = '';

    html += `<div class="section"><div class="section-title">Медали (${d.medals.length} шт.)</div>`;
    html += `<div class="medal-summary">`;
    html += `<div class="medal-summary-total">Итого репутационный рейтинг: <strong>${totalRep}</strong></div>`;
    for (const qName of QUALITY_ORDER) {
        const g = groups[qName];
        if (!g) continue;
        html += `<div class="medal-summary-row">`;
        html += `<span class="badge badge-quality" style="background:${g.quality.color}">${g.quality.emoji} ${qName}</span>`;
        html += `<span class="medal-summary-count">${g.items.length} шт.</span>`;
        html += `<span class="medal-summary-rep">= ${g.repTotal} очков</span>`;
        html += `</div>`;
    }
    html += `</div></div>`;

    for (const qName of QUALITY_ORDER) {
        const g = groups[qName];
        if (!g) continue;

        const repKeys = Object.keys(g.byRep);
        html += `<div class="section"><div class="section-title">${g.quality.emoji} ${qName} (${g.items.length} шт. / ${g.repTotal} очков)</div>`;
        html += `<table class="data-table medal-table"><thead><tr>`;
        html += `<th style="width:25%">Репутация</th>`;
        html += `<th style="width:20%">Медаль</th>`;
        html += `<th style="width:55%">Описание</th>`;
        html += `</tr></thead><tbody>`;

        for (const rep of repKeys) {
            const repItems = g.byRep[rep];
            for (const m of repItems) {
                html += `<tr>`;
                html += `<td><strong>${esc(m.reputation)}</strong></td>`;
                html += `<td>${esc(m.title)}</td>`;
                html += `<td class="medal-desc">${esc(m.description)}</td>`;
                html += `</tr>`;
            }
        }

        html += `</tbody></table></div>`;
    }

    return html;
}

function renderOther(d) {
    let html = '';

    html += `<div class="section"><div class="section-title">Профессии</div>`;
    html += `<table class="data-table"><thead><tr><th>Профессия</th><th style="text-align:right">Уровень</th></tr></thead><tbody>`;
    for (const [k, v] of Object.entries(d.professions)) {
        html += `<tr><td>${esc(k)}</td><td class="num">${v}</td></tr>`;
    }
    html += `</tbody></table></div>`;

    html += `<div class="section"><div class="section-title">Достижения</div>`;
    html += `<table class="data-table"><tbody>`;
    for (const [k, v] of Object.entries(d.achievements)) {
        html += `<tr><td>${esc(k)}</td><td class="num">${v}</td></tr>`;
    }
    html += `</tbody></table></div>`;

    if (d.manor_location) {
        html += `<div class="section"><div class="section-title">Поместье</div>`;
        html += `<p style="margin-bottom:10px">Расположение: <strong>${esc(d.manor_location)}</strong></p>`;
        if (d.manor_buildings.length > 0) {
            html += `<div class="manor-buildings">`;
            for (const b of d.manor_buildings) {
                html += `<span class="building-tag">${esc(b)}</span>`;
            }
            html += `</div>`;
        }
        html += `</div>`;
    }

    return html;
}

function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            this.classList.add('active');
            document.getElementById(this.dataset.tab).classList.add('active');
        });
    });
}

function esc(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

document.getElementById('save-pdf-btn').addEventListener('click', function() {
    const btn = this;
    btn.disabled = true;
    btn.textContent = 'Генерация PDF...';

    const content = document.getElementById('results-content');
    const clone = content.cloneNode(true);

    clone.querySelectorAll('.tab-content').forEach(tc => {
        tc.classList.add('active');
        tc.style.display = 'block';
    });

    clone.querySelectorAll('.tabs').forEach(t => t.remove());

    const wrapper = document.createElement('div');
    wrapper.style.background = '#1a1a2e';
    wrapper.style.color = '#e0e0e0';
    wrapper.style.padding = '20px';
    wrapper.style.fontFamily = 'Segoe UI, Tahoma, sans-serif';
    wrapper.appendChild(clone);

    document.body.appendChild(wrapper);

    const charName = document.querySelector('.char-name')?.textContent || 'character';
    const opt = {
        margin:       [10, 10, 10, 10],
        filename:     `${charName}.pdf`,
        image:        { type: 'jpeg', quality: 0.98 },
        html2canvas:  { scale: 2, useCORS: true, backgroundColor: '#1a1a2e' },
        jsPDF:        { unit: 'mm', format: 'a4', orientation: 'portrait' },
        pagebreak:    { mode: ['avoid-all', 'css', 'legacy'] }
    };

    html2pdf().set(opt).from(wrapper).save().then(() => {
        document.body.removeChild(wrapper);
        btn.disabled = false;
        btn.textContent = '📄 Сохранить в PDF';
    }).catch(() => {
        document.body.removeChild(wrapper);
        btn.disabled = false;
        btn.textContent = '📄 Сохранить в PDF';
    });
});

document.getElementById('save-html-btn').addEventListener('click', async function() {
    const btn = this;
    btn.disabled = true;
    btn.textContent = 'Генерация HTML...';

    const content = document.getElementById('results-content');
    const charName = document.querySelector('.char-name')?.textContent || 'character';

    const clone = content.cloneNode(true);
    clone.querySelectorAll('.tab-content').forEach(tc => {
        tc.classList.add('active');
        tc.style.display = 'block';
    });
    clone.querySelectorAll('.tabs').forEach(t => t.remove());

    let cssContent = '';
    try {
        const resp = await fetch('/static/style.css');
        cssContent = await resp.text();
    } catch (e) {
        console.error('Failed to fetch CSS:', e);
    }

    const htmlDoc = `<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${esc(charName)} — Dwar Rater</title>
<style>
:root {
    --bg-primary: #1a1a2e;
    --bg-secondary: #16213e;
    --bg-card: #1c2541;
    --bg-card-hover: #243056;
    --text-primary: #e0e0e0;
    --text-secondary: #a0a0b0;
    --text-muted: #6b6b80;
    --accent: #e94560;
    --accent-hover: #ff6b81;
    --border: #2a2a4a;
    --gold: #ffd700;
    --green: #339900;
    --blue: #3300ff;
    --purple: #990099;
    --orange: #ff0000;
    --red: #016e71;
    --unique: #f55e27;
    --radius: 8px;
    --shadow: 0 2px 12px rgba(0,0,0,0.3);
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    min-height: 100vh;
    line-height: 1.6;
    padding: 24px;
}
${cssContent}
</style>
</head>
<body>
${clone.innerHTML}
</body>
</html>`;

    const blob = new Blob([htmlDoc], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${charName}.html`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    btn.disabled = false;
    btn.textContent = '🌐 Сохранить в HTML';
});

// Save to DB
document.getElementById('save-db-btn').addEventListener('click', function() {
    if (!lastAnalysisResult) {
        alert('Сначала выполните анализ персонажа');
        return;
    }
    document.getElementById('save-db-modal').classList.remove('hidden');
    document.getElementById('snapshot-name').value = lastAnalysisResult.name || '';
    document.getElementById('snapshot-name').focus();
});

document.getElementById('cancel-save-db').addEventListener('click', function() {
    document.getElementById('save-db-modal').classList.add('hidden');
});

document.getElementById('confirm-save-db').addEventListener('click', async function() {
    const name = document.getElementById('snapshot-name').value.trim();
    if (!name) {
        document.getElementById('snapshot-name').focus();
        return;
    }

    const btn = this;
    btn.disabled = true;
    btn.textContent = 'Сохранение...';

    try {
        const resp = await fetch('/api/save-snapshot', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': authHeader || ''
            },
            body: JSON.stringify({
                snapshot_data: lastAnalysisResult,
                snapshot_name: name,
                url: lastAnalysisUrl
            })
        });

        if (!resp.ok) {
            const data = await resp.json();
            throw new Error(data.error || 'Ошибка сохранения');
        }

        btn.textContent = '✓ Сохранено';
        setTimeout(() => {
            btn.textContent = '💾 Сохранить в БД';
            btn.disabled = false;
        }, 2000);

        document.getElementById('save-db-modal').classList.add('hidden');
        renderHistory();
    } catch (err) {
        alert('Ошибка: ' + err.message);
        btn.disabled = false;
        btn.textContent = '💾 Сохранить в БД';
    }
});

// Enter key in snapshot name input
document.getElementById('snapshot-name').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') {
        document.getElementById('confirm-save-db').click();
    }
    if (e.key === 'Escape') {
        document.getElementById('cancel-save-db').click();
    }
});

async function deleteSnapshotFromDb(snapshotId) {
    if (!confirm('Удалить слепок из базы данных?')) return;

    try {
        const resp = await fetch(`/api/snapshots/${snapshotId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': authHeader || ''
            }
        });

        if (!resp.ok) {
            const data = await resp.json();
            throw new Error(data.error || 'Ошибка удаления');
        }

        renderHistory();
    } catch (err) {
        alert('Ошибка: ' + err.message);
    }
}

// Enter key in snapshot name input
document.getElementById('snapshot-name').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') {
        document.getElementById('confirm-save-db').click();
    }
    if (e.key === 'Escape') {
        document.getElementById('cancel-save-db').click();
    }
});

async function deleteSnapshotFromDb(snapshotId) {
    if (!confirm('Удалить слепок из базы данных?')) return;

    try {
        const resp = await fetch(`/api/snapshots/${snapshotId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': authHeader || ''
            }
        });

        if (!resp.ok) {
            const data = await resp.json();
            throw new Error(data.error || 'Ошибка удаления');
        }

        renderHistory();
    } catch (err) {
        alert('Ошибка: ' + err.message);
    }
}
