import { defineConfig } from '@vben/vite-config';
import { loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  return {
    application: {},
    vite: {
      server: {
        port: Number(env.VITE_PORT) || 5674,
        strictPort: true,
        proxy: {
          '/api': {
            changeOrigin: true,
            // rewrite: (path) => path.replace(/^\/api/, ''),
            // mock代理目标地址
            target: 'http://127.0.0.1:5000',
            ws: true,
          },
          '/socket.io': {
            target: 'http://127.0.0.1:5000',
            ws: true,
            changeOrigin: true,
          },
        },
      },
    },
  };
});
