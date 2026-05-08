Page({
  data: {
    applied: [],
    stats: { total: 0, bySource: {} }
  },

  onShow() {
    this.loadApplied()
  },

  loadApplied() {
    const ids = wx.getStorageSync('applied') || []
    this.setData({ 'stats.total': ids.length })
    // We store minimal info; could be enriched later
    this.setData({ applied: ids.map((id, i) => ({ id, index: i })).reverse() })
  },

  clearAll() {
    wx.showModal({
      title: '确认清除',
      content: '清除所有投递记录？',
      success: res => {
        if (res.confirm) {
          wx.removeStorageSync('applied')
          this.setData({ applied: [], 'stats.total': 0 })
        }
      }
    })
  }
})
