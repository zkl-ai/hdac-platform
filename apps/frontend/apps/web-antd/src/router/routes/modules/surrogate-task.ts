import type { RouteRecordRaw } from 'vue-router'
import { $t } from '#/locales'

const routes: RouteRecordRaw[] = [
  {
    name: 'SurrogateTask',
    path: '/surrogate-task',
    component: () => import('#/views/surrogate-task/index.vue'),
    meta: {
      icon: 'ant-design:deployment-unit-outlined',
      title: $t('page.surrogateTask.title'),
      order: 20,
    },
  },
]

export default routes
