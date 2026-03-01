import type { RouteRecordRaw } from 'vue-router'
import { $t } from '#/locales'

const routes: RouteRecordRaw[] = [
  {
    name: 'ModelLibrary',
    path: '/model',
    component: () => import('#/views/model/index.vue'),
    meta: {
      icon: 'ant-design:appstore-outlined',
      title: $t('page.model.title'),
    },
  },
]

export default routes
