import { defineConfig } from 'vitepress'

export default defineConfig({
  lang: 'zh-CN',
  title: 'AI Code Review',
  description: 'AI 驱动的代码审查工具',
  base: '/ai-code-review/',

  head: [
    ['link', { rel: 'icon', href: '/ai-code-review/favicon.ico' }],
  ],

  themeConfig: {
    logo: '/logo.svg',

    nav: [
      { text: '指南', link: '/guide/getting-started' },
      { text: '配置', link: '/guide/configuration' },
      { text: '命令', link: '/guide/commands' },
      { text: '规则系统', link: '/guide/rules' },
      { text: 'GitHub', link: 'https://github.com/SoloShine/ai-code-review' },
    ],

    sidebar: {
      '/guide/': [
        {
          text: '介绍',
          items: [
            { text: '什么是 AI Code Review', link: '/guide/getting-started' },
            { text: '快速开始', link: '/guide/quick-start' },
            { text: 'AI Agent 一键配置', link: '/guide/ai-agent-setup' },
          ],
        },
        {
          text: '核心功能',
          items: [
            { text: '配置说明', link: '/guide/configuration' },
            { text: '命令参考', link: '/guide/commands' },
            { text: '规则系统', link: '/guide/rules' },
            { text: '通知中心', link: '/guide/inbox' },
            { text: '抑制管理', link: '/guide/suppress' },
          ],
        },
        {
          text: '进阶',
          items: [
            { text: 'LLM 后端', link: '/guide/llm-backends' },
            { text: 'Git Hooks', link: '/guide/hooks' },
            { text: '记忆系统', link: '/guide/memory' },
            { text: '常见问题', link: '/guide/faq' },
          ],
        },
      ],
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/SoloShine/ai-code-review' },
    ],

    footer: {
      message: '基于 MIT 协议发布',
      copyright: 'Copyright 2026 SoloShine',
    },

    search: {
      provider: 'local',
      options: {
        locales: {
          zh: {
            translations: {
              button: { buttonText: '搜索文档', buttonAriaLabel: '搜索文档' },
              modal: {
                noResultsText: '无法找到相关结果',
                resetButtonTitle: '清除查询条件',
                footer: { selectText: '选择', navigateText: '切换', closeText: '关闭' },
              },
            },
          },
        },
      },
    },
  },
})
