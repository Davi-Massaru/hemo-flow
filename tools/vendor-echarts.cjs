// Copy the pinned distribution: no CDN, bundler or runtime Node dependency.
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const target = path.join(root, 'web/static/vendor/echarts');
fs.mkdirSync(target, {recursive: true});
for (const file of ['dist/echarts.min.js', 'LICENSE', 'NOTICE']) {
  fs.copyFileSync(path.join(root, 'node_modules/echarts', file), path.join(target, path.basename(file)));
}
console.log('Vendored Apache ECharts 5.6.0');
