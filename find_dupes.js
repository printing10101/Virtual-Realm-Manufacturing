const fs = require('fs');
const content = fs.readFileSync('src/composables/useCommandPalette.ts', 'utf8');
const match = content.match(/const pinyinMap[^{]*\{([\s\S]*?)\n  \}/);
if (!match) { console.log('No match'); process.exit(0); }
const body = match[1];
const regex = /'([^']+)'\s*:/g;
const seen = {};
const dupes = [];
let m;
while ((m = regex.exec(body)) !== null) {
  const key = m[1];
  const lineNum = body.substring(0, m.index).split('\n').length + 250;
  if (seen[key]) {
    dupes.push({ key, firstLine: seen[key], dupLine: lineNum });
  } else {
    seen[key] = lineNum;
  }
}
console.log('Duplicates found:', dupes.length);
dupes.forEach(d => console.log(`  '${d.key}' first at line ${d.firstLine}, dup at line ${d.dupLine}`));
