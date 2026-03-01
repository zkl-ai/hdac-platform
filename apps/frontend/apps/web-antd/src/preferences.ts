import { defineOverridesPreferences } from '@vben/preferences';

/**
 * @description 项目配置文件
 * 覆盖需要修改的配置，不写的继续使用默认配置
 * 更改配置后请清空缓存，否则可能不生效
 */
export const overridesPreferences = defineOverridesPreferences({
  app: {
    name: 'HDAC Platform',
    dynamicTitle: true,
    enablePreferences: false,
    layout: "header-nav",
    defaultHomePath: '/dashboard',
    authPageLayout: 'panel-center',
  },
  logo: {
    enable: true,
    source: '/logo.png',
  },
  // 可选：顺手把版权信息也改掉
  copyright: {
    companyName: 'HDAC Platform',
    companySiteLink: '#', // 没有就写 '#'
  },
  widget: {
    fullscreen: true,
    globalSearch: false,
    languageToggle: false,
    lockScreen: false,
    notification: false,
    refresh: true,
    sidebarToggle: false,
    themeToggle: true,
    timezone:false,
  },
  theme: {
    mode: 'light',
  }

});
