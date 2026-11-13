// Draws a dialog recorded by dialogRecorder.py the way Fusion shows it, and frames the part of it a shot takes,
// see screenshots.py. Pages of browser inputs are the add-in's own, they get the dialog's answer to their ready message
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
};

// pages left to answer, the shot waits for them
const pagesLoading = [];

function row(input, ...classNames) {
    const node = element('div', ['row', ...classNames].join(' '));
    node.dataset.inputId = input.id;
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
                fusionSendData: (action) => {
                    if (action !== 'ready') {
                        return 'OK';
                    }
                    setTimeout(() => frame.contentDocument.fonts.ready.then(resolve), 0);
                    return input.answer;
                },
            };
        });
    }));
    return frame;
}

function drawInput(input, nested) {
    switch (input.type) {
    case 'group':
        return group(input, nested);
    case 'value':
    case 'string':
        return labelled(input, textField(input.text));
    case 'spinner': {
        const spin = element('div', 'spin');
        const up = element('span');
        const down = element('span');
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
        return labelled(input, field);
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

function group(input, nested) {
    const node = element('section', 'group ' + (nested ? 'nested' : 'top'));
    node.dataset.inputId = input.id;
    const header = element('div', 'group-header');
    // a shot can take the header alone
    header.dataset.inputId = `${input.id}:header`;
    header.append(input.expanded ? ICONS.expanded() : ICONS.collapsed(), element('span', '', input.name));
    node.append(header);
    if (input.expanded) {
        const children = element('div', 'children');
        children.append(...input.children.map((child) => drawInput(child, true)));
        node.append(children);
    }
    return node;
}

function drawDialog(model) {
    const dialog = element('div', 'dialog');
    dialog.style.width = `${model.width}px`;

    const titleBar = element('div', 'title-bar');
    titleBar.append(ICONS.minimize(), element('span', 'title', model.title), ICONS.dock());

    const body = element('div', 'body');
    const content = element('div', 'content');
    content.append(...model.inputs.map((input) => drawInput(input, false)));
    body.append(content);

    const footer = element('div', 'footer');
    footer.append(element('button', 'button', model.okText), element('button', 'button', model.cancelText));

    dialog.append(titleBar, body, footer);
    return dialog;
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

// spans of the inputs a shot shows, by id, from the top of the dialog
function regionOf(dialog, ids) {
    const top = dialog.getBoundingClientRect().top;
    const boxes = ids.map((id) => {
        const node = dialog.querySelector(`[data-input-id="${id}"]`);
        if (!node) {
            throw new Error(`The dialog doesn't show ${id}, is it hidden or in a collapsed group?`);
        }
        return node.getBoundingClientRect();
    });
    return {
        top: Math.min(...boxes.map((box) => box.top)) - top,
        bottom: Math.max(...boxes.map((box) => box.bottom)) - top,
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

// draws the dialog, resolves once its pages have drawn and the size of what to capture is known
async function renderShot(model, shot) {
    const stage = document.getElementById('stage');
    const dialog = drawDialog(model);
    const frame = element('div', 'frame');
    const viewport = element('div', 'viewport');
    const capture = element('div', 'shot');
    viewport.append(dialog);
    frame.append(viewport);
    capture.append(frame);
    stage.append(capture);

    await document.fonts.ready;
    await Promise.all(pagesLoading);
    // a frame for the pages to lay out with their data
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));

    if (shot.height) {
        limitHeight(dialog, shot.height);
    }
    if (shot.inputs && shot.inputs.length > 0) {
        const margin = shot.margin ?? 10;
        const region = regionOf(dialog, shot.inputs);
        const top = Math.max(0, region.top - margin);
        const bottom = Math.min(dialog.offsetHeight, region.bottom + margin);
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
            const lower = bottom < dialog.offsetHeight ? cutEdge(width, height, -1, edge(next)) : [[0, height], [width, height]];
            const points = [...upper, ...lower.reverse()];
            viewport.style.clipPath = `polygon(${points.map(([x, y]) => `${x.toFixed(1)}px ${y.toFixed(1)}px`).join(', ')})`;
        }
    }
    return true;
}
