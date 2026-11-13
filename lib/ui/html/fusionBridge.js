// Talks to the dialog a page is shown in, see lib/ui/browserPages.py. Data comes with the dialog's font, which is
// loaded here, pages only get their own data
const fusionBridge = (() => {
    let redraw = () => {};
    // the font comes from the Fusion install, its path changes with every update
    let loadedFont = '';

    function loadFont(fontUrl) {
        if (!fontUrl || fontUrl === loadedFont) {
            return;
        }
        loadedFont = fontUrl;
        const style = document.createElement('style');
        style.textContent = `@font-face { font-family: "Fusion Artifakt Element"; src: url("${fontUrl}"); }`;
        document.head.appendChild(style);
        // text is laid out again with the font
        document.fonts.ready.then(() => redraw());
    }

    // the page's data, null when the dialog had nothing for it
    function receive(json) {
        if (!json || json === 'OK') {
            return null;
        }
        const message = JSON.parse(json);
        loadFont(message.fontUrl);
        return message.data;
    }

    function isReady() {
        return Boolean(window.adsk && adsk.fusionSendData);
    }

    // the dialog's answer, older Fusion versions return it directly
    function send(action, data) {
        if (!isReady()) {
            return Promise.resolve(null);
        }
        return Promise.resolve(adsk.fusionSendData(action, JSON.stringify(data === undefined ? null : data))).then(receive);
    }

    // update gets the data the dialog sends, redraw is for a new font or size, the last data stays with the page
    function connect(update, onRedraw) {
        redraw = onRedraw || (() => {});
        window.addEventListener('resize', () => redraw());
        window.fusionJavaScriptHandler = {
            handle: function (action, payload) {
                if (action === 'update') {
                    const data = receive(payload);
                    if (data !== null) {
                        update(data);
                    }
                }
                return 'OK';
            },
        };
        // the bridge is injected after the page starts loading
        const requestInitialData = () => {
            if (!isReady()) {
                setTimeout(requestInitialData, 100);
                return;
            }
            send('ready').then((data) => {
                if (data !== null) {
                    update(data);
                }
            });
        };
        requestInitialData();
    }

    return { send: send, connect: connect };
})();
