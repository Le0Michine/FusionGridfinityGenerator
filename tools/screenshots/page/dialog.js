// Draws a dialog recorded by dialogRecorder.py the way Fusion shows it, and frames the part of it a shot takes,
// see screenshots.py. Pages of browser inputs are the add-in's own, they talk to the dialog through fusionSend, which
// screenshots.py provides. An animation changes the dialog in place, see animation.py, pages keep their state
const SVG_NS = 'http://www.w3.org/2000/svg';

function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) {
        node.className = className;
    }
    if (text !== undefined) {
        node.textContent = text;
    }
    return node;
}

function icon(width, height, markup) {
    const svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('width', width);
    svg.setAttribute('height', height);
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.innerHTML = markup;
    return svg;
}

const ICONS = {
    expanded: () => icon(9, 9, '<path d="M0.5 2 h8 L4.5 7.5 z"/>'),
    collapsed: () => icon(9, 9, '<path d="M2 0.5 v8 L7.5 4.5 z"/>'),
    dropdown: () => icon(9, 9, '<path d="M1 3 h7 L4.5 7 z"/>'),
    spinUp: () => icon(7, 4, '<path d="M0 4 h7 L3.5 0 z"/>'),
    spinDown: () => icon(7, 4, '<path d="M0 0 h7 L3.5 4 z"/>'),
    check: () => icon(11, 11, '<path d="M2 5.8 L4.5 8.2 L9.2 2.8"/>'),
    minimize: () => icon(9, 9, '<path d="M1 4.5 h7"/>'),
    dock: () => icon(10, 9, '<path d="M1 1.5 L4 4.5 L1 7.5 M5.5 1.5 L8.5 4.5 L5.5 7.5"/>'),
    // the system arrow, its tip at 0, 0
    cursor: () => icon(14, 21, '<path d="M1 1 V16.5 L4.8 12.9 L7.6 19.2 L10.2 18.1 L7.5 11.9 H12.6 Z"/>'),
};

// pages left to answer, the shot waits for them
const pagesLoading = [];

function row(input, ...classNames) {
    const node = element('div', ['row', ...classNames].join(' '));
    node.dataset.inputId = input.id;
    node.hidden = !input.visible;
    if (!input.enabled) {
        node.classList.add('disabled');
    }
    return node;
}

function labelled(input, field, ...classNames) {
    const node = row(input, ...classNames);
    node.append(element('div', 'label', input.name), field);
    return node;
}

function textField(text, ...extras) {
    const field = element('div', 'field');
    field.append(element('span', 'text', text), ...extras);
    return field;
}

function checkbox(checked) {
    const box = element('div', 'checkbox' + (checked ? ' checked' : ''));
    if (checked) {
        box.append(ICONS.check());
    }
    return box;
}

function page(input) {
    const frame = element('iframe');
    frame.style.height = `${input.height}px`;
    frame.src = input.url;
    pagesLoading.push(new Promise((resolve) => {
        frame.addEventListener('load', () => {
            // what Fusion injects, the page asks for its data once it is there, see lib/ui/html/fusionBridge.js
            frame.contentWindow.adsk = {
                fusionSendData: (action, data) => {
                    const answer = window.fusionSend(input.id, action, data);
                    if (action === 'ready') {
                        answer.then(() => setTimeout(() => frame.contentDocument.fonts.ready.then(resolve), 0));
                    }
                    return answer;
                },
            };
        }, { once: true });
    }));
    return frame;
}

function drawInput(input) {
    switch (input.type) {
    case 'group':
        return group(input);
    case 'value':
    case 'string':
        return labelled(input, textField(input.text));
    case 'spinner': {
        const spin = element('div', 'spin');
        const up = element('span', 'up');
        const down = element('span', 'down');
        up.append(ICONS.spinUp());
        down.append(ICONS.spinDown());
        spin.append(up, down);
        return labelled(input, textField(input.text, spin));
    }
    case 'dropdown': {
        const field = textField(input.text, ICONS.dropdown());
        if (input.icon) {
            const image = element('img');
            image.src = input.icon;
            field.prepend(image);
        }
        const node = labelled(input, field);
        // for when the dropdown is opened, see openDropdown
        node.dataset.items = JSON.stringify(input.items || []);
        return node;
    }
    case 'checkbox':
        return labelled(input, checkbox(input.checked));
    case 'button': {
        const button = element('button', 'button', input.name);
        if (input.fullWidth) {
            const node = row(input, 'full');
            node.append(button);
            return node;
        }
        return labelled(input, button);
    }
    case 'textbox': {
        const box = element('div', 'text-box');
        box.innerHTML = input.html;
        box.style.minHeight = `${input.rows * 17 + 8}px`;
        return labelled(input, box, 'text');
    }
    case 'table': {
        // tables without a grid show their cells across the dialog, without the label
        const node = row(input, 'full');
        const table = element('div', 'table');
        const ratios = input.columnRatio.split(':').map(Number);
        table.style.gridTemplateColumns = ratios.map((ratio) => `${ratio}fr`).join(' ');
        for (const cells of input.rows) {
            for (const cell of cells) {
                table.append(element('div', 'cell', cell ? (cell.text ?? cell.name) : ''));
            }
        }
        node.append(table);
        return node;
    }
    case 'browser':
        if (input.fullWidth) {
            const node = row(input, 'full');
            node.append(page(input));
            return node;
        }
        return labelled(input, page(input));
    default:
        throw new Error(`Unknown input ${input.id} of type ${input.type}`);
    }
}

function groupHeader(input) {
    const header = element('div', 'group-header');
    // a shot can take the header alone
    header.dataset.inputId = `${input.id}:header`;
    header.append(input.expanded ? ICONS.expanded() : ICONS.collapsed(), element('span', '', input.name));
    return header;
}

// children of collapsed groups are drawn hidden, so their pages are there when the group opens
function group(input) {
    const node = element('section', 'group');
    node.dataset.inputId = input.id;
    node.hidden = !input.visible;
    const children = element('div', 'children');
    children.hidden = !input.expanded;
    children.append(...input.children.map((child) => {
        const drawn = drawInput(child);
        if (child.type === 'group') {
            drawn.classList.add('nested');
        }
        return drawn;
    }));
    node.append(groupHeader(input), children);
    return node;
}

function drawDialog(model) {
    const dialog = element('div', 'dialog');
    dialog.style.width = `${model.width}px`;

    const titleBar = element('div', 'title-bar');
    titleBar.append(ICONS.minimize(), element('span', 'title', model.title), ICONS.dock());

    const body = element('div', 'body');
    const content = element('div', 'content');
    content.append(...model.inputs.map((input) => {
        const drawn = drawInput(input);
        if (input.type === 'group') {
            drawn.classList.add('top');
        }
        return drawn;
    }));
    body.append(content);

    const footer = element('div', 'footer');
    const ok = element('button', 'button ok', model.okText);
    ok.disabled = !model.okEnabled;
    footer.append(ok, element('button', 'button', model.cancelText));

    dialog.append(titleBar, body, footer);
    return dialog;
}

function dialogElement() {
    return document.querySelector('.dialog');
}

function inputNode(id) {
    return dialogElement().querySelector(`[data-input-id="${CSS.escape(id)}"]`);
}

function* allInputs(inputs) {
    for (const input of inputs) {
        yield input;
        if (input.type === 'group') {
            yield* allInputs(input.children);
        }
    }
}

// the dialog after a change, pages stay where they are, moving them would load them again
function updateDialog(model) {
    for (const input of allInputs(model.inputs)) {
        const node = inputNode(input.id);
        if (!node) {
            continue;
        }
        if (input.type === 'group') {
            node.hidden = !input.visible;
            node.querySelector(':scope > .group-header').replaceWith(groupHeader(input));
            node.querySelector(':scope > .children').hidden = !input.expanded;
        } else if (input.type === 'browser') {
            node.hidden = !input.visible;
            node.classList.toggle('disabled', !input.enabled);
        } else {
            node.replaceWith(drawInput(input));
        }
    }
    dialogElement().querySelector('.footer .ok').disabled = !model.okEnabled;
}

// what the dialog sends a page, as Fusion calls it
function sendToPage(id, action, data) {
    inputNode(id).querySelector('iframe').contentWindow.fusionJavaScriptHandler.handle(action, data);
}

function nextFrame() {
    return new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
}

// a point of a part of the dialog, from the dialog's corner and from the window's for the mouse
function targetPoint(target) {
    const dialogBox = dialogElement().getBoundingClientRect();
    const [fractionX, fractionY] = target.at || [0.5, 0.5];
    let box;
    if (target.page) {
        const frame = inputNode(target.page).querySelector('iframe');
        const frameBox = frame.getBoundingClientRect();
        const node = frame.contentDocument.querySelector(target.selector || 'body');
        if (!node) {
            throw new Error(`Page ${target.page} has nothing matching ${target.selector}`);
        }
        const nodeBox = node.getBoundingClientRect();
        box = { left: frameBox.left + nodeBox.left, top: frameBox.top + nodeBox.top, width: nodeBox.width, height: nodeBox.height };
    } else if (target.item !== undefined) {
        const item = [...document.querySelectorAll('.dropdown-list .item')].find((node) => node.dataset.name === target.item);
        if (!item) {
            throw new Error(`The open dropdown has no item ${target.item}`);
        }
        box = item.getBoundingClientRect();
    } else {
        const node = inputNode(target.input);
        if (!node || node.offsetParent === null) {
            throw new Error(`The dialog doesn't show ${target.input}, is it hidden or in a collapsed group?`);
        }
        const parts = target.part ? [`.${target.part}`] : [':scope > .group-header span', '.checkbox', '.field', '.button', 'iframe'];
        box = (parts.map((part) => node.querySelector(part)).find(Boolean) || node).getBoundingClientRect();
    }
    const x = box.left + box.width * fractionX;
    const y = box.top + box.height * fractionY;
    return { x: x - dialogBox.left, y: y - dialogBox.top, clientX: x, clientY: y };
}

function moveCursor(x, y, pressed) {
    let cursor = document.querySelector('.cursor');
    if (!cursor) {
        cursor = element('div', 'cursor');
        cursor.append(element('div', 'press'), ICONS.cursor());
        dialogElement().append(cursor);
    }
    cursor.style.left = `${x}px`;
    cursor.style.top = `${y}px`;
    cursor.classList.toggle('pressed', Boolean(pressed));
}

function hideCursor() {
    document.querySelector('.cursor')?.remove();
}

// a dropdown open below its field, the item under the cursor lit
function openDropdown(id, highlighted) {
    closeDropdown();
    const field = inputNode(id).querySelector('.field');
    const dialogBox = dialogElement().getBoundingClientRect();
    const fieldBox = field.getBoundingClientRect();
    const list = element('div', 'dropdown-list');
    list.style.left = `${fieldBox.left - dialogBox.left}px`;
    list.style.top = `${fieldBox.bottom - dialogBox.top}px`;
    list.style.width = `${fieldBox.width}px`;
    const model = JSON.parse(field.closest('.row').dataset.items || '[]');
    for (const item of model) {
        if (item.separator) {
            list.append(element('div', 'separator'));
            continue;
        }
        const node = element('div', 'item');
        node.dataset.name = item.name;
        if (item.icon) {
            const image = element('img');
            image.src = item.icon;
            node.append(image);
        }
        node.append(element('span', '', item.name));
        list.append(node);
    }
    dialogElement().append(list);
    highlightItem(highlighted);
}

function highlightItem(name) {
    for (const item of document.querySelectorAll('.dropdown-list .item')) {
        item.classList.toggle('lit', item.dataset.name === name);
    }
}

function closeDropdown() {
    document.querySelector('.dropdown-list')?.remove();
}

// a field being typed in, all of its text selected first as a click in Fusion does
function editField(id, text, selected) {
    const node = inputNode(id);
    node.querySelector('.field').classList.add('editing');
    const span = node.querySelector('.field .text');
    span.textContent = text;
    span.classList.toggle('selected', Boolean(selected));
}

// the same torn edge for the same shot
function random(seedText) {
    let seed = 2166136261;
    for (const char of seedText) {
        seed = Math.imul(seed ^ char.charCodeAt(0), 16777619);
    }
    return () => {
        seed = Math.imul(seed ^ (seed >>> 15), 2246822507);
        seed = Math.imul(seed ^ (seed >>> 13), 3266489909);
        return ((seed ^= seed >>> 16) >>> 0) / 4294967296;
    };
}

// the shape of a cut edge, the depth into the paper at x
const EDGES = {
    // even teeth, as docs usually cut a screenshot
    zigzag: () => {
        const tooth = 32;
        const depth = 8;
        return (x) => {
            const along = (x % tooth) / tooth;
            return depth * (along < 0.5 ? along * 2 : 2 - along * 2);
        };
    },
    wave: () => (x) => 3 * (1 - Math.cos(x / 28 * 2 * Math.PI)) / 2 + 0.5,
    // torn paper, long uneven strokes
    rough: (next) => {
        const points = [];
        for (let x = 0; x < 4000; x += 14 + next() * 22) {
            points.push([x, 1 + next() * 5]);
        }
        return (x) => {
            const index = points.findIndex(([pointX]) => pointX > x);
            const [[x0, y0], [x1, y1]] = [points[index - 1], points[index]];
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0);
        };
    },
};

// a cut edge across the width at y, the paper goes the way of inwards
function cutEdge(width, y, inwards, depthAt) {
    const points = [];
    for (let x = 0; x < width; x += 1) {
        points.push([x, y + inwards * depthAt(x)]);
    }
    points.push([width, y + inwards * depthAt(width)]);
    return points;
}

// the span of the inputs a shot shows, by id, from the top of the dialog, an open dropdown counts too
function measureRegion(ids) {
    const dialog = dialogElement();
    const top = dialog.getBoundingClientRect().top;
    if (ids.length === 0) {
        return { top: 0, bottom: dialog.offsetHeight, dialogHeight: dialog.offsetHeight };
    }
    const boxes = ids.map((id) => {
        const node = inputNode(id);
        if (!node) {
            throw new Error(`The dialog has no ${id}`);
        }
        return node;
    }).filter((node) => node.offsetParent !== null).map((node) => node.getBoundingClientRect());
    const list = document.querySelector('.dropdown-list');
    if (list) {
        boxes.push(list.getBoundingClientRect());
    }
    if (boxes.length === 0) {
        return null;
    }
    return {
        top: Math.min(...boxes.map((box) => box.top)) - top,
        bottom: Math.max(...boxes.map((box) => box.bottom)) - top,
        dialogHeight: dialog.offsetHeight,
    };
}

function limitHeight(dialog, height) {
    const body = dialog.querySelector('.body');
    const content = body.firstChild;
    const bodyHeight = height - (dialog.offsetHeight - body.offsetHeight);
    if (content.offsetHeight <= bodyHeight) {
        return;
    }
    body.style.height = `${bodyHeight}px`;
    const scrollbar = element('div', 'scrollbar');
    const thumb = element('div', 'thumb');
    thumb.style.top = '0';
    thumb.style.height = `${Math.max(20, bodyHeight * bodyHeight / content.offsetHeight)}px`;
    scrollbar.append(thumb);
    body.append(scrollbar);
}

// draws the dialog, resolves once its pages have drawn
async function renderDialog(model, shot) {
    const dialog = drawDialog(model);
    const frame = element('div', 'frame');
    const viewport = element('div', 'viewport');
    const capture = element('div', 'shot');
    if (shot.background) {
        capture.style.background = shot.background;
    }
    viewport.append(dialog);
    frame.append(viewport);
    capture.append(frame);
    document.getElementById('stage').append(capture);

    await document.fonts.ready;
    await Promise.all(pagesLoading);
    // a frame for the pages to lay out with their data
    await nextFrame();
    if (shot.height) {
        limitHeight(dialog, shot.height);
    }
}

// cuts out the part of the dialog a shot shows, a region measured beforehand keeps it still through an animation
function frameShot(shot, region) {
    const dialog = dialogElement();
    const viewport = document.querySelector('.viewport');
    if (!shot.inputs || shot.inputs.length === 0) {
        // the whole dialog, as tall as it gets through an animation
        if (region) {
            viewport.style.height = `${region.dialogHeight}px`;
        }
        return;
    }
    region = region || measureRegion(shot.inputs);
    if (!region) {
        throw new Error(`The dialog shows none of ${shot.inputs.join(', ')}`);
    }
    const margin = shot.margin ?? 10;
    const dialogHeight = Math.max(region.dialogHeight, dialog.offsetHeight);
    const top = Math.max(0, region.top - margin);
    const bottom = Math.min(dialogHeight, region.bottom + margin);
    const width = dialog.offsetWidth;
    const height = bottom - top;
    viewport.style.height = `${height}px`;
    dialog.style.marginTop = `${-top}px`;
    if (shot.torn !== false) {
        const edge = EDGES[shot.edge || 'zigzag'];
        if (!edge) {
            throw new Error(`Unknown edge ${shot.edge}, one of ${Object.keys(EDGES).join(', ')}`);
        }
        const next = random(shot.name || '');
        const upper = top > 0 ? cutEdge(width, 0, 1, edge(next)) : [[0, 0], [width, 0]];
        const lower = bottom < dialogHeight ? cutEdge(width, height, -1, edge(next)) : [[0, height], [width, height]];
        const points = [...upper, ...lower.reverse()];
        viewport.style.clipPath = `polygon(${points.map(([x, y]) => `${x.toFixed(1)}px ${y.toFixed(1)}px`).join(', ')})`;
    }
}
