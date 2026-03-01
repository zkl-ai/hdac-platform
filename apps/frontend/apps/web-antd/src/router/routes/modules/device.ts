import type { RouteRecordRaw } from 'vue-router'
import { $t } from '#/locales'

const routes: RouteRecordRaw[] = [
  {
    name: 'Device',
    path: '/device',
    component: () => import('#/views/device/index.vue'),
    meta: {
      icon: 'lucide:server',
      title: $t('page.device.title'),
    },
  },
]

export default routes
