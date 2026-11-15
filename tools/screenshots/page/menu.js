// Draws Fusion's right-click menu with the items of a shot, see screenshots.py. Uses the cut edges of dialog.js

// Fusion's own icons aren't ours to ship, the few its items need are simple shapes
const MENU_ICONS = {
    eye: '<path d="M1 8 Q8 1.5 15 8 Q8 14.5 1 8 z" style="fill: var(--menu-shortcut)"/><circle cx="8" cy="8" r="3.2" style="fill: var(--menu)"/><circle cx="8" cy="8" r="1.6" style="fill: var(--menu-shortcut)"/>',
};

function menuItem(item) {
    if (item.separator) {
        return element('div', 'separator');
    }
    const row = element('div', item.hover ? 'item hover' : 'item');
    if (item.icon && MENU_ICONS[item.icon]) {
        const svg = icon(16, 16, MENU_ICONS[item.icon]);
        svg.classList.add('icon');
        row.append(svg);
    } else if (item.icon) {
        // a file of the add-in, by its path from the add-in folder
        const image = element('img', 'icon');
        image.src = `/${item.icon}`;
        row.append(image);
    } else {
        row.append(element('span', 'icon'));
    }
    row.append(element('span', 'label', item.label));
    if (item.shortcut) {
        row.append(element('span', 'shortcut', item.shortcut));
    }
    return row;
}

// the viewport of Fusion with a model picture and the menu opened on it, the menu can start above the viewport's top
function drawScene(scene, menu) {
    const view = element('div', 'scene');
    view.style.width = `${scene.width}px`;
    view.style.height = `${scene.height}px`;
    const model = element('img', 'model');
    model.src = `/${scene.model.picture}`;
    model.style.left = `${scene.model.x}px`;
    model.style.top = `${scene.model.y}px`;
    model.style.width = `${scene.model.width}px`;
    menu.style.left = `${scene.menuAt[0]}px`;
    menu.style.top = `${scene.menuAt[1]}px`;
    view.append(model, menu);
    return view;
}

// the pointer at a share of the width and height of a part of the menu
function moveSceneCursor(view, target, [fx, fy]) {
    const box = target.getBoundingClientRect();
    const viewBox = view.getBoundingClientRect();
    const cursor = element('div', 'cursor');
    cursor.append(ICONS.cursor());
    cursor.style.left = `${box.left - viewBox.left + box.width * fx}px`;
    cursor.style.top = `${box.top - viewBox.top + box.height * fy}px`;
    view.append(cursor);
}

// draws the menu, resolves once its icons and font have loaded
async function renderMenu(shot) {
    const menu = element('div', 'menu');
    for (const item of shot.menu.items) {
        menu.append(menuItem(item));
    }
    if (shot.menu.width) {
        menu.style.width = `${shot.menu.width}px`;
    }
    const frame = element('div', 'frame');
    const viewport = element('div', 'viewport');
    const capture = element('div', 'shot');
    if (shot.background) {
        capture.style.background = shot.background;
    }
    const scene = shot.menu.scene;
    if (scene) {
        viewport.append(drawScene(scene, menu));
    } else {
        viewport.append(menu);
    }
    frame.append(viewport);
    capture.append(frame);
    document.getElementById('stage').append(capture);

    await document.fonts.ready;
    await Promise.all([...viewport.querySelectorAll('img')].map((image) => image.decode()));
    const hovered = menu.querySelector('.hover');
    if (scene && hovered) {
        // the pointer rests on the item, a little into its label
        const label = hovered.querySelector('.label');
        moveSceneCursor(viewport.querySelector('.scene'), label, scene.cursorAt || [0.35, 0.6]);
    }
    // the menu goes on above its first item, the top is torn
    if (shot.menu.cutTop) {
        const edge = EDGES[shot.edge || 'zigzag'](random(shot.name || ''));
        menu.style.borderTop = 'none';
        menu.style.paddingTop = '10px';
        const width = menu.offsetWidth;
        const height = menu.offsetHeight;
        const points = [...cutEdge(width, 0, 1, edge), [width, height], [0, height]];
        viewport.style.clipPath = `polygon(${points.map(([x, y]) => `${x.toFixed(1)}px ${y.toFixed(1)}px`).join(', ')})`;
    }
    await nextFrame();
}
