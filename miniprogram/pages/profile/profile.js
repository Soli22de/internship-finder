const api = require('../../utils/api')

Page({
  data: {
    stats: null,
    health: null,
    city: '上海',
    sources: []
  },

  onShow() {
    this.loadInfo()
  },

  async loadInfo() {
    try {
      const [stats, health] = await Promise.all([api.getStats(), api.getHealth()])
      this.setData({
        stats,
        health,
        sources: Object.entries(stats.by_source || {}).map(([k, v]) => ({ name: k, count: v }))
      })
    } catch (e) {}
  },

  async doCrawl() {
    wx.showLoading({ title: '爬取中...' })
    try {
      const res = await api.triggerCrawl()
      wx.hideLoading()
      wx.showToast({ title: `更新了 ${res.total_sources} 个数据源`, icon: 'none' })
      this.loadInfo()
    } catch (e) {
      wx.hideLoading()
      wx.showToast({ title: '爬取失败', icon: 'none' })
    }
  },

  onCityChange(e) {
    this.setData({ city: e.detail.value })
  }
})
