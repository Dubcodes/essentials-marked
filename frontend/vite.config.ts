import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const APP_VERSION = '0.1.1-demo';
const BUILD_TIME = new Date().toISOString();

export default defineConfig({
  plugins:[react()],
  define:{
    __APP_VERSION__:JSON.stringify(APP_VERSION),
    __BUILD_TIME__:JSON.stringify(BUILD_TIME)
  },
  server:{
    proxy:{
      '/api':'http://localhost:8000'
    }
  }
});