const app = getApp()

function request(url, method = 'GET', data = {}) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: app.globalData.baseUrl + url,
      method,
      data,
      header: { 'content-type': 'application/json' },
      success: res => resolve(res.data),
      fail: err => reject(err)
    })
  })
}

module.exports = {
  getJobs(params) {
    return request('/api/jobs?' + obj2params(params))
  },
  getJob(id) {
    return request('/api/jobs/' + id)
  },
  getStats() {
    return request('/api/stats')
  },
  triggerCrawl(sources) {
    return request('/api/crawl', 'POST', { sources })
  },
  matchResume(resumeText, city = '上海', topN = 20) {
    return request('/api/match', 'POST', { resume_text: resumeText, city, top_n: topN })
  },
  getHealth() {
    return request('/api/health')
  }
}

function obj2params(obj) {
  return Object.entries(obj || {})
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
    .join('&')
}
