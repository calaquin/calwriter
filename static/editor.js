function execCmd(command, value = null) {
    document.execCommand(command, false, value);
}

function findAndReplace() {
    const findText = prompt('Find text:');
    if (!findText) return;
    const replaceText = prompt('Replace with:', '');
    if (replaceText === null) return;
    const editor = document.getElementById('chapter_editor');
    if (!editor) return;
    const regex = new RegExp(findText, 'g');
    editor.innerHTML = editor.innerHTML.replace(regex, replaceText);
    updateWordCount();
}

function togglePreEdit() {
    const body = document.body;
    body.classList.toggle('preedit-mode');
    const btn = document.getElementById('preedit_toggle');
    if (btn) btn.classList.toggle('active', body.classList.contains('preedit-mode'));
}

const preEditIcons = {
    'pe-cut': '✂️',
    'pe-pin': '📌',
    'pe-spiral': '🌀',
    'pe-contradict': '⁉️',
    'pe-love': '❤️'
};

function clearPreEditTags() {
    if (!document.body.classList.contains('preedit-mode')) return;
    const sel = window.getSelection();
    if (!sel.rangeCount) return;
    const range = sel.getRangeAt(0);
    document.querySelectorAll('#chapter_editor .pe').forEach(span => {
        if (range.intersectsNode(span)) span.remove();
    });
    sel.removeAllRanges();
    const editor = document.getElementById('chapter_editor');
    if (editor) editor.dispatchEvent(new Event('input'));
}

function insertPreEditIcon(cls) {
    if (!document.body.classList.contains('preedit-mode')) return;
    const editor = document.getElementById('chapter_editor');
    if (!editor) return;
    editor.focus();
    const sel = window.getSelection();
    if (!sel.rangeCount) return;
    const range = sel.getRangeAt(0);
    const span = document.createElement('span');
    span.className = 'pe ' + cls;
    range.insertNode(span);
    range.setStartAfter(span);
    sel.removeAllRanges();
    sel.addRange(range);
    editor.dispatchEvent(new Event('input'));
}

function toggleTree(el) {
    const li = el.closest('li');
    if (li) {
        li.classList.toggle('collapsed');
        const path = li.dataset.path;
        if (path) {
            const collapsed = li.classList.contains('collapsed');
            localStorage.setItem('collapsed:' + path, collapsed ? '1' : '0');
        }
    }
}
function prepareChapter() {
    document.getElementById('chapter_text').value = document.getElementById('chapter_editor').innerHTML;
}

function updateWordCount() {
    const editor = document.getElementById('chapter_editor');
    if (!editor) return;
    const text = editor.innerText || '';
    const words = text.trim().split(/\s+/).filter(Boolean);
    const counter = document.getElementById('word_count');
    if (counter) counter.textContent = words.length;
}

function colorFromString(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    const h = Math.abs(hash) % 360;
    return `hsl(${h},70%,90%)`;
}

function sortTabs(tabs) {
    const order = [];
    tabs.forEach(t => {
        const root = t.folder.split('/')[0];
        if (!order.includes(root)) order.push(root);
    });
    tabs.sort((a, b) => {
        const ra = a.folder.split('/')[0];
        const rb = b.folder.split('/')[0];
        const ia = order.indexOf(ra);
        const ib = order.indexOf(rb);
        if (ia !== ib) return ia - ib;
        return a.name.localeCompare(b.name);
    });
}


document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('form.close-book-form').forEach(form => {
        form.addEventListener('submit', () => {
            const match = form.action.match(/\/folder\/(.+)\/close$/);
            if (match) {
                const root = match[1];
                let tabs = JSON.parse(localStorage.getItem('open_tabs') || '[]');
                tabs = tabs.filter(t => !t.folder.startsWith(root));
                localStorage.setItem('open_tabs', JSON.stringify(tabs));
            }
        });
    });
    document.querySelectorAll('#sidebar .tree-item').forEach(li => {
        const path = li.dataset.path;
        if (path && localStorage.getItem('collapsed:' + path) === '1') {
            li.classList.add('collapsed');
        }
    });
    const editor = document.getElementById('chapter_editor');
    if (editor) {
        let timeout;
        editor.addEventListener('input', () => {
            updateWordCount();
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                fetch(editor.dataset.saveUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded'
                    },
                    body: new URLSearchParams({text: editor.innerHTML})
                });
            }, 1000);
        });
        updateWordCount();
    }
    const undoBtn = document.getElementById('undo_btn');
    if (undoBtn && editor) {
        undoBtn.addEventListener('click', () => execCmd('undo'));
    }
    const redoBtn = document.getElementById('redo_btn');
    if (redoBtn && editor) {
        redoBtn.addEventListener('click', () => execCmd('redo'));
    }
    const notes = document.getElementById('notes_editor');
    if (notes) {
        let timeout;
        notes.addEventListener('input', () => {
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                fetch(notes.dataset.saveUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded'
                    },
                    body: new URLSearchParams({notes: notes.value})
                });
            }, 500);
        });
    }

    const sidebar = document.getElementById('notes_sidebar');
    const resizer = document.getElementById('notes_resizer');
    if (sidebar && resizer) {
        const storedWidth = localStorage.getItem('notesWidth');
        if (storedWidth) sidebar.style.width = storedWidth;
        let startX, startWidth;
        const saveWidth = () => {
            localStorage.setItem('notesWidth', sidebar.style.width);
        };
        const onMove = e => {
            const dx = e.clientX - startX;
            sidebar.style.width = (startWidth - dx) + 'px';
        };
        const stopDrag = () => {
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', stopDrag);
            saveWidth();
        };
        resizer.addEventListener('mousedown', e => {
            startX = e.clientX;
            startWidth = sidebar.offsetWidth;
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', stopDrag);
        });
    }

    document.querySelectorAll('.preedit-icons button[data-class]').forEach(btn => {
        btn.addEventListener('click', () => insertPreEditIcon(btn.dataset.class));
    });

    setupTabs();

    document.querySelectorAll('.sortable').forEach(ul => {
        enableDragSort(ul);
    });
});

function setupTabs() {
    const tabsEl = document.getElementById('chapter_tabs');
    if (!tabsEl) return;
    const currentFolder = tabsEl.dataset.folder;
    const currentChapter = tabsEl.dataset.chapter;
    const currentType = tabsEl.dataset.type || 'chapter';
    let tabs = JSON.parse(localStorage.getItem('open_tabs') || '[]');
    const existing = tabs.find(t => t.folder === currentFolder && t.name === currentChapter && t.type === currentType);
    if (!existing) {
        tabs.push({folder: currentFolder, name: currentChapter, type: currentType});
        sortTabs(tabs);
        localStorage.setItem('open_tabs', JSON.stringify(tabs));
    } else {
        sortTabs(tabs);
    }
    renderTabs(tabsEl, tabs, currentFolder, currentChapter, currentType);
    window.addEventListener('storage', (e) => {
        if (e.key === 'open_tabs') {
            const updated = JSON.parse(e.newValue || '[]');
            const stillOpen = updated.some(t => t.folder === currentFolder && t.name === currentChapter && t.type === currentType);
            if (!stillOpen) {
                if (updated.length) {
                    const next = updated[updated.length - 1];
                    window.location.href = `/folder/${next.folder}/chapter/${next.name}`;
                } else {
                    window.location.href = '/';
                }
                return;
            }
            renderTabs(tabsEl, updated, currentFolder, currentChapter, currentType);
        }
    });
}


function enableTabDrag(container, tabs, currentFolder, currentChapter, currentType) {
    let dragging;
    container.querySelectorAll('.chapter-tab').forEach((tab) => {
        tab.draggable = true;
        tab.addEventListener('dragstart', () => {
            dragging = tab;
        });
        tab.addEventListener('dragover', e => {
            e.preventDefault();
            const rect = tab.getBoundingClientRect();
            const next = (e.clientX - rect.left) > (rect.width / 2);
            tab.parentNode.insertBefore(dragging, next ? tab.nextSibling : tab);
        });
        tab.addEventListener('drop', () => {
            const newOrder = Array.from(container.querySelectorAll('.chapter-tab')).map(el => ({
                folder: el.dataset.folder,
                name: el.dataset.chapter,
                type: el.dataset.type || 'chapter'
            }));
            tabs.splice(0, tabs.length, ...newOrder);
            localStorage.setItem('open_tabs', JSON.stringify(tabs));
            renderTabs(container, tabs, currentFolder, currentChapter, currentType);
        });
    });
}

function enableGroupDrag(container, tabs, currentFolder, currentChapter, currentType) {
    let dragging;
    container.querySelectorAll('.tab-group').forEach(group => {
        group.draggable = true;
        group.addEventListener('dragstart', () => { dragging = group; });
        group.addEventListener('dragover', e => {
            e.preventDefault();
            const rect = group.getBoundingClientRect();
            const next = (e.clientX - rect.left) > (rect.width / 2);
            container.insertBefore(dragging, next ? group.nextSibling : group);
        });
        group.addEventListener('drop', () => {
            const order = Array.from(container.querySelectorAll('.tab-group')).map(g => g.dataset.root);
            const newTabs = [];
            order.forEach(r => {
                tabs.filter(t => t.folder.split('/')[0] === r).forEach(t => newTabs.push(t));
            });
            tabs.splice(0, tabs.length, ...newTabs);
            localStorage.setItem('open_tabs', JSON.stringify(tabs));
            renderTabs(container, tabs, currentFolder, currentChapter, currentType);
        });
    });
}

function enableDragSort(ul) {
    let dragging;
    ul.querySelectorAll('li').forEach(li => {
        li.draggable = true;
        li.addEventListener('dragstart', () => {
            dragging = li;
        });
        li.addEventListener('dragover', e => {
            e.preventDefault();
            const rect = li.getBoundingClientRect();
            const next = (e.clientY - rect.top) > (rect.height / 2);
            ul.insertBefore(dragging, next ? li.nextSibling : li);
        });
        li.addEventListener('drop', () => {
            sendOrder(ul);
        });
    });
}

function sendOrder(ul) {
    const names = Array.from(ul.children).map(li => li.dataset.name);
    let url;
    if (ul.id === 'book_list') {
        url = '/books/reorder';
    } else {
        url = ul.dataset.reorderUrl;
    }
    fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ order: names, type: ul.dataset.type })
    });
}
function renderTabs(container, tabs, currentFolder, currentChapter, currentType) {
    container.innerHTML = '';
    const groups = {};
    tabs.forEach(t => {
        const root = t.folder.split('/')[0];
        if (!groups[root]) groups[root] = [];
        groups[root].push(t);
    });
    const orderedRoots = [];
    tabs.forEach(t => {
        const root = t.folder.split('/')[0];
        if (!orderedRoots.includes(root)) orderedRoots.push(root);
    });
    orderedRoots.forEach(root => {
        const wrapper = document.createElement('div');
        wrapper.className = 'tab-group';
        wrapper.dataset.root = root;
        const colorMap = window.bookColors || {};
        wrapper.style.backgroundColor = colorMap[root] || colorFromString(root);
        const title = document.createElement('div');
        title.className = 'tab-group-title';
        const span = document.createElement('span');
        span.textContent = root;
        const closeAll = document.createElement('button');
        closeAll.textContent = '\u00d7';
        closeAll.className = 'close-group';
        closeAll.addEventListener('click', e => {
            e.stopPropagation();
            tabs = tabs.filter(t => t.folder.split('/')[0] !== root);
            localStorage.setItem('open_tabs', JSON.stringify(tabs));
            if (!tabs.some(t => t.folder === currentFolder && t.name === currentChapter && t.type === currentType)) {
                if (tabs.length) {
                    const next = tabs[tabs.length - 1];
                    window.location.href = `/folder/${next.folder}/chapter/${next.name}`;
                } else {
                    window.location.href = '/';
                }
                return;
            }
            renderTabs(container, tabs, currentFolder, currentChapter, currentType);
        });
        title.appendChild(span);
        title.appendChild(closeAll);
        wrapper.appendChild(title);
        groups[root].forEach(t => {
            const tab = document.createElement('span');
            tab.className = 'chapter-tab' + (t.folder === currentFolder && t.name == currentChapter && t.type === currentType ? ' active' : '');
            tab.dataset.folder = t.folder;
            tab.dataset.chapter = t.name;
            tab.dataset.type = t.type;
            const link = document.createElement('a');
            link.textContent = t.name;
            link.href = `/folder/${t.folder}/chapter/${t.name}`;
            tab.appendChild(link);
            const close = document.createElement('button');
            close.textContent = '\u00d7';
            close.className = 'close-tab';
            close.addEventListener('click', e => {
                e.stopPropagation();
                e.preventDefault();
                const idx = tabs.findIndex(pt => pt.folder === t.folder && pt.name === t.name && pt.type === t.type);
                if (idx !== -1) tabs.splice(idx, 1);
                localStorage.setItem('open_tabs', JSON.stringify(tabs));
                if (t.folder === currentFolder && t.name === currentChapter && t.type === currentType) {
                    if (tabs.length) {
                        const next = tabs[tabs.length - 1];
                        window.location.href = `/folder/${next.folder}/chapter/${next.name}`;
                    } else {
                        window.location.href = `/folder/${t.folder}`;
                    }
                } else {
                    renderTabs(container, tabs, currentFolder, currentChapter, currentType);
                }
            });
            tab.appendChild(close);
            wrapper.appendChild(tab);
        });
        container.appendChild(wrapper);
    });
    enableTabDrag(container, tabs, currentFolder, currentChapter, currentType);
    enableGroupDrag(container, tabs, currentFolder, currentChapter, currentType);
}
