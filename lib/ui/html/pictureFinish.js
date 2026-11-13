// Finishes pictures of the viewport Fusion saved larger than they are, which its Python can't: cut to the model,
// graded, fitted in the picture with a margin and scaled down, see lib/ui/pictureJobs.py. A page gives it the jobs
// that come with its updates, the answer goes back through the bridge
const pictureFinish = (() => {
    function loadImage(source) {
        return new Promise((resolve, reject) => {
            const image = new Image();
            image.onload = () => resolve(image);
            image.onerror = () => reject(new Error('the rendered picture could not be read'));
            image.src = source;
        });
    }

    function canvas(width, height) {
        const result = document.createElement('canvas');
        result.width = Math.max(1, Math.round(width));
        result.height = Math.max(1, Math.round(height));
        return result;
    }

    function pixelsOf(source) {
        const context = source.getContext('2d', { willReadFrequently: true });
        return context.getImageData(0, 0, source.width, source.height).data;
    }

    // the box of what differs from the background, transparent or the color of the top left corner
    function contentBounds(pixels, width, height, transparent) {
        const [r0, g0, b0] = pixels;
        const isContent = transparent
            ? (i) => pixels[i + 3] > 8
            : (i) => Math.abs(pixels[i] - r0) > 12 || Math.abs(pixels[i + 1] - g0) > 12 || Math.abs(pixels[i + 2] - b0) > 12;
        let [left, top, right, bottom] = [width, height, -1, -1];
        for (let y = 0; y < height; y++) {
            for (let x = 0; x < width; x++) {
                if (isContent((y * width + x) * 4)) {
                    left = Math.min(left, x);
                    right = Math.max(right, x);
                    top = Math.min(top, y);
                    bottom = Math.max(bottom, y);
                }
            }
        }
        return right < 0 ? null : { left, top, width: right - left + 1, height: bottom - top + 1 };
    }

    // halving at most each time keeps every pixel in the average, one big step would skip most of them
    function scaled(source, width, height) {
        let current = source;
        while (current.width / 2 >= width && current.height / 2 >= height) {
            const half = canvas(current.width / 2, current.height / 2);
            const context = half.getContext('2d');
            context.imageSmoothingQuality = 'high';
            context.drawImage(current, 0, 0, half.width, half.height);
            current = half;
        }
        const result = canvas(width, height);
        const context = result.getContext('2d');
        context.imageSmoothingQuality = 'high';
        context.drawImage(current, 0, 0, result.width, result.height);
        return result;
    }

    // brighter by stops as a camera's exposure, in linear light so the darkest stays dark, clipped at white, then the
    // colors deepened by saturation away from their grey. An opaque background's color stays, the picture's padding is
    // filled with it
    function grade(source, stops, saturation, background) {
        const context = source.getContext('2d', { willReadFrequently: true });
        const image = context.getImageData(0, 0, source.width, source.height);
        const factor = 2 ** stops;
        const table = new Uint8ClampedArray(256);
        for (let value = 0; value < 256; value++) {
            const channel = value / 255;
            const linear = (channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4) * factor;
            const encoded = linear <= 0.0031308 ? linear * 12.92 : 1.055 * linear ** (1 / 2.4) - 0.055;
            table[value] = Math.round(encoded * 255);
        }
        const pixels = image.data;
        for (let i = 0; i < pixels.length; i += 4) {
            if (background && Math.abs(pixels[i] - background[0]) <= 12 && Math.abs(pixels[i + 1] - background[1]) <= 12
                && Math.abs(pixels[i + 2] - background[2]) <= 12) {
                continue;
            }
            const [r, g, b] = [table[pixels[i]], table[pixels[i + 1]], table[pixels[i + 2]]];
            const grey = 0.2126 * r + 0.7152 * g + 0.0722 * b;
            pixels[i] = grey + saturation * (r - grey);
            pixels[i + 1] = grey + saturation * (g - grey);
            pixels[i + 2] = grey + saturation * (b - grey);
        }
        context.putImageData(image, 0, 0);
    }

    // the render cut to the model and fitted in the picture with a margin, a smaller picture of a larger render
    // smooths the edges
    async function picture(job) {
        const image = await loadImage(job.image);
        const full = canvas(image.width, image.height);
        full.getContext('2d', { willReadFrequently: true }).drawImage(image, 0, 0);
        // the background of an opaque render is measured before, it stays its own color
        const pixels = pixelsOf(full);
        const saturation = job.saturation === undefined ? 1 : job.saturation;
        if (job.exposure || saturation !== 1) {
            grade(full, job.exposure || 0, saturation, job.transparent ? null : [pixels[0], pixels[1], pixels[2]]);
        }
        const bounds = contentBounds(pixels, full.width, full.height, job.transparent);
        if (!bounds) {
            throw new Error('the render is empty');
        }
        const touchesEdge = bounds.left <= 1 || bounds.top <= 1
            || bounds.left + bounds.width >= full.width - 1 || bounds.top + bounds.height >= full.height - 1;
        const cropped = canvas(bounds.width, bounds.height);
        cropped.getContext('2d').drawImage(full, bounds.left, bounds.top, bounds.width, bounds.height, 0, 0, bounds.width, bounds.height);

        const scale = Math.min(job.width * (1 - 2 * job.margin) / bounds.width, job.height * (1 - 2 * job.margin) / bounds.height);
        const model = scaled(cropped, bounds.width * scale, bounds.height * scale);
        const result = canvas(job.width, job.height);
        const output = result.getContext('2d');
        if (!job.transparent) {
            output.fillStyle = `rgb(${pixels[0]}, ${pixels[1]}, ${pixels[2]})`;
            output.fillRect(0, 0, result.width, result.height);
        }
        output.drawImage(model, Math.round((result.width - model.width) / 2), Math.round((result.height - model.height) / 2));
        return { png: result.toDataURL('image/png'), touchesEdge: touchesEdge };
    }

    async function process(job) {
        try {
            const result = await picture(job);
            fusionBridge.send('picture', { id: job.id, ...result });
        } catch (err) {
            fusionBridge.send('picture', { id: job.id, error: String(err.message || err) });
        }
    }

    return { process };
})();
