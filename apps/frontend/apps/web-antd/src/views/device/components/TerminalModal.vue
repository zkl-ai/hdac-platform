<script lang="ts" setup>
import { ref, watch, onBeforeUnmount, nextTick } from 'vue';
import { Modal } from 'ant-design-vue';
import { Terminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import { io, Socket } from 'socket.io-client';
import 'xterm/css/xterm.css';

const props = defineProps<{
  open: boolean;
  ip: string;
}>();

const emit = defineEmits(['update:open', 'close']);

const terminalContainer = ref<HTMLElement | null>(null);
let term: Terminal | null = null;
let socket: Socket | null = null;
let fitAddon: FitAddon | null = null;

const initTerminal = () => {
  if (!terminalContainer.value) return;

  if (term) {
    term.dispose();
  }

  term = new Terminal({
    cursorBlink: true,
    fontSize: 14,
    fontFamily: 'Menlo, Monaco, "Courier New", monospace',
    theme: {
      background: '#1e1e1e',
      foreground: '#f0f0f0',
    },
  });

  fitAddon = new FitAddon();
  term.loadAddon(fitAddon);
  term.open(terminalContainer.value);
  
  nextTick(() => {
    fitAddon?.fit();
  });

  let baseUrl = import.meta.env.VITE_GLOB_API_URL || 'http://localhost:5088';
  let socketUrl = '';
  try {
      // Extract origin if url has path
      if (baseUrl.startsWith('http')) {
        const u = new URL(baseUrl);
        socketUrl = u.origin;
      }
      // If relative (e.g. /api), we assume proxy handles it at root, so we use empty string (current origin)
  } catch (e) {
      console.warn('Failed to parse API URL, using default');
  }

  const namespaceUrl = socketUrl ? `${socketUrl}/ssh` : '/ssh';

  const sshSocket = io(namespaceUrl, {
      transports: ['websocket'],
      path: '/socket.io'
  });

  sshSocket.on('connect', () => {
    term?.write('\r\n*** Connecting to ' + props.ip + '... ***\r\n');
    sshSocket.emit('start_ssh', { ip: props.ip });
  });

  sshSocket.on('output', (data: any) => {
    term?.write(data.data);
  });
  
  sshSocket.on('disconnect', () => {
    term?.write('\r\n*** Disconnected ***\r\n');
  });

  sshSocket.on('connect_error', (err) => {
    term?.write(`\r\n*** Connection Error: ${err.message} ***\r\n`);
  });

  term.onData((data) => {
    sshSocket.emit('input', { data });
  });

  term.onResize((size) => {
      sshSocket.emit('resize', { rows: size.rows, cols: size.cols });
  });

  socket = sshSocket;
  
  window.addEventListener('resize', handleWindowResize);
};

const handleWindowResize = () => {
  fitAddon?.fit();
  if (term && socket) {
      socket.emit('resize', { rows: term.rows, cols: term.cols });
  }
};

const handleClose = () => {
  if (socket) {
    socket.disconnect();
    socket = null;
  }
  if (term) {
    term.dispose();
    term = null;
  }
  window.removeEventListener('resize', handleWindowResize);
  emit('update:open', false);
  emit('close');
};

watch(
  () => props.open,
  (val) => {
    if (val) {
      nextTick(() => {
        initTerminal();
      });
    }
  }
);

onBeforeUnmount(() => {
  if (socket) socket.disconnect();
  if (term) term.dispose();
  window.removeEventListener('resize', handleWindowResize);
});
</script>

<template>
  <Modal
    :open="open"
    title="远程终端"
    :footer="null"
    width="80%"
    :destroy-on-close="true"
    :mask-closable="false"
    @cancel="handleClose"
    wrap-class-name="terminal-modal"
  >
    <div ref="terminalContainer" style="height: 600px; width: 100%; background-color: #1e1e1e; padding: 10px; overflow: hidden; border-radius: 4px;"></div>
  </Modal>
</template>

<style>
.terminal-modal .ant-modal-body {
    padding: 0;
}
</style>