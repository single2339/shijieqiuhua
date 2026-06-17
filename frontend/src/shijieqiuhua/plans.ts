// Single source of truth for subscription tiers, shared by LandingPage and PaywallModal.

export interface Plan {
  id: 'guest' | 'free' | 'paid'
  name: string
  price: string
  unit: string
  items: string[]
  featured: boolean
}

export const PLANS: Plan[] = [
  {
    id: 'guest', name: '试用', price: '0', unit: '免登录',
    items: ['浏览今日赛程', '查看公开倾向标签', '了解研判方法论'],
    featured: false,
  },
  {
    id: 'free', name: '注册会员', price: '0', unit: '需邀请码',
    items: ['每日 1 次完整研判', '证据链与信源状态', '置信度评级', '问答历史保留 7 天'],
    featured: false,
  },
  {
    id: 'paid', name: '情报通', price: '39', unit: '/ 月',
    items: ['无限次完整研判', '因子权重与贝叶斯轨迹', '开赛前自动复扫提醒', '导出研判报告', '优先接入新信源'],
    featured: true,
  },
]
