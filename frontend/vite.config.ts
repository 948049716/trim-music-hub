import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import path from 'path';
import fs from 'node:fs';
import https from 'node:https';

const fnosCoverRoot = process.env.FNOS_COVER_DIR || (fs.existsSync('/app/cover') ? '/app/cover' : '/var/apps/trim.music/meta/cover');

function fnosCoverDevPlugin() {
  return {
    name: 'fnos-cover-dev-server',
    configureServer(server: any) {
      server.middlewares.use((req: any, res: any, next: () => void) => {
        const url = new URL(req.url || '/', 'http://localhost');
        const match = url.pathname.match(/^\/api\/covers\/(playlist|track|album|artist)\/([a-f0-9]{32})$/i);
        if (!match || req.method !== 'GET') return next();

        // 本地环境若无 NAS 封面目录，直接放行交由代理向 NAS 后端请求
        if (!fs.existsSync(fnosCoverRoot)) return next();

        const type = match[1].toLowerCase();
        const guid = match[2].toLowerCase();
        const requestedSize = url.searchParams.get('size') || '160';
        const size = new Set(['120', '160', '400', '600', '800']).has(requestedSize) ? requestedSize : '160';

        const typesToSearch = [type, 'album', 'track', 'artist', 'playlist']
          .filter((item, index, list) => list.indexOf(item) === index);
        let coverPath: string | undefined;

        for (const currentType of typesToSearch) {
          const typeRoot = path.resolve(fnosCoverRoot, currentType);
          const shardRoot = path.resolve(typeRoot, guid.slice(0, 2));
          const candidates = [
            path.resolve(shardRoot, `${guid}_w${size}.jpg`),
            path.resolve(shardRoot, `${guid}_w400.jpg`),
            path.resolve(shardRoot, `${guid}_w160.jpg`),
            path.resolve(shardRoot, `${guid}_w120.jpg`),
            path.resolve(shardRoot, `${guid}_w600.jpg`),
            path.resolve(shardRoot, `${guid}_w800.jpg`),
            path.resolve(shardRoot, guid)
          ];
          coverPath = candidates.find(candidate => candidate.startsWith(`${typeRoot}${path.sep}`) && fs.existsSync(candidate) && fs.statSync(candidate).isFile());
          if (coverPath) break;
        }

        // 本地未命中的封面放行给代理后端尝试回退
        if (!coverPath) return next();

        const fd = fs.openSync(coverPath, 'r');
        const header = Buffer.alloc(12);
        const bytesRead = fs.readSync(fd, header, 0, header.length, 0);
        fs.closeSync(fd);
        const signature = header.subarray(0, bytesRead);
        let contentType = 'application/octet-stream';
        if (signature[0] === 0xff && signature[1] === 0xd8 && signature[2] === 0xff) contentType = 'image/jpeg';
        else if (signature.subarray(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]))) contentType = 'image/png';
        else if (signature.subarray(0, 4).toString('ascii') === 'RIFF' && signature.subarray(8, 12).toString('ascii') === 'WEBP') contentType = 'image/webp';
        else if (signature.subarray(0, 3).toString('ascii') === 'GIF') contentType = 'image/gif';

        res.setHeader('Content-Type', contentType);
        res.setHeader('Cache-Control', 'public, max-age=86400, immutable');
        res.setHeader('X-Content-Type-Options', 'nosniff');
        fs.createReadStream(coverPath).pipe(res);
      });
    }
  };
}

const backendTarget = process.env.VITE_BACKEND_TARGET || 'http://127.0.0.1:4175';
const isHttps = backendTarget.startsWith('https:');

let httpsAgent: https.Agent | undefined;
if (isHttps) {
  httpsAgent = new https.Agent({
    rejectUnauthorized: false
  });
  httpsAgent.createConnection = (options: any, cb: any) => {
    // 抑制 SNI 校验，避免直连云服务器/反代时因未备案域名触发连接重置 (ECONNRESET)
    options.servername = '';
    return (https.Agent.prototype as any).createConnection.call(httpsAgent, options, cb);
  };
}

export default defineConfig({
  plugins: [vue(), fnosCoverDevPlugin()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  },
  server: {
    host: '0.0.0.0',
    port: 5175,
    allowedHosts: ['music.miong.me', 'music-api.miong.me', 'localhost', '127.0.0.1'],
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
        agent: httpsAgent,
        ws: true
      }
    }
  }
});
