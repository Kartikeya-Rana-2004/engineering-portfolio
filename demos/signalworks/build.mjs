import {readFileSync,writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {svg} from './geometry.mjs';
const here=fileURLToPath(new URL('.',import.meta.url));
const template=readFileSync(here+'template.html','utf8');
writeFileSync(here+'index.html',template.replace('<!-- MACHINE -->',svg()));
writeFileSync(here+'traces.json',readFileSync(here+'../../evidence/signalworks-traces.json'));
console.log('Built SignalWorks static SVG page and recorded traces.');
