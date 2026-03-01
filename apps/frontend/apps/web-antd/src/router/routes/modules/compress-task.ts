import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    name: 'CompressTask',
    path: '/compress-task',
    component: () => import('#/views/compress-task/index.vue'),
    meta: {
      icon: 'ant-design:compress-outlined',
      title: 'DNN模型压缩',
      order: 21,
    },
  },
]

export default routes
