App({
  onLaunch() {
    const logs = wx.getStorageSync('logs') || []
    logs.unshift(Date.now())
    wx.setStorageSync('logs', logs)
  },
  globalData: {
    baseUrl: 'http://127.0.0.1:8000',
    userInfo: null,
    resumeInfo: null,
    appliedJobs: []
  }
})
