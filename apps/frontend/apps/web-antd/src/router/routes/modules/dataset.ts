import type { RouteRecordRaw } from 'vue-router'
import { $t } from '#/locales'

const routes: RouteRecordRaw[] = [
  {
    name: 'Dataset',
    path: '/dataset',
    component: () => import('#/views/dataset/index.vue'),
    meta: {
      icon: 'ant-design:database-outlined',
      title: '数据集管理',
    },
  },
]

export default routes
