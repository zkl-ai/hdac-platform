import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    name: 'GrayDeployTask',
    path: '/gray-deploy-task',
    component: () => import('#/views/gray-deploy-task/index.vue'),
    meta: {
      icon: 'ant-design:rocket-outlined',
      title: 'DNN模型部署',
      order: 22,
    },
  },
]

export default routes
