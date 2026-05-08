const api = require('../../utils/api')

Page({
  data: {
    job: null,
    loading: true,
    applied: false
  },

  onLoad(options) {
    if (options.id) this.loadJob(options.id)
  },

  async loadJob(id) {
    try {
      const job = await api.getJob(id)
      this.setData({ job, loading: false })
      const applied = wx.getStorageSync('applied') || []
      this.setData({ applied: applied.includes(String(id)) })
    } catch (e) {
      this.setData({ loading: false })
    }
  },

  goApply() {
    const url = this.data.job.url
    if (!url) return
    wx.setClipboardData({
      data: url,
      success: () => wx.showToast({ title: '链接已复制，去浏览器打开', icon: 'none' })
    })
  },

  markApplied() {
    const id = String(this.data.job.id)
    const applied = wx.getStorageSync('applied') || []
    if (!applied.includes(id)) {
      applied.unshift(id)
      wx.setStorageSync('applied', applied)
      this.setData({ applied: true })
    }
  }
})
