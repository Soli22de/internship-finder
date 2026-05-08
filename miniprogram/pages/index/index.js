const api = require('../../utils/api')

Page({
  data: {
    jobs: [],
    loading: true,
    page: 1,
    hasMore: true,
    keyword: '',
    source: '',
    city: '上海',
    sources: [],
    stats: null,
    showFilter: false,
    scrollTop: 0
  },

  onLoad() {
    this.loadJobs()
    this.loadStats()
  },

  onPullDownRefresh() {
    this.setData({ page: 1, jobs: [], hasMore: true })
    this.loadJobs().then(() => wx.stopPullDownRefresh())
  },

  onReachBottom() {
    if (this.data.hasMore) {
      this.setData({ page: this.data.page + 1 })
      this.loadJobs(true)
    }
  },

  async loadJobs(append = false) {
    this.setData({ loading: true })
    try {
      const res = await api.getJobs({
        city: this.data.city,
        source: this.data.source,
        keyword: this.data.keyword,
        limit: 20,
        offset: (this.data.page - 1) * 20
      })
      const jobs = append ? this.data.jobs.concat(res.jobs) : res.jobs
      this.setData({
        jobs,
        loading: false,
        hasMore: res.jobs.length >= 20
      })
    } catch (e) {
      this.setData({ loading: false })
    }
  },

  async loadStats() {
    try {
      const stats = await api.getStats()
      this.setData({
        stats,
        sources: Object.entries(stats.by_source || {}).map(([k, v]) => ({ name: k, count: v }))
      })
    } catch (e) {}
  },

  onSearchInput(e) {
    this.setData({ keyword: e.detail.value })
  },

  onSearch() {
    this.setData({ page: 1, jobs: [] })
    this.loadJobs()
  },

  onSourceFilter(e) {
    this.setData({
      source: e.currentTarget.dataset.source,
      page: 1,
      jobs: []
    })
    this.loadJobs()
    this.setData({ showFilter: false })
  },

  toggleFilter() {
    this.setData({ showFilter: !this.data.showFilter })
  },

  goDetail(e) {
    wx.navigateTo({ url: `/pages/detail/detail?id=${e.currentTarget.dataset.id}` })
  }
})
